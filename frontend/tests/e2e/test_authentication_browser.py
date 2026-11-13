"""Real authentication, guarded navigation, admin accounts, and revoked sessions."""

import httpx
from conftest import TEST_PASSWORD, TEST_USERNAME
from playwright.sync_api import Page, expect

USER_PASSWORD = "Password analis browser 593!"


def login_ui(page: Page, username: str, password: str) -> None:
    form = page.get_by_role("form", name="Form login", exact=True)
    expect(form).to_be_visible()
    form.get_by_label("Username", exact=True).fill(username)
    form.get_by_label("Password", exact=True).fill(password)
    form.get_by_role("button", name="Masuk", exact=True).click()


def sign_out(page: Page) -> None:
    page.get_by_role("button", name="Menu akun pengguna", exact=True).click()
    page.get_by_role("menuitem", name="Keluar dari Sistem", exact=True).click()
    page.wait_for_url("**/login")


def test_default_login_no_registration_wrong_password_and_logout(
    page: Page,
    servers: tuple[str, str],
) -> None:
    page.context.clear_cookies()
    page.goto("/")
    page.wait_for_url("**/login")
    expect(page.get_by_role("heading", name="Masuk", exact=True)).to_be_visible()
    expect(page.get_by_text("Daftar sekarang", exact=True)).to_have_count(0)
    expect(page.get_by_label("Konfirmasi password", exact=True)).to_have_count(0)
    login_ui(page, TEST_USERNAME, "wrong-password")
    expect(page.get_by_role("alert")).to_have_text("Username atau password salah")
    login_ui(page, TEST_USERNAME, TEST_PASSWORD)
    expect(
        page.get_by_role("button", name="Menu akun pengguna", exact=True)
    ).to_be_visible()
    assert "geomatch_session" not in page.evaluate("document.cookie")
    assert "geomatch_csrf" in page.evaluate("document.cookie")
    cookies = {cookie["name"]: cookie["value"] for cookie in page.context.cookies()}
    page.reload()
    expect(
        page.get_by_role("button", name="Menu akun pengguna", exact=True)
    ).to_be_visible()
    sign_out(page)
    with httpx.Client(cookies=cookies) as client:
        assert client.get(servers[1] + "/history/processes").status_code == 401
    page.goto("/master/dil")
    page.wait_for_url("**/login")


def test_logout_clears_another_open_tab(page: Page) -> None:
    page.goto("/master/dil")
    other = page.context.new_page()
    other.goto("/history")
    expect(other.get_by_role("button", name="Menu akun pengguna", exact=True)).to_be_visible()
    sign_out(page)
    other.wait_for_url("**/login")
    other.close()


def test_admin_creates_real_account_and_nonadmin_cannot_manage_users(
    page: Page,
    servers: tuple[str, str],
) -> None:
    page.goto("/admin")
    page.get_by_role("button", name="Tambah pengguna", exact=True).click()
    form = page.get_by_role("region", name="Tambah pengguna", exact=True)
    form.get_by_label("Username", exact=True).fill("browser-analis")
    form.get_by_label("Password pengguna", exact=True).fill(USER_PASSWORD)
    form.get_by_label("Konfirmasi password pengguna", exact=True).fill(USER_PASSWORD)
    form.get_by_label("Password admin Anda", exact=True).fill(TEST_PASSWORD)
    form.get_by_role("button", name="Buat pengguna", exact=True).click()
    expect(page.get_by_role("table")).to_contain_text("browser-analis")
    sign_out(page)
    login_ui(page, "browser-analis", USER_PASSWORD)
    expect(
        page.get_by_role("button", name="Menu akun pengguna", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("link", name="Manajemen Pengguna", exact=True)
    ).to_have_count(0)
    page.goto("/admin")
    expect(
        page.get_by_role("heading", name="Akses Ditolak", exact=True)
    ).to_be_visible()
    cookies = {cookie["name"]: cookie["value"] for cookie in page.context.cookies()}
    with httpx.Client(
        cookies=cookies, headers={"X-CSRF-Token": cookies["geomatch_csrf"]}
    ) as client:
        assert client.get(servers[1] + "/admin/users").status_code == 403
        assert (
            client.post(
                servers[1] + "/admin/users",
                json={
                    "username": "rogue-admin",
                    "password": USER_PASSWORD,
                    "role": "admin",
                    "admin_password": USER_PASSWORD,
                },
            ).status_code
            == 403
        )


def test_blocking_account_revokes_browser_session(
    page: Page,
    servers: tuple[str, str],
    authenticated_api: httpx.Client,
) -> None:
    created = authenticated_api.post(
        "/admin/users",
        json={
            "username": "blocked-analis",
            "password": USER_PASSWORD,
            "role": "analis",
            "admin_password": TEST_PASSWORD,
        },
    )
    created.raise_for_status()
    page.context.clear_cookies()
    page.goto("/login")
    login_ui(page, "blocked-analis", USER_PASSWORD)
    expect(
        page.get_by_role("button", name="Menu akun pengguna", exact=True)
    ).to_be_visible()
    response = authenticated_api.patch(
        "/admin/users/" + created.json()["id"],
        json={"role": "analis", "is_active": False, "admin_password": TEST_PASSWORD},
    )
    response.raise_for_status()
    page.goto("/master/dil")
    page.wait_for_url("**/login")
    login_ui(page, "blocked-analis", USER_PASSWORD)
    expect(page.get_by_role("alert")).to_have_text("Username atau password salah")


def test_user_can_change_own_password_and_must_login_again(
    page: Page,
    authenticated_api: httpx.Client,
) -> None:
    authenticated_api.post(
        "/admin/users",
        json={
            "username": "password-analis",
            "password": USER_PASSWORD,
            "role": "analis",
            "admin_password": TEST_PASSWORD,
        },
    ).raise_for_status()
    page.context.clear_cookies()
    page.goto("/login")
    login_ui(page, "password-analis", USER_PASSWORD)
    page.get_by_role("button", name="Menu akun pengguna", exact=True).click()
    page.get_by_role("menuitem", name="Ubah password", exact=True).click()
    dialog = page.get_by_role("dialog", name="Ubah password", exact=True)
    dialog.get_by_label("Password saat ini", exact=True).fill(USER_PASSWORD)
    dialog.get_by_label("Password baru", exact=True).fill(
        "Password yang baru browser 872!"
    )
    dialog.get_by_label("Konfirmasi password baru", exact=True).fill(
        "Password yang baru browser 872!"
    )
    dialog.get_by_role("button", name="Simpan password", exact=True).click()
    page.wait_for_url("**/login")
    expect(page.get_by_role("status")).to_contain_text("Password berhasil diubah")
    login_ui(page, "password-analis", USER_PASSWORD)
    expect(page.get_by_role("alert")).to_have_text("Username atau password salah")
    login_ui(page, "password-analis", "Password yang baru browser 872!")
    expect(
        page.get_by_role("button", name="Menu akun pengguna", exact=True)
    ).to_be_visible()
