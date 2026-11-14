"""Isolated browser, API, and database fixtures shared by feature acceptance tests."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from functools import wraps
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
TEST_USERNAME = "test-admin"
TEST_PASSWORD = "Browser admin password 2026!"

# The startup animation now includes a five-second logo entrance and a fade.
expect.set_options(timeout=10000)


def free_port() -> int:
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def wait_server(url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server pengujian berhenti sebelum siap: {url}")
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"Server pengujian tidak siap: {url}")


@pytest.fixture(scope="module")
def servers(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, str]]:
    folder = tmp_path_factory.mktemp("master-browser")
    api_port, frontend_port = free_port(), free_port()
    api_url, ui_url = (
        f"http://127.0.0.1:{api_port}",
        f"http://127.0.0.1:{frontend_port}",
    )
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{(folder / 'isolated.db').as_posix()}",
        "UPLOAD_STORAGE_DIR": str(folder / "uploads"),
        "VITE_API_PROXY_TARGET": api_url,
        "VITE_API_BASE_URL": "/api",
        "ALLOW_SYNC_FALLBACK": "true",
        "REDIS_URL": "redis://127.0.0.1:1/0",
        "APP_ENV": "development",
        "AUTH_COOKIE_SECURE": "false",
        "ALLOW_TEST_DATA_TOOLS": "true",
        "CORS_ALLOWED_ORIGINS": json.dumps([ui_url]),
    }
    processes = []
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "app.modules.auth.bootstrap",
                "--username",
                TEST_USERNAME,
                "--password-stdin",
            ],
            input=TEST_PASSWORD + "\n",
            text=True,
            cwd=ROOT / "backend",
            env=environment,
            capture_output=True,
            check=True,
            **options,
        )
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    os.environ.get("E2E_ASGI_APP", "app.main:app"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--no-access-log",
                    "--log-level",
                    "warning",
                ],
                cwd=ROOT / "backend",
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **options,
            )
        )
        wait_server(api_url, processes[-1])
        node = shutil.which("node")
        assert node is not None
        processes.append(
            subprocess.Popen(
                [
                    node,
                    str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(frontend_port),
                    "--strictPort",
                ],
                cwd=ROOT / "frontend",
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **options,
            )
        )
        wait_server(ui_url, processes[-1])
        yield ui_url, api_url
    finally:
        for process in reversed(processes):
            process.terminate()
            process.wait(timeout=10)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        channel = os.environ.get(
            "E2E_BROWSER_CHANNEL", "msedge" if os.name == "nt" else "chromium"
        )
        instance = playwright.chromium.launch(channel=channel, headless=True)
        yield instance
        instance.close()


@pytest.fixture
def authenticated_api(servers: tuple[str, str], monkeypatch) -> Iterator[httpx.Client]:
    """Real login for business tests; never disable application security."""
    with httpx.Client(
        base_url=servers[1], headers={"X-Requested-With": "PLN-GeoMatch"}
    ) as client:
        result = client.post(
            "/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        result.raise_for_status()
        client.headers["X-CSRF-Token"] = client.cookies["geomatch_csrf"]
        for method in ("get", "post", "patch", "put", "delete", "request"):
            original = getattr(httpx, method)

            def wrap(function):
                @wraps(function)
                def authenticated(*args, **kwargs):
                    url = args[1] if function.__name__ == "request" else args[0]
                    if str(url).startswith(servers[1] + "/"):
                        kwargs.setdefault("cookies", client.cookies)
                        kwargs["headers"] = {
                            **dict(client.headers),
                            **kwargs.get("headers", {}),
                        }
                    return function(*args, **kwargs)

                return authenticated

            monkeypatch.setattr(httpx, method, wrap(original))
        yield client


@pytest.fixture
def page(
    browser: Browser, servers: tuple[str, str], authenticated_api: httpx.Client
) -> Iterator[Page]:
    assert httpx.post(f"{servers[1]}/upload/reset").status_code == 200
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000}, base_url=servers[0]
    )
    signed_in = context.request.post(
        servers[1] + "/auth/login",
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        headers={"X-Requested-With": "PLN-GeoMatch"},
    )
    assert signed_in.ok
    errors = []
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    context.close()
    assert not errors, f"Kesalahan browser: {errors}"
