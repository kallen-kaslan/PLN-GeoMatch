"""Isolated browser, API, and database fixtures shared by feature acceptance tests."""

import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]


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
        "VITE_API_PROXY_TARGET": api_url,
        "VITE_API_BASE_URL": "/api",
        "ALLOW_SYNC_FALLBACK": "true",
        "REDIS_URL": "redis://127.0.0.1:1/0",
    }
    processes = []
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
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
def page(browser: Browser, servers: tuple[str, str]) -> Iterator[Page]:
    assert httpx.post(f"{servers[1]}/upload/reset").status_code == 200
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000}, base_url=servers[0]
    )
    errors = []
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    context.close()
    assert not errors, f"Kesalahan browser: {errors}"
