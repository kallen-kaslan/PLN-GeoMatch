"""Exercise the real application policy, with no authentication bypass overrides."""

from datetime import timedelta

import pytest
from app.application import create_application
from app.auth_schema import upgrade_auth
from app.config import Settings, settings
from app.database import get_db
from app.models.auth import AuthAudit, AuthSession, AuthThrottle, utcnow
from app.models.user import User
from app.modules.auth.bootstrap import create_initial_admin
from app.modules.auth.security import cookie_name, digest, password_valid
from fastapi.testclient import TestClient
from sqlalchemy import select

PASSWORD = "Kopi pagi untuk admin 874!"
OTHER_PASSWORD = "Langit sore milik analis 582!"


@pytest.fixture
def secured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "ALLOW_TEST_DATA_TOOLS", False)
    upgrade_auth(db_session.connection())
    db_session.commit()
    create_initial_admin(db_session, "admin", PASSWORD)
    app = create_application()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        yield client, db_session


def login(client, username="admin", password=PASSWORD):
    result = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-Requested-With": "PLN-GeoMatch"},
    )
    if result.status_code == 200:
        client.headers["X-CSRF-Token"] = client.cookies[cookie_name(True)]
    return result


def add_user(client, username="analis", role="analis"):
    response = client.post(
        "/admin/users",
        json={
            "username": username,
            "password": OTHER_PASSWORD,
            "role": role,
            "admin_password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/history/processes"),
        ("GET", "/master/dil/records"),
        ("GET", "/pdpj/batches"),
        ("GET", "/corrections/ready-pdpj"),
        ("POST", "/upload/reset"),
        ("DELETE", "/history/processes"),
        ("GET", "/admin/users"),
        ("GET", "/auth/me"),
        ("POST", "/upload/progress"),
        ("POST", "/corrections/idpel_kosong/checks/1/automatic/preview"),
        ("POST", "/corrections/idpel_kosong/checks/1/automatic/apply"),
        ("POST", "/corrections/idpel_kosong/checks/1/automatic/review-groups"),
        ("POST", "/corrections/idpel_kosong/checks/1/automatic/suggestions/export"),
        ("POST", "/corrections/idpel_kosong/checks/1/automatic/unpaired-search"),
        ("POST", "/corrections/idpel_kosong/checks/1/automatic/unpaired-search/export"),
        ("GET", "/corrections/idpel_kosong/checks/1/records/1/advanced-candidates"),
    ],
)
def test_all_data_routes_reject_missing_and_fake_tokens(secured, method, path):
    client, _ = secured
    for headers in ({}, {"Authorization": "Bearer mock-token-dev"}):
        assert client.request(method, path, headers=headers).status_code == 401


def test_real_login_cookie_security_session_hash_and_logout(secured):
    client, db = secured
    assert login(client, password="wrong").status_code == 401
    assert login(client, username="unknown", password="wrong").json() == {
        "detail": "Username atau password salah"
    }
    result = login(client)
    assert result.status_code == 200 and result.json()["role"] == "admin"
    assert "access_token" not in result.json() and "password" not in result.text
    session_cookie = next(
        value
        for value in result.headers.get_list("set-cookie")
        if value.startswith(cookie_name() + "=")
    )
    assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie
    token = client.cookies[cookie_name()]
    stored = db.query(AuthSession).one()
    assert stored.token_hash == digest(token) and token not in stored.token_hash
    user = db.query(User).one()
    assert user.hashed_password.startswith("$argon2id$") and password_valid(
        PASSWORD, user.hashed_password
    )
    assert client.get("/auth/me").json()["username"] == "admin"
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401
    client.cookies.set(cookie_name(), token)
    assert client.get("/history/processes").status_code == 401
    assert db.query(AuthAudit).filter_by(action="logout").count() == 1


def test_csrf_origin_login_header_and_registration_denied(secured):
    client, _ = secured
    body = {"username": "admin", "password": PASSWORD}
    assert client.post("/auth/login", json=body).status_code == 403
    assert (
        client.post(
            "/auth/login",
            json=body,
            headers={
                "X-Requested-With": "PLN-GeoMatch",
                "Origin": "https://evil.example",
            },
        ).status_code
        == 403
    )
    assert login(client).status_code == 200
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/auth/logout").status_code == 403
    assert (
        client.post("/auth/logout", headers={"X-CSRF-Token": "forged"}).status_code
        == 403
    )
    assert (
        client.post(
            "/auth/logout",
            headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert client.post("/auth/register", json=body).status_code == 404
    assert (
        client.post("/upload/reset", headers={"X-CSRF-Token": csrf}).status_code == 403
    )


def test_admin_account_management_revokes_sessions_and_preserves_last_admin(secured):
    client, db = secured
    login(client)
    user = add_user(client)
    other = TestClient(client.app)
    assert login(other, "analis", OTHER_PASSWORD).status_code == 200
    other_token = other.cookies[cookie_name()]
    assert other.get("/admin/users").status_code == 403
    assert (
        other.post(
            "/admin/users",
            json={
                "username": "intruder",
                "role": "admin",
                "password": OTHER_PASSWORD,
                "admin_password": OTHER_PASSWORD,
            },
        ).status_code
        == 403
    )
    assert other.delete("/history/processes").status_code == 403
    admin = db.query(User).filter_by(username="admin").one()
    body = {"role": "analis", "is_active": False, "admin_password": PASSWORD}
    assert client.patch("/admin/users/" + admin.id, json=body).status_code == 403
    assert client.patch("/admin/users/" + user["id"], json=body).status_code == 200
    assert db.query(AuthSession).filter_by(token_hash=digest(other_token)).count() == 0
    assert other.get("/history/processes").status_code == 401
    assert login(other, "analis", OTHER_PASSWORD).status_code == 401
    assert (
        client.patch(
            "/admin/users/" + user["id"],
            json={
                **body,
                "is_active": True,
                "password": "Password baru yang unik 961!",
            },
        ).status_code
        == 200
    )
    assert login(other, "analis", OTHER_PASSWORD).status_code == 401
    assert login(other, "analis", "Password baru yang unik 961!").status_code == 200


def test_auditor_read_only_and_password_change_revokes_all_sessions(secured):
    client, db = secured
    login(client)
    add_user(client, "audit01", "auditor")
    login(client, "audit01", OTHER_PASSWORD)
    assert client.get("/history/processes").status_code == 200
    assert client.post("/pdpj/reviews", json={"batch_id": 1}).status_code == 403
    for action in ("preview", "apply", "review-groups", "suggestions/export", "unpaired-search", "unpaired-search/export"):
        assert client.post(f"/corrections/idpel_kosong/checks/1/automatic/{action}", json={}).status_code == 403
    old_token = client.cookies[cookie_name()]
    result = client.post(
        "/auth/password",
        json={
            "current_password": OTHER_PASSWORD,
            "new_password": "Password auditor baru 774!",
        },
    )
    assert result.status_code == 204, result.text
    assert db.query(AuthSession).filter_by(token_hash=digest(old_token)).count() == 0
    assert login(client, "audit01", OTHER_PASSWORD).status_code == 401
    assert login(client, "audit01", "Password auditor baru 774!").status_code == 200


def test_idle_and_absolute_expiration_are_enforced_on_server(secured):
    client, db = secured
    for field, value in (
        ("last_seen_at", utcnow() - timedelta(minutes=31)),
        ("expires_at", utcnow() - timedelta(seconds=1)),
    ):
        assert login(client).status_code == 200
        session = (
            db.query(AuthSession)
            .filter_by(token_hash=digest(client.cookies[cookie_name()]))
            .one()
        )
        setattr(session, field, value)
        db.commit()
        assert client.get("/history/processes").status_code == 401


def test_brute_force_limit_is_persistent_and_expires(secured):
    client, db = secured
    for _ in range(settings.AUTH_LOGIN_ACCOUNT_LIMIT):
        assert login(client, password="wrong").status_code == 401
    result = login(client)
    assert result.status_code == 429 and result.headers["retry-after"] == "900"
    bucket = db.get(AuthThrottle, digest("account:admin"))
    bucket.started_at = utcnow() - timedelta(minutes=16)
    db.commit()
    assert login(client).status_code == 200


def test_password_rules_hidden_validation_values_and_no_escalation(secured):
    client, db = secured
    login(client)
    response = client.post(
        "/admin/users",
        json={"username": "weak", "password": "abc", "admin_password": PASSWORD},
    )
    assert response.status_code == 422
    assert "abc" not in response.text and PASSWORD not in response.text
    assert "input" not in response.text
    assert (
        client.post(
            "/admin/users",
            json={
                "username": "duplicate",
                "password": OTHER_PASSWORD,
                "role": "superadmin",
                "admin_password": PASSWORD,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/admin/users",
            json={
                "username": "valid-user",
                "password": OTHER_PASSWORD,
                "admin_password": "wrong",
            },
        ).status_code
        == 403
    )
    assert db.query(User).count() == 1
    with pytest.raises(ValueError, match="Admin aktif"):
        create_initial_admin(db, "another-admin", PASSWORD)
    db.rollback()
    assert db.query(User).count() == 1


def test_audit_actor_cannot_be_forged(secured):
    client, db = secured
    login(client)
    from tests.test_corrections import upload

    upload(client, "dil", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    batch = upload(client, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n")
    review = client.post("/pdpj/reviews", json={"batch_id": batch}).json()
    row = client.get(f"/pdpj/reviews/{review['id']}/rows").json()["items"][0]
    response = client.post(
        f"/pdpj/reviews/{review['id']}/rows/{row['id']}/decision",
        json={
            "revision": review["revision"],
            "actor": "Pretend Administrator",
            "action": "exception",
            "reason": "Perlu verifikasi lapangan",
        },
    )
    assert response.status_code == 200, response.text
    from app.models.pdpj import PdpjChange

    assert db.query(PdpjChange).one().actor == "admin"


def test_production_config_requires_https_and_disables_test_tools():
    for kwargs in (
        {},
        {"AUTH_COOKIE_SECURE": True, "ALLOW_TEST_DATA_TOOLS": True},
        {"AUTH_COOKIE_SECURE": True, "CORS_ALLOWED_ORIGINS": ["http://example.com"]},
    ):
        with pytest.raises(ValueError):
            Settings(_env_file=None, APP_ENV="production", **kwargs)
    secure = Settings(
        _env_file=None,
        APP_ENV="production",
        AUTH_COOKIE_SECURE=True,
        CORS_ALLOWED_ORIGINS=["https://geomatch.example"],
    )
    assert secure.AUTH_COOKIE_SECURE


def test_auth_schema_idempotent_preserves_existing_data(secured):
    _, db = secured
    upgrade_auth(db.connection())
    db.commit()
    assert db.execute(select(User.username)).scalar_one() == "admin"


def test_production_cookie_attributes(secured, monkeypatch):
    client, _ = secured
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", True)
    with TestClient(client.app, base_url="https://testserver") as browser:
        response = login(browser)
        assert response.status_code == 200
        cookies = response.headers.get_list("set-cookie")
        session = next(
            value for value in cookies if value.startswith("__Host-geomatch_session=")
        )
        assert "Secure" in session and "HttpOnly" in session and "Path=/" in session
        assert "Domain=" not in session and "Max-Age=" not in session
        assert browser.get("/auth/me").status_code == 200


def test_ip_limit_covers_different_usernames(secured, monkeypatch):
    client, db = secured
    monkeypatch.setattr(settings, "AUTH_LOGIN_IP_LIMIT", 5)
    for number in range(5):
        assert login(client, "unknown-" + str(number), "wrong").status_code == 401
    assert login(client, "another-username", "wrong").status_code == 429
    assert db.query(AuthThrottle).count() == 6  # one IP and five account buckets


def test_concurrent_admin_deactivation_keeps_an_active_admin(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from app.models.user import UserRole
    from app.sqlite_runtime import configure_sqlite_engine
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine(
        "sqlite:///" + (tmp_path / "auth.db").as_posix(),
        connect_args={"check_same_thread": False},
    )
    configure_sqlite_engine(engine)
    with engine.begin() as connection:
        upgrade_auth(connection)
    with Session(engine) as db:
        create_initial_admin(db, "admin", PASSWORD)
    app = create_application()

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    with TestClient(app) as first, TestClient(app) as second:
        assert login(first).status_code == 200
        other = add_user(first, "second-admin", "admin")
        assert login(second, "second-admin", OTHER_PASSWORD).status_code == 200
        first_id = first.get("/auth/me").json()["id"]

        def disable(client, identity, password):
            return client.patch(
                "/admin/users/" + identity,
                json={"role": "admin", "is_active": False, "admin_password": password},
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(disable, first, other["id"], PASSWORD),
                pool.submit(disable, second, first_id, OTHER_PASSWORD),
            ]
            statuses = [future.result(timeout=15) for future in futures]
        assert sorted(statuses) == [200, 401]
        with Session(engine) as db:
            assert (
                db.query(User)
                .filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
                .count()
                == 1
            )
    engine.dispose()


def test_session_heartbeat_does_not_block_progress_reads_during_sqlite_import(tmp_path):
    from time import monotonic

    from app.models.auth import AuthGuard
    from app.sqlite_runtime import configure_sqlite_engine
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session

    engine = create_engine(
        "sqlite:///" + (tmp_path / "auth-busy.db").as_posix(),
        connect_args={"check_same_thread": False},
    )
    configure_sqlite_engine(engine)
    with engine.begin() as connection:
        upgrade_auth(connection)
    with Session(engine) as db:
        create_initial_admin(db, "admin", PASSWORD)
    app = create_application()

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    with TestClient(app) as client:
        assert login(client).status_code == 200
        token_hash = digest(client.cookies[cookie_name()])
        with Session(engine) as db:
            db.get(AuthSession, token_hash).last_seen_at = utcnow() - timedelta(
                seconds=70
            )
            db.commit()
        with engine.connect() as writer:
            writer.execute(
                update(AuthGuard).where(AuthGuard.id == 1).values(revision=1)
            )
            started = monotonic()
            assert client.get("/auth/me").status_code == 200
            assert monotonic() - started < 2
            writer.rollback()
        assert client.get("/auth/me").status_code == 200
        with Session(engine) as db:
            assert (
                utcnow() - db.get(AuthSession, token_hash).last_seen_at
            ).total_seconds() < 5
        with engine.connect() as connection:
            assert (
                connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 5000
            )
    engine.dispose()
