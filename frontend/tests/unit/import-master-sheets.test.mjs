import assert from "node:assert/strict";
import test from "node:test";
import { importMasterSheets } from "../../src/lib/import-master-sheets.ts";

test("imports sheets sequentially with a separate mapping and result for each", async () => {
  const calls = [];
  const progress = [];
  const results = await importMasterSheets(["Mei", "Juni"], {
    prepare: async (sheet) => { calls.push(`prepare:${sheet}`); return { idpel: `${sheet}_ID` }; },
    upload: async (sheet) => { calls.push(`upload:${sheet}`); return { id: sheet === "Mei" ? 1 : 2, status: "needs_mapping" }; },
    confirm: async (id, mapping) => {
      await new Promise((resolve) => setImmediate(resolve));
      calls.push(`confirm:${id}:${mapping.idpel}`);
      return { batch_id: id, rows: 10, valid_rows: 9, error_rows: 1 };
    },
    progress: (event) => progress.push(event),
  });
  assert.deepEqual(calls, ["prepare:Mei", "upload:Mei", "confirm:1:Mei_ID", "prepare:Juni", "upload:Juni", "confirm:2:Juni_ID"]);
  assert.deepEqual(results.map((item) => item.batch_id), [1, 2]);
  assert.equal(progress.filter((item) => item.status === "completed").length, 2);
});

test("stops after an import failure, keeping completed sheets and leaving later sheets untouched", async () => {
  const confirmed = [];
  const prepared = [];
  const progress = [];
  await assert.rejects(importMasterSheets(["Mei", "Juni", "Juli"], {
    prepare: async (sheet) => { prepared.push(sheet); return { idpel: "IDPEL" }; },
    upload: async (sheet) => ({ id: sheet === "Mei" ? 1 : 2, status: "needs_mapping" }),
    confirm: async (id) => {
      if (id === 2) throw { message: "Penyimpanan gagal" };
      confirmed.push(id);
      return { batch_id: id, rows: 1, valid_rows: 1, error_rows: 0 };
    },
    progress: (event) => progress.push(event),
  }), /sheet "Juni": Penyimpanan gagal/);
  assert.deepEqual(confirmed, [1]);
  assert.deepEqual(prepared, ["Mei", "Juni"]);
  assert.equal(progress.at(-1).status, "failed");
});

test("rejects missing columns before importing a sheet", async () => {
  let uploaded = false;
  await assert.rejects(importMasterSheets(["Petunjuk"], {
    prepare: async () => { throw new Error("Kolom IDPEL tidak ditemukan"); },
    upload: async () => { uploaded = true; return { id: 1, status: "needs_mapping" }; },
    confirm: async () => assert.fail("Invalid sheet must not be confirmed"),
    progress: () => {},
  }), /Kolom IDPEL tidak ditemukan/);
  assert.equal(uploaded, false);
});

test("skips sheets completed by another request and ignores duplicate selections", async () => {
  let uploaded = 0;
  const progress = [];
  const results = await importMasterSheets(["Mei", "Mei"], {
    prepare: async () => ({ idpel: "IDPEL" }),
    upload: async () => { uploaded++; return { id: 1, status: "completed" }; },
    confirm: async () => assert.fail("Completed sheets must not be confirmed again"),
    progress: (event) => progress.push(event),
  });
  assert.equal(uploaded, 1);
  assert.deepEqual(results, []);
  assert.equal(progress.at(-1).status, "skipped");
});
