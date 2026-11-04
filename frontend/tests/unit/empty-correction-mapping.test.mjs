import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import test from "node:test";

// Exercise the actual mapping module without a browser, API calls, or build files.
const source = readFileSync(new URL("../../src/lib/master.ts", import.meta.url), "utf8")
  .replace('import { api } from "@/lib/api";', "const api = {};");
const { guessMasterMapping, masterFields } = await import(`data:text/javascript;base64,${Buffer.from(stripTypeScriptTypes(source)).toString("base64")}`);

test("empty-ID upload recognizes the source columns without requiring IDPEL", () => {
  const mapping = guessMasterMapping([
    "noagenda", "idpelanggan", "jenispelanggan", "namapelanggan",
    "alamatlengkap", "nokwhmeter", "daya", "latitudey", "longitude",
  ], "idpel_kosong");
  assert.equal(mapping.agenda_ref, "noagenda");
  assert.equal(mapping.idpel, "idpelanggan");
  assert.equal(mapping.jenis_pel, "jenispelanggan");
  assert.equal(mapping.nama, "namapelanggan");
  assert.equal(mapping.alamat, "alamatlengkap");
  assert.equal(mapping.nomor_meter_kwh, "nokwhmeter");
  assert.equal(mapping.daya, "daya");
  assert.equal(mapping.lat, "latitudey");
  assert.equal(mapping.lon, "longitude");
  assert.equal(masterFields("idpel_kosong").some((field) => field.required), false);
  assert.equal(masterFields("idpel_tidak_ketemu").find((field) => field.key === "idpel").required, true);
});

test("renamed X/Y headers retain both coordinate orientations", () => {
  const headers = ["KOORDINAT_X", "Koordinat Y"];
  const standard = guessMasterMapping(headers, "idpel_kosong", [{ KOORDINAT_X: "108.5", "Koordinat Y": "-6.2" }]);
  assert.equal(standard.lon, "KOORDINAT_X");
  assert.equal(standard.lat, "Koordinat Y");
  const reversed = guessMasterMapping(headers, "idpel_kosong", [{ KOORDINAT_X: "-6.2", "Koordinat Y": "108.5" }]);
  assert.equal(reversed.lat, "KOORDINAT_X");
  assert.equal(reversed.lon, "Koordinat Y");
});
