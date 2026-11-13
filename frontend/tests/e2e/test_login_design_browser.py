"""Branded login, responsive form, password visibility, and reduced motion."""

import pytest
from conftest import ROOT, TEST_PASSWORD, TEST_USERNAME
from playwright.sync_api import expect


@pytest.mark.parametrize(
    "viewport",
    [
        {"width": 1440, "height": 900},
        {"width": 390, "height": 844},
        {"width": 360, "height": 640},
    ],
)
def test_login_logo_intro_responsive_layout_password_visibility_and_sign_in(
    page, viewport
):
    page.set_viewport_size(viewport)
    page.context.clear_cookies()
    page.goto("/login")
    expect(
        page.get_by_role("main", name="Memuat PLN GeoMatch", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("img", name="Logo PLN", exact=True)).to_be_visible()
    form = page.get_by_role("form", name="Form login", exact=True)
    expect(form).to_be_visible()
    expect(page.get_by_role("heading", name="Masuk", exact=True)).to_be_visible()
    logo = page.get_by_role("img", name="Logo PLN", exact=True)
    assert logo.evaluate("element => element.complete && element.naturalWidth > 0")
    # Screenshots are local review artifacts, never uploaded or used as app data.
    folder = ROOT / ".runtime" / "login-design-preview"
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(folder / f"login-{viewport['width']}.png"), animations="disabled"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    brand = page.locator(".auth-brand").bounding_box()
    panel = page.locator(".auth-form-panel").bounding_box()
    assert brand and panel
    if viewport["width"] >= 900:
        assert brand["x"] + brand["width"] <= panel["x"] + 1
        assert abs(brand["y"] - panel["y"]) <= 1
    else:
        assert brand["y"] + brand["height"] <= panel["y"] + 1
    calls = []
    page.on(
        "request",
        lambda request: (
            calls.append(request.url) if request.url.endswith("/auth/login") else None
        ),
    )
    username = form.get_by_label("Username", exact=True)
    password = form.get_by_label("Password", exact=True)
    username.fill(TEST_USERNAME)
    password.fill(TEST_PASSWORD)
    expect(password).to_have_attribute("type", "password")
    reveal = form.get_by_role("button", name="Tampilkan password", exact=True)
    reveal.click()
    expect(password).to_have_attribute("type", "text")
    expect(password).to_have_value(TEST_PASSWORD)
    expect(
        form.get_by_role("button", name="Sembunyikan password", exact=True)
    ).to_have_attribute("aria-pressed", "true")
    form.get_by_role("button", name="Sembunyikan password", exact=True).click()
    expect(password).to_have_attribute("type", "password")
    assert not calls  # Visibility controls must never submit credentials.
    expect(page.get_by_role("link", name="Daftar", exact=True)).to_have_count(0)
    form.get_by_role("button", name="Masuk", exact=True).click()
    expect(
        page.get_by_role("button", name="Menu akun pengguna", exact=True)
    ).to_be_visible()
    assert len(calls) == 1


def test_reduced_motion_and_keyboard_password_control(page):
    page.emulate_media(reduced_motion="reduce")
    page.context.clear_cookies()
    page.goto("/login")
    expect(page.get_by_role("form", name="Form login", exact=True)).to_be_visible()
    assert (
        page.locator(".auth-card").evaluate("element => element.getAnimations().length")
        == 0
    )
    assert (
        page.locator(".auth-route-flow").evaluate(
            "element => element.getAnimations().length"
        )
        == 0
    )
    password = page.get_by_label("Password", exact=True)
    password.fill("keyboard visibility check")
    password.press("Tab")
    toggle = page.get_by_role("button", name="Tampilkan password", exact=True)
    expect(toggle).to_be_focused()
    toggle.press("Space")
    expect(password).to_have_attribute("type", "text")
    page.get_by_role("button", name="Sembunyikan password", exact=True).press("Enter")
    expect(password).to_have_attribute("type", "password")
