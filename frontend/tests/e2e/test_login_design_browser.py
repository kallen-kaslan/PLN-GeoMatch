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
        {"width": 412, "height": 915},
        {"width": 390, "height": 420},
        {"width": 844, "height": 390},
        {"width": 768, "height": 1024},
    ],
)
def test_login_logo_intro_responsive_layout_password_visibility_and_sign_in(
    page, viewport
):
    page.set_viewport_size(viewport)
    page.context.clear_cookies()
    page.goto("/login")
    form = page.get_by_role("form", name="Form login", exact=True)
    expect(form).to_be_visible(timeout=10000)
    expect(page.get_by_role("heading", name="Masuk", exact=True)).to_be_visible()
    logo = page.get_by_role("img", name="Logo PLN", exact=True)
    assert logo.evaluate("element => element.complete && element.naturalWidth > 0")
    # Screenshots are local review artifacts, never uploaded or used as app data.
    folder = ROOT / ".runtime" / "login-design-preview"
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(folder / f"login-{viewport['width']}x{viewport['height']}.png"), animations="disabled"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    brand = page.locator(".auth-brand").bounding_box()
    panel = page.locator(".auth-form-panel").bounding_box()
    assert brand and panel
    if viewport["width"] >= 900:
        assert brand["x"] + brand["width"] <= panel["x"] + 1
        assert abs(brand["y"] - panel["y"]) <= 1
    else:
        fullscreen = viewport["width"] <= 639 or viewport["height"] <= 500
        card = page.locator(".auth-card").bounding_box()
        assert card
        if fullscreen:
            assert abs(card["x"]) <= 1 and abs(card["y"]) <= 1
            assert abs(card["width"] - viewport["width"]) <= 1
            assert card["height"] >= viewport["height"]
            assert panel["y"] >= brand["y"] + brand["height"] - 24
            assert panel["y"] < brand["y"] + brand["height"]
            submit_box = form.get_by_role("button", name="Masuk", exact=True).bounding_box()
            help_box = page.locator(".auth-help").bounding_box()
            assert submit_box and help_box
            assert 0 <= help_box["y"] - submit_box["y"] - submit_box["height"] <= 32
        else:
            assert card["x"] > 0 and card["width"] < viewport["width"]
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
    expect(page.get_by_role("form", name="Form login", exact=True)).to_be_visible(timeout=10000)
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


def test_startup_zoom_settles_into_orbit_and_waits_for_the_real_session(page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.context.clear_cookies()
    pending = []
    page.route("**/auth/me", lambda route: pending.append(route))
    page.goto("/login")
    splash = page.get_by_role("main", name="Memuat PLN GeoMatch", exact=True)
    expect(splash).to_be_visible()
    mark = splash.locator(".auth-splash-mark")
    # Sample the actual motion: a close logo settles before its ring rotates.
    page.wait_for_timeout(240)
    close = mark.bounding_box()
    assert close and close["width"] > 140
    folder = ROOT / ".runtime" / "login-design-preview"
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / "startup-zoom.png"))
    page.wait_for_function("""() => {
      const mark = document.querySelector('.app-entrance-overlay .auth-splash-mark');
      return mark && Math.abs(mark.getBoundingClientRect().width - 96) < 1
        && Number(getComputedStyle(mark, '::after').opacity) > .9;
    }""")
    first = mark.evaluate("el => getComputedStyle(el, '::after').transform")
    page.wait_for_timeout(300)
    second = mark.evaluate("el => getComputedStyle(el, '::after').transform")
    assert first != second
    page.screenshot(path=str(folder / "startup-orbit.png"))
    expect(page.get_by_role("form", name="Form login", exact=True)).to_have_count(0)
    assert pending
    for request in pending:
        request.continue_()
    expect(page.get_by_role("form", name="Form login", exact=True)).to_be_visible(timeout=10000)
    expect(splash).to_have_count(0)
    assert page.locator(".app-entrance-content").get_attribute("inert") is None
