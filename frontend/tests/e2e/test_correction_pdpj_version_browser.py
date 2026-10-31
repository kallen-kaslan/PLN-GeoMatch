"""Start corrections on a new PDPJ publication while an old check is safely paused."""

import re

import httpx
import pytest
from playwright.sync_api import Page, expect
from test_corrections_browser import upload
from test_processing_progress_browser import captured


@pytest.mark.parametrize("kind", ["idpel_kosong", "idpel_tidak_ketemu"])
def test_switch_to_final_pdpj_while_old_correction_remains_paused(
    page: Page, servers: tuple[str, str], kind: str
) -> None:
    api = servers[1]
    with httpx.Client(base_url=api, timeout=20) as client:

        def post(path: str, body: dict | None = None) -> dict:
            response = client.post(path, json=body)
            response.raise_for_status()
            return response.json()

        upload(
            api,
            "dil",
            "IDPEL,LAT,LON\n001,-6.2,106.8\n002,-6.2,106.8\n003,-6.2,106.8\n004,-6.2,106.8\n",
        )
        pdpj = upload(api, "pdpj", "IDPEL,LAT,LON\n001,-6.2,106.8\n004,-6.2,106.8\n")
        review = post("/pdpj/reviews", {"batch_id": pdpj, "incremental": True})
        root = f"/pdpj/reviews/{review['id']}"
        review = post(
            root + "/advance", {"revision": review["revision"], "chunk_size": 1}
        )
        review = post(root + "/pause")
        published = post(
            root + "/complete", {"revision": review["revision"], "actor": "Petugas"}
        )["published_review"]
        assert published["publication"]["version"] == 1
        assert published["publication"]["row_count"] == 1

        target = upload(
            api,
            kind,
            "IDPEL,NAMA,LAT,LON\n"
            + "".join(
                f"{700 + i if kind == 'idpel_tidak_ketemu' else ''},Target {i},-6.2,106.8\n"
                for i in range(5)
            ),
        )
        check = post(
            f"/corrections/{kind}/checks",
            {
                "batch_id": target,
                "pdpj_review_id": published["id"],
                "radius_meters": 10,
                "actor": "Petugas",
                "request_key": "old_pdpj_version_check",
                "incremental": True,
            },
        )
        process = check["process_id"]
        base = f"/corrections/{kind}/checks/{process}"
        run = check["latest_run"]
        for _ in range(20):
            if run["processing"]["processed_rows"] >= 2:
                break
            run = post(
                base + "/advance",
                {
                    "run_id": run["id"],
                    "revision": run["processing"]["revision"],
                    "chunk_size": 2,
                },
            )
        assert run["processing"]["processed_rows"] == 2
        rows = client.get(
            f"/corrections/{kind}/records", params={"process_id": process}
        ).json()["items"]
        record = rows[0]["id"]
        candidate = client.get(
            f"/corrections/{kind}/records/{record}", params={"process_id": process}
        ).json()["candidates"][0]
        choice_path = base + f"/records/{record}/choice"
        choice = post(
            choice_path,
            {
                "generation": 1,
                "expected_revision": 0,
                "candidate_id": candidate["id"],
                "actor": "Petugas",
                "reason": "",
                "request_key": "old_pdpj_version_choice",
            },
        )

        review = post(root + "/resume")
        for _ in range(12):
            if review["processing"]["state"] == "ready":
                break
            review = post(
                root + "/advance", {"revision": review["revision"], "chunk_size": 2}
            )
        final = post(
            root + "/complete", {"revision": review["revision"], "actor": "Petugas"}
        )["published_review"]
        assert final["publication"]["version"] == 2
        assert final["publication"]["row_count"] == 2
        assert (
            final["id"] < published["id"]
        )  # Publication version is not the review ID.

        core_requests = []
        core_pattern = re.compile(rf"/corrections/{kind}/checks/{process}(?:\?.*)?$")
        page.route(core_pattern, lambda route: core_requests.append(route))
        selected_process = "" if kind == "idpel_kosong" else f"&process_id={process}"
        page.goto(
            f"/koreksi/{kind.replace('_', '-')}?batch_id={target}{selected_process}"
        )
        selector = page.get_by_label("PDPJ selesai divalidasi", exact=True)
        expect(
            page.get_by_text(
                "Memulihkan pemeriksaan dan progres tersimpan...", exact=True
            )
        ).to_be_visible()
        expect(selector).to_be_disabled()
        captured(page, core_requests)
        core = core_requests[-1]
        assert "include_update_conflicts=false" in core.request.url
        core.continue_()
        page.unroute(core_pattern)
        page.get_by_label("Petugas untuk riwayat", exact=True).fill(
            "Petugas Versi Baru"
        )
        expect(selector).to_have_value(str(published["id"]))
        expect(page).to_have_url(re.compile(rf"[?&]process_id={process}(?:&|$)"))
        expect(selector).to_be_disabled()
        expect(
            page.get_by_role("button", name="Pemeriksaan baru", exact=True)
        ).to_be_disabled()

        paused = post(base + "/pause", {"run_id": run["id"]})
        page.get_by_role("button", name="Muat ulang data koreksi", exact=True).click()
        expect(selector).to_be_enabled()
        expect(
            page.get_by_role("button", name="Pemeriksaan baru", exact=True)
        ).to_be_enabled()
        expect(
            page.get_by_role("button", name="Pemeriksaan dijeda", exact=True)
        ).to_be_disabled()
        expect(
            page.get_by_label("Radius pemeriksaan (meter)", exact=True)
        ).to_be_enabled()
        selector.select_option(str(final["id"]))
        page.get_by_label("Radius pemeriksaan (meter)", exact=True).fill("20")
        start = page.get_by_role("button", name="Jalankan pemeriksaan", exact=True)
        expect(start).to_be_enabled()
        # A paused process cannot be retried in-place with a new generation.
        retry = client.post(
            base + "/retry",
            json={
                "latest_run_id": run["id"],
                "radius_meters": 20,
                "actor": "Petugas",
                "request_key": "blocked_paused_retry",
                "incremental": True,
            },
        )
        assert retry.status_code == 409

        # Refresh preserves the draft without changing the old source or checkpoint.
        background = []
        page.route("**/pdpj-update", lambda route: background.append(route))
        posts_after_refresh = []
        page.on(
            "request",
            lambda request: (
                posts_after_refresh.append(request.url)
                if request.method == "POST"
                else None
            ),
        )
        page.reload()
        expect(selector).to_be_enabled()
        expect(selector).to_have_value(str(final["id"]))
        expect(page.get_by_label("Petugas untuk riwayat", exact=True)).to_have_value(
            "Petugas Versi Baru"
        )
        expect(
            page.get_by_label("Radius pemeriksaan (meter)", exact=True)
        ).to_have_value("20")
        expect(
            page.get_by_role("region", name="Progres pemeriksaan koreksi", exact=True)
        ).to_contain_text("Proses dijeda")
        expect(
            page.get_by_text(
                "Memeriksa benturan pilihan dengan PDPJ terbaru. Progres pemeriksaan tetap tersedia.",
                exact=True,
            )
        ).to_be_visible()
        expect(start).to_be_enabled()
        assert posts_after_refresh == []
        captured(page, background).abort()
        page.unroute("**/pdpj-update")
        expect(
            page.get_by_role(
                "button", name="Coba lagi pemeriksaan benturan", exact=True
            )
        ).to_be_visible()
        expect(start).to_be_enabled()
        with page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.endswith(f"/corrections/{kind}/checks")
            )
        ) as created:
            start.click()
        assert created.value.status == 200
        fresh = created.value.json()
        assert fresh["process_id"] != process
        assert fresh["pdpj_review_id"] == final["id"]
        assert fresh["latest_run"]["radius_meters"] == 20
        expect(page).to_have_url(
            f"{servers[0]}/koreksi/{kind.replace('_', '-')}?batch_id={target}&process_id={fresh['process_id']}"
        )
        dialog = page.get_by_role(
            "dialog", name="Pemeriksaan koreksi selesai", exact=True
        )
        expect(dialog).to_be_visible(timeout=20000)
        dialog.get_by_role("button", name="Lihat hasil pemeriksaan", exact=True).click()
        expect(selector).to_have_value(str(final["id"]))

        old = client.get(base).json()
        assert old["pdpj_review_id"] == published["id"]
        assert old["latest_run"]["id"] == run["id"]
        assert old["latest_run"]["processing"] == paused["processing"]
        assert client.get(choice_path).json() == choice
        new = client.get(f"/corrections/{kind}/checks/{fresh['process_id']}").json()
        assert new["latest_run"]["status"] == "completed"
        assert new["pdpj_review_id"] == final["id"]
