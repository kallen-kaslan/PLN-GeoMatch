"""Explicit interactions with the redesigned optional workspace panels."""

from playwright.sync_api import Page


def open_radius_controls(page: Page) -> None:
    if not page.get_by_label("Radius perluasan (meter)", exact=True).is_visible():
        page.get_by_text("Perluasan radius seluruh berkas", exact=True).click()
