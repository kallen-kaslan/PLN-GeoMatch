import { usePermissions } from "@/hooks/usePermissions";
import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, MapPin, Save } from "lucide-react";
import { unparse } from "papaparse";
import { api, type ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { CORRECTION_TYPES } from "@/lib/corrections";
import type { ImportResult } from "@/lib/master";
import { useAppStore } from "@/store/app";

const control = "w-full rounded-lg border border-ui-border bg-white px-3 py-2 text-sm";

function coordinate(value: string, limit: number, label: string): string {
  const text = value.trim().replace(",", ".");
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text) || Math.abs(Number(text)) > limit) {
    throw new Error(label + " harus berupa angka antara -" + limit + " dan " + limit + ".");
  }
  return text;
}

export default function ProcessPage() {
  const user = useAppStore((state) => state.user);
  const canOperate = user?.role === "admin" || user?.role === "analis";
  const navigate = useNavigate();
  const { canWrite } = usePermissions();
  const queryClient = useQueryClient();
  const [sessionName, setSessionName] = useState("");
  const [reference, setReference] = useState("");
  const [idpel, setIdpel] = useState("");
  const [agenda, setAgenda] = useState("");
  const [meter, setMeter] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [radius, setRadius] = useState("150");
  const [stage, setStage] = useState<string | null>(null);
  const [error, setError] = useState("");
  const pending = useRef(false);
  // Reuse the uploaded row when mapping fails, rather than uploading it again.
  const uploaded = useRef<{ content: string; filename: string; batchId: number } | null>(null);
  const descriptor = CORRECTION_TYPES.find((item) => item.key === (idpel.trim() ? "idpel_tidak_ketemu" : "idpel_kosong"))!;

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending.current) return;
    pending.current = true;
    setError("");
    try {
      if (!sessionName.trim() || !reference.trim()) throw new Error("Isi nama sesi dan referensi titik.");
      const lat = coordinate(latitude, 90, "Latitude (Y)");
      const lon = coordinate(longitude, 180, "Longitude (X)");
      const radiusMeters = Number(radius);
      if (!radius.trim() || !Number.isFinite(radiusMeters) || radiusMeters <= 0 || radiusMeters > 100000) {
        throw new Error("Radius harus lebih dari 0 dan paling besar 100.000 meter.");
      }
      const content = unparse([
        ["IDPEL", "ID_TITIK", "NOAGENDA", "NOMOR_METER", "LATITUDEY", "LONGITUDEX", "KETERANGAN"],
        [idpel.trim(), reference.trim(), agenda.trim(), meter.trim(), lat, lon, sessionName.trim()],
      ]);
      const filename = "manual-" + sessionName.trim().replace(/[^\p{L}\p{N}_-]/gu, "_").slice(0, 80) + ".csv";
      setStage("Menyimpan titik manual ke Data Koreksi...");
      if (uploaded.current?.content !== content || uploaded.current.filename !== filename) {
        const form = new FormData();
        form.append("file", new Blob([content], { type: "text/csv;charset=utf-8" }), filename);
        form.append("dataset_type", descriptor.key);
        const response = await api.post<{ id: number }>("/upload/", form, { headers: { "Content-Type": "multipart/form-data" } });
        uploaded.current = { content, filename, batchId: response.data.id };
      }
      const batchId = uploaded.current.batchId;
      setStage("Memvalidasi identitas dan koordinat titik...");
      const response = await api.post<ImportResult>("/upload/confirm-mapping", {
        batch_id: batchId,
        column_mapping: {
          idpel: "IDPEL", survey_ref: "ID_TITIK", agenda_ref: "NOAGENDA", meter_ref: "NOMOR_METER",
          lat: "LATITUDEY", lon: "LONGITUDEX",
        },
      });
      if (response.data.error_rows || response.data.rows !== 1) {
        throw new Error("Data titik belum valid. Periksa identitas dan koordinat, lalu simpan kembali.");
      }
      await queryClient.invalidateQueries({ queryKey: ["corrections", descriptor.key] });
      const params = new URLSearchParams({ batch_id: String(batchId), radius_meters: String(radiusMeters) });
      navigate("/koreksi/" + descriptor.slug + "?" + params);
    } catch (err) {
      setError((err as ApiError | Error).message || "Gagal menyimpan titik manual. Silakan coba kembali.");
    } finally {
      pending.current = false;
      setStage(null);
    }
  };

  if (!canWrite) return <div role="alert" className="geo-panel space-y-3 p-6"><h1 className="text-xl font-semibold">Akses Ditolak</h1><p>Input manual dan matching hanya tersedia untuk admin dan analis. Auditor dapat melihat data dan mengunduh hasil.</p><Link to="/result" className={buttonClass.secondary}>Lihat hasil</Link></div>;

  return <div className="space-y-5">
    <div className="space-y-2 border-b border-ui-border pb-4">
      <h1 className="flex items-center gap-2 text-xl font-semibold"><MapPin size={22} />Input Manual & Matching</h1>
      <p className="text-sm text-ui-muted">Masukkan satu titik lapangan, lalu periksa melalui Data Koreksi, pilih kandidat di Peta Koreksi, dan unduh Hasil Koreksi.</p>
    </div>
    <div className="mx-auto flex w-full max-w-5xl flex-wrap gap-2 text-sm">
      {CORRECTION_TYPES.map((item) => <Link key={item.key} to={"/koreksi/" + item.slug} className={buttonClass.secondary}>Gunakan berkas {item.label}</Link>)}
    </div>
    <form onSubmit={save} className="mx-auto w-full max-w-5xl space-y-4 rounded-lg border border-ui-border bg-white p-4 sm:p-6 lg:p-8" aria-label="Input manual satu titik">
      <fieldset disabled={stage !== null} className="min-w-0 space-y-4 disabled:opacity-70">
        <legend className="mb-4 font-semibold">Input Manual 1 Titik Koordinat</legend>
        <div className="grid gap-4 md:grid-cols-2">
        <label className="block space-y-1 text-sm font-semibold"><span>Nama sesi</span><input required maxLength={120} value={sessionName} onChange={(event) => setSessionName(event.target.value)} className={control} placeholder="Contoh: Survei Gardu A" /></label>
        <label className="block space-y-1 text-sm font-semibold"><span>Referensi survei / ID titik</span><input required maxLength={120} value={reference} onChange={(event) => setReference(event.target.value)} className={control} placeholder="Contoh: TIANG-001" /></label>
        <label className="block space-y-1 text-sm font-semibold"><span>IDPEL awal (opsional)</span><input value={idpel} onChange={(event) => setIdpel(event.target.value)} maxLength={64} className={control} placeholder="Kosongkan jika belum diketahui" /></label>
        <label className="block space-y-1 text-sm font-semibold"><span>Radius pemeriksaan (meter)</span><input required type="number" min="0.01" max="100000" step="any" value={radius} onChange={(event) => setRadius(event.target.value)} className={control} /></label>
        </div>
        <p role="status" className="text-xs text-ui-muted">Titik akan disimpan pada kategori <strong>{descriptor.label}</strong>. Referensi titik disimpan sebagai referensi survei.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-1 text-sm font-semibold"><span>Nomor agenda (opsional)</span><input value={agenda} onChange={(event) => setAgenda(event.target.value)} maxLength={120} className={control} /></label>
          <label className="block space-y-1 text-sm font-semibold"><span>Nomor meter (opsional)</span><input value={meter} onChange={(event) => setMeter(event.target.value)} maxLength={120} className={control} /></label>
          <label className="block space-y-1 text-sm font-semibold"><span>Latitude (Y)</span><input required inputMode="decimal" value={latitude} onChange={(event) => setLatitude(event.target.value)} className={control} placeholder="Contoh: -6.20890" /></label>
          <label className="block space-y-1 text-sm font-semibold"><span>Longitude (X)</span><input required inputMode="decimal" value={longitude} onChange={(event) => setLongitude(event.target.value)} className={control} placeholder="Contoh: 106.84570" /></label>
        </div>
        <p className="text-sm text-ui-muted">Setelah disimpan, pilih versi PDPJ yang selesai divalidasi dan isi nama petugas di Data Koreksi, lalu jalankan pemeriksaan. Semua kandidat dalam radius dapat ditinjau.</p>
        {canOperate ? (
          <button type="submit" className={buttonClass.primary}>{stage ? <LoaderCircle size={16} className="animate-spin" /> : <Save size={16} />}Simpan & Buka Data Koreksi</button>
        ) : (
          <div className="p-3 text-center rounded-lg border border-ui-border bg-gray-50 text-xs text-ui-muted">
            Akun auditor memiliki akses lihat data saja. Penyimpanan titik manual hanya dapat dijalankan oleh admin dan analis.
          </div>
        )}
      </fieldset>
      {stage && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />{stage}</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </form>
  </div>;
}
