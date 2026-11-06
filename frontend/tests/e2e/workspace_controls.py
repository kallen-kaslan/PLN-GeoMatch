"""Explicit interactions with the redesigned optional workspace panels."""

from playwright.sync_api import Page


def open_map_options(page: Page) -> None:
    options = page.get_by_label("Riwayat dan opsi peta", exact=True)
    if options.get_attribute("open") is None:
        options.locator(":scope > summary").click()


def open_radius_controls(page: Page) -> None:
    open_map_options(page)
    if not page.get_by_label("Radius perluasan (meter)", exact=True).is_visible():
        page.get_by_text("Perluasan radius seluruh berkas", exact=True).click()


def sign_in_map(page: Page, username: str) -> None:
    """Use the existing mock account store; do not fabricate an actor field."""
    page.evaluate("""async username => {
      const { useAppStore } = await import('/src/store/app.ts');
      useAppStore.getState().setUser({id: 'browser-account', username, role: 'analis'});
    }""", username)


def apply_map_radius(page: Page, value: str) -> None:
    page.get_by_label("Radius peta (meter)", exact=True).fill(value)
    button = page.get_by_role("button", name="Terapkan Radius", exact=True)
    if button.is_enabled():
        button.click()
