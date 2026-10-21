import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Papa from "papaparse";
import * as XLSX from "xlsx";
import { api } from "@/lib/api";

type DatasetType = "pascabayar" | "prabayar" | "pdpj" | "koordinat_kosong";

interface RequiredField {
  key: string;
  label: string;
  aliases: string[];
}


const DATASET_CONFIG: Record<DatasetType, { title: string; desc: string; fields: RequiredField[] }> = {
  pascabayar: {
    title: "1. Data Pascabayar (ACMT / RBM)",
    desc: "Data histori pencatatan meter pascabayar multi-bulan. Sistem akan membersihkan data bertumpuk.",
    fields: [
      { key: "idpel", label: "ID Pelanggan (IDPEL)", aliases: ["idpel", "idpelanggan", "nopelanggan", "id_pelanggan"] },
      { key: "lat", label: "Latitude (Y)", aliases: ["latitudey", "latitude", "lat", "lintang", "y"] },
      { key: "lon", label: "Longitude (X)", aliases: ["longitudex", "longitude", "long", "lon", "bujur", "x"] },
      { key: "tglbaca", label: "Tanggal Baca / Periode", aliases: ["tglbaca", "tanggalbaca", "periode", "bulan"] },
    ],
  },
  prabayar: {
    title: "2. Data Prabayar (LPB)",
    desc: "Data transaksi meter prabayar multi-bulan. Akan digabung bersama Pascabayar menjadi Master.",
    fields: [
      { key: "idpel", label: "ID Pelanggan (IDPEL)", aliases: ["idpel", "idpelanggan", "nopelanggan", "id_pelanggan"] },
      { key: "lat", label: "Latitude (Y)", aliases: ["latitudey", "latitude", "lat", "lintang", "y"] },
      { key: "lon", label: "Longitude (X)", aliases: ["longitudex", "longitude", "long", "lon", "bujur", "x"] },
      { key: "tglbaca", label: "Tanggal Baca / Periode", aliases: ["tglbaca", "tanggalbaca", "periode", "bulan"] },
    ],
  },
  pdpj: {
    title: "3. Data PDPJ (Sudah Verif)",
    desc: "Data yang sudah terverifikasi di lapangan. IDPEL pada data ini akan DIKECUALIKAN dari Master.",
    fields: [
      { key: "idpelanggan", label: "ID Pelanggan (PDPJ)", aliases: ["idpelanggan", "idpel", "nopelanggan"] },
      { key: "verif", label: "Status Verifikasi", aliases: ["verif", "statusverif", "status", "status_bayar"] },
      { key: "latitudey", label: "Latitude Y (Opsional)", aliases: ["latitudey", "latitude", "lat", "y"] },
      { key: "longitudex", label: "Longitude X (Opsional)", aliases: ["longitudex", "longitude", "long", "x"] },
    ],
  },
  koordinat_kosong: {
    title: "4. Koordinat Kosong (Target Tanpa IDPEL)",
    desc: "Data tiang/meteran yang IDPEL-nya kosong atau tidak ditemukan. Akan dicocokkan ke Master Sisa.",
    fields: [
      { key: "nomor_meter", label: "Nomor Meter / Referensi Titik", aliases: ["nomormeter", "nomor_meter", "id_titik", "ref"] },
      { key: "lat", label: "Latitude (Y)", aliases: ["latitudey", "latitude", "lat", "lintang", "y"] },
      { key: "lon", label: "Longitude (X)", aliases: ["longitudex", "longitude", "long", "lon", "bujur", "x"] },
    ],
  },
};

const DUMMY_SAMPLES: Record<DatasetType, Record<string, string | number>[]> = {
  pascabayar: [
    { IDPELANGGAN: "531234567890", LATITUDEY: -6.20888, LONGITUDEX: 106.84568, TGLBACA: "2026-01-15", JENISPENGGUNAAN: "PASCABAYAR", NAMA_PELANGGAN: "Budi Santoso", KODE_GARDU: "GRD-01" },
    { IDPELANGGAN: "531234567890", LATITUDEY: -6.20889, LONGITUDEX: 106.84569, TGLBACA: "2026-02-15", JENISPENGGUNAAN: "PASCABAYAR", NAMA_PELANGGAN: "Budi Santoso (Update Bulan 2)", KODE_GARDU: "GRD-01" },
    { IDPELANGGAN: "531234567891", LATITUDEY: -6.20900, LONGITUDEX: 106.84600, TGLBACA: "2026-02-10", JENISPENGGUNAAN: "PASCABAYAR", NAMA_PELANGGAN: "Siti Aminah", KODE_GARDU: "GRD-01" },
  ],
  prabayar: [
    { IDPELANGGAN: "531234567892", LATITUDEY: -6.21008, LONGITUDEX: 106.84708, TGLBACA: "2026-01-20", JENISPENGGUNAAN: "PRABAYAR", NAMA_PELANGGAN: "Joko Widodo", KODE_GARDU: "GRD-01" },
    { IDPELANGGAN: "531234567892", LATITUDEY: -6.21009, LONGITUDEX: 106.84709, TGLBACA: "2026-02-20", JENISPENGGUNAAN: "PRABAYAR", NAMA_PELANGGAN: "Joko Widodo (Update Bulan 2)", KODE_GARDU: "GRD-01" },
    { IDPELANGGAN: "531234567893", LATITUDEY: -6.21500, LONGITUDEX: 106.85000, TGLBACA: "2026-02-14", JENISPENGGUNAAN: "PRABAYAR", NAMA_PELANGGAN: "Dewi Lestari", KODE_GARDU: "GRD-02" },
  ],
  pdpj: [
    { NOAGENDA: "AGD-2026-001", IDPELANGGAN: "531234567891", VERIF: "1", JENISPELANGGAN: "PASCABAYAR", LATITUDEY: -6.20900, LONGITUDEX: 106.84600 },
    { NOAGENDA: "AGD-2026-002", IDPELANGGAN: "531234567894", VERIF: "1", JENISPELANGGAN: "PASCABAYAR", LATITUDEY: -6.22000, LONGITUDEX: 106.85500 },
  ],
  koordinat_kosong: [
    { NOMOR_METER: "MTR-KOSONG-001", LATITUDEY: -6.20890, LONGITUDEX: 106.84570, KETERANGAN: "Tiang depan pagar - IDPEL tidak ditemukan" },
    { NOMOR_METER: "MTR-KOSONG-002", LATITUDEY: -6.21010, LONGITUDEX: 106.84710, KETERANGAN: "Dekat gardu trafo - Rumah baru belum ada IDPEL" },
    { NOMOR_METER: "MTR-KOSONG-003", LATITUDEY: -6.99990, LONGITUDEX: 110.00000, KETERANGAN: "Koordinat jauh / Anomali pencatatan" },
  ],
};

interface DatasetUploadState {
  status: "empty" | "uploaded" | "reviewing" | "locked" | "rejected";
  file?: File;
  headers: string[];
  previewRows: Record<string, any>[];
  mapping: Record<string, string>;
  batchId?: number;
  totalRows?: number;
  validRows?: number;
}

export default function UploadPage() {
  const navigate = useNavigate();

  // Multi-dataset state untuk 4 jenis dataset
  const [datasetStates, setDatasetStates] = useState<Record<DatasetType, DatasetUploadState>>({
    pascabayar: { status: "empty", headers: [], previewRows: [], mapping: {} },
    prabayar: { status: "empty", headers: [], previewRows: [], mapping: {} },
    pdpj: { status: "empty", headers: [], previewRows: [], mapping: {} },
    koordinat_kosong: { status: "empty", headers: [], previewRows: [], mapping: {} },
  });

  const [currentDataset, setCurrentDataset] = useState<DatasetType>("pascabayar");
  const [loading, setLoading] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<string | null>(null);

  // Batch processing state
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [batchProgress, setBatchProgress] = useState("");

  // Lazy Loading Animation Pipeline State
  const [pipelineActive, setPipelineActive] = useState(false);
  const [pipelineTitle, setPipelineTitle] = useState("Memproses & Mencocokkan Data...");
  const [pipelineStepIndex, setPipelineStepIndex] = useState(0);
  const pipelineSteps = [
    { title: "1. Upload & Parsing Berkas", desc: "Membaca baris data dan memvalidasi kolom spasial" },
    { title: "2. Cleaning & Pembentukan Master", desc: "Deduplikasi multi-bulan ACMT & LPB berdasarkan tanggal baca" },
    { title: "3. Pengecualian Data PDPJ", desc: "Menyaring IDPEL yang sudah terverifikasi sebelumnya" },
    { title: "4. Spatial Haversine Matching Engine", desc: "Mencocokkan koordinat kosong dengan Master Sisa dalam radius" },
    { title: "5. Menyiapkan Peta Spasial & GMaps", desc: "Mengalihkan ke halaman Review & Peta Interaktif..." },
  ];

  const autoFilterColumns = (fileHeaders: string[], type: DatasetType) => {
    const initialMapping: Record<string, string> = {};
    DATASET_CONFIG[type].fields.forEach((field) => {
      const match = fileHeaders.find((header) => {
        const clean = header.trim().toLowerCase().replace(/[_\s-]/g, "");
        return field.aliases.some((alias) => clean === alias || clean.includes(alias));
      });
      if (match) initialMapping[field.key] = match;
    });
    return initialMapping;
  };

  const updateDataset = (type: DatasetType, update: Partial<DatasetUploadState>) => {
    setDatasetStates((current) => ({
      ...current,
      [type]: { ...current[type], ...update },
    }));
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    const type = currentDataset;
    if (datasetStates[type].status === "locked") return;
    setErrorMessage(null);
    setSuccessInfo(null);

    const onParsed = (fileHeaders: string[], rows: Record<string, any>[]) => {
      updateDataset(type, {
        status: "reviewing",
        file: selectedFile,
        headers: fileHeaders,
        previewRows: rows,
        mapping: autoFilterColumns(fileHeaders, type),
        batchId: undefined,
      });
    };

    const ext = selectedFile.name.split(".").pop()?.toLowerCase();
    if (ext === "csv") {
      Papa.parse(selectedFile, {
        header: true,
        preview: 5,
        complete: (results) => {
          if (results.meta.fields) onParsed(results.meta.fields, results.data as Record<string, any>[]);
          else setErrorMessage("Header CSV tidak ditemukan.");
        },
        error: (error) => setErrorMessage(error.message),
      });
    } else if (ext === "xlsx" || ext === "xls") {
      const reader = new FileReader();
      reader.onerror = () => setErrorMessage("Gagal membaca file Excel.");
      reader.onload = (evt) => {
        try {
          const wb = XLSX.read(evt.target?.result, { type: "binary" });
          const ws = wb.Sheets[wb.SheetNames[0]];
          const data = XLSX.utils.sheet_to_json<unknown[]>(ws, { header: 1 });
          if (!data.length) throw new Error("File Excel kosong.");
          const fileHeaders = data[0].map(String);
          const rows = data.slice(1, 6).map((row) => {
            const obj: Record<string, any> = {};
            fileHeaders.forEach((header, index) => { obj[header] = row[index]; });
            return obj;
          });
          onParsed(fileHeaders, rows);
        } catch (error: any) {
          setErrorMessage(error.message || "Gagal membaca file Excel.");
        }
      };
      reader.readAsBinaryString(selectedFile);
    } else {
      setErrorMessage("Format file harus CSV atau Excel.");
    }
    e.target.value = "";
  };

  const handleLoadDummyToForm = () => {
    const sample = DUMMY_SAMPLES[currentDataset];
    const dummyHeaders = Object.keys(sample[0]);
    updateDataset(currentDataset, {
      status: "reviewing",
      file: new File([Papa.unparse(sample)], `${currentDataset}_sample.csv`, { type: "text/csv" }),
      headers: dummyHeaders,
      previewRows: sample,
      mapping: autoFilterColumns(dummyHeaders, currentDataset),
      batchId: undefined,
    });
    setErrorMessage(null);
    setSuccessInfo(`Data contoh [${DATASET_CONFIG[currentDataset].title}] dimuat.`);
  };

  const handleLockDataset = async () => {
    const state = datasetStates[currentDataset];
    if (!state.file || !state.headers.length) return;
    const missingFields = DATASET_CONFIG[currentDataset].fields.filter((field) => !state.mapping[field.key]);
    if (missingFields.length) {
      setErrorMessage(`Pemetaan kolom belum lengkap: ${missingFields.map((field) => field.label).join(", ")}`);
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const formData = new FormData();
      formData.append("file", state.file);
      formData.append("dataset_type", currentDataset);
      const uploadRes = await api.post("/upload/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const batchId = Number(uploadRes.data.id);
      if (!Number.isFinite(batchId)) throw new Error("ID batch upload tidak valid.");
      await api.post("/upload/confirm-mapping", {
        batch_id: batchId,
        column_mapping: state.mapping,
      });
      updateDataset(currentDataset, { status: "locked", batchId });
      setSuccessInfo(`${DATASET_CONFIG[currentDataset].title} berhasil di-keep dan dikunci.`);
    } catch (error: any) {
      setErrorMessage(error.response?.data?.detail || error.message || "Gagal upload dan mengunci dataset.");
    } finally {
      setLoading(false);
    }
  };

  const handleBatchProcess = async () => {
    const locked = datasetStates;
    const hasSources = locked.pascabayar.status === "locked" || locked.prabayar.status === "locked";
    if (!hasSources) {
      setErrorMessage("Kunci minimal satu dataset sumber: Pascabayar atau Prabayar.");
      return;
    }
    if (locked.koordinat_kosong.status !== "locked") {
      setErrorMessage("Kunci dataset Koordinat Kosong sebelum memulai matching.");
      return;
    }

    setBatchProcessing(true);
    setBatchProgress("Membentuk master dan memproses dataset terkunci...");
    setPipelineActive(true);
    setPipelineTitle("Membentuk master dan memproses dataset...");
    setPipelineStepIndex(0);
    setErrorMessage(null);
    try {
      const processing = api.post("/upload/batch-process", {
        pascabayar_batch_id: locked.pascabayar.batchId ?? null,
        prabayar_batch_id: locked.prabayar.batchId ?? null,
        pdpj_batch_id: locked.pdpj.batchId ?? null,
        target_batch_id: locked.koordinat_kosong.batchId,
      });
      let processingFinished = false;
      processing.then(
        () => { processingFinished = true; },
        () => { processingFinished = true; },
      );
      for (let step = 0; step < pipelineSteps.length - 1 && !processingFinished; step++) {
        setPipelineStepIndex(step);
        await new Promise((resolve) => setTimeout(resolve, 900));
      }
      const response = await processing;
      const id = Number(response.data.process_id);
      if (!Number.isFinite(id)) throw new Error("Server tidak mengembalikan process_id yang valid.");
      setPipelineStepIndex(pipelineSteps.length - 1);
      setBatchProgress("Pemrosesan selesai. Membuka halaman review...");
      setTimeout(() => navigate(`/candidates?process_id=${id}`), 500);
    } catch (error: any) {
      setErrorMessage(error.response?.data?.detail || error.message || "Gagal memproses dataset.");
      setBatchProcessing(false);
      setPipelineActive(false);
    }
  };

  // Helper fungsi untuk animasi langkah lazy loading
  const runStepAnimation = async (startStep: number, targetStep: number, delayMs: number = 400) => {
    for (let i = startStep; i <= targetStep; i++) {
      setPipelineStepIndex(i);
      await new Promise((r) => setTimeout(r, delayMs));
    }
  };

  // 1-Click Alur Lengkap PLN (Pascabayar + Prabayar -> Master -> Exclude PDPJ -> Match Koordinat Kosong)
  const handleAutoSeedPLN = async () => {
    setPipelineActive(true);
    setPipelineTitle("Menjalankan Alur Lengkap PLN GeoMatch...");
    setPipelineStepIndex(0);
    setErrorMessage(null);
    setSuccessInfo(null);

    try {
      await runStepAnimation(0, 1, 350);
      const seedPromise = api.post("/upload/seed-dummy");
      await runStepAnimation(1, 2, 400);
      await runStepAnimation(2, 3, 400);

      const res = await seedPromise;
      const pid = res.data.process_id || 1;

      await runStepAnimation(3, 4, 350);

      setSuccessInfo(
        `Alur PLN Selesai: Master dibentuk (${res.data.master_cleaning_summary?.total_master_clean} pelanggan), PDPJ diexclude, & Koordinat Kosong dicocokkan! Mengalihkan ke Review...`
      );

      setTimeout(() => {
        navigate(`/candidates?process_id=${pid}`);
      }, 700);
    } catch (err: any) {
      setErrorMessage(err.message || "Gagal menjalankan alur PLN otomatis.");
      setPipelineActive(false);
    }
  };

  const handleResetDatabase = async () => {
    if (!window.confirm("Kosongkan semua data di database?")) return;
    setResetting(true);
    setErrorMessage(null);
    try {
      const res = await api.post("/upload/reset");
      setDatasetStates({
        pascabayar: { status: "empty", headers: [], previewRows: [], mapping: {} },
        prabayar: { status: "empty", headers: [], previewRows: [], mapping: {} },
        pdpj: { status: "empty", headers: [], previewRows: [], mapping: {} },
        koordinat_kosong: { status: "empty", headers: [], previewRows: [], mapping: {} },
      });
      setSuccessInfo(res.data.message);
    } catch (error: any) {
      setErrorMessage(error.response?.data?.detail || error.message || "Gagal reset.");
    } finally {
      setResetting(false);
    }
  };

  const currentState = datasetStates[currentDataset];
  const currentConfig = DATASET_CONFIG[currentDataset];
  const lockedCount = Object.values(datasetStates).filter((state) => state.status === "locked").length;

  return (
    <div className="space-y-6 relative">
      {/* Overlay Animasi Lazy Loading Menyeluruh */}
      {pipelineActive && (
        <div className="fixed inset-0 z-50 bg-neo-black/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border-2 border-neo-black rounded-sm p-6 max-w-lg w-full shadow-[8px_8px_0_#ff6b35] space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3 border-b-2 border-neo-black pb-3">
              <div className="w-6 h-6 border-3 border-neo-accent border-t-transparent rounded-full animate-spin"></div>
              <div>
                <h3 className="text-base font-black text-neo-black">{pipelineTitle}</h3>
                <p className="text-xs text-neo-border">Otomatis memproses, mencocokkan, dan membuka Peta Spasial...</p>
              </div>
            </div>

            {/* Stepper Progress Bar */}
            <div className="space-y-3">
              {pipelineSteps.map((step, idx) => {
                const isDone = idx < pipelineStepIndex;
                const isCurrent = idx === pipelineStepIndex;
                return (
                  <div
                    key={step.title}
                    className={`p-3 border rounded-sm transition-all duration-300 flex items-start gap-3 ${
                      isDone
                        ? "border-[#16a34a] bg-[#dcfce7] shadow-[0_2px_0_#16a34a]"
                        : isCurrent
                        ? "border-neo-black bg-[#fef9c3] shadow-[0_3px_0_#0a0a0a] scale-[1.01]"
                        : "border-[#e5e4e7] bg-neo-white opacity-60"
                    }`}
                  >
                    <div className="mt-0.5 font-bold text-sm">
                      {isDone ? (
                        <span className="text-[#16a34a]">✓</span>
                      ) : isCurrent ? (
                        <span className="text-neo-black animate-pulse">▶</span>
                      ) : (
                        <span className="text-gray-400">○</span>
                      )}
                    </div>
                    <div className="flex-1">
                      <div className={`text-xs font-bold ${isDone ? "text-[#16a34a]" : isCurrent ? "text-neo-black" : "text-gray-500"}`}>
                        {step.title}
                      </div>
                      <div className="text-[11px] text-neo-border mt-0.5">{step.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="text-center pt-1 text-[11px] text-neo-border font-mono">
              Mohon tunggu sebentar, sistem sedang melakukan kalkulasi radius geografis...
            </div>
          </div>
        </div>
      )}

      {/* Header Utama & Shortcut Cepat */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold mb-1">Upload & Pembentukan Master Data PLN</h1>
          <p className="text-sm text-neo-border">
            Bentuk master dari gabungan ACMT (Pascabayar) & LPB (Prabayar), exclude PDPJ, lalu cocokkan Koordinat Kosong.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={pipelineActive || resetting}
            onClick={handleAutoSeedPLN}
            className="px-3.5 py-2 border border-neo-border bg-neo-accent text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] hover:bg-[#e85a26] disabled:opacity-50"
            title="Jalankan alur penuh PLN: Gabung ACMT+LPB -> Exclude PDPJ -> Cocokkan Koordinat Kosong"
          >
            {pipelineActive ? "Memproses Alur PLN..." : "⚡ Quick Demo Alur Riil PLN"}
          </button>

          <button
            type="button"
            disabled={pipelineActive || resetting}
            onClick={handleResetDatabase}
            className="px-3 py-2 border border-[#dc2626] bg-white text-[#dc2626] text-xs font-bold rounded-sm shadow-[0_2px_0_#dc2626] hover:bg-[#fee2e2] disabled:opacity-50"
          >
            {resetting ? "Resetting..." : "🗑️ Reset Data"}
          </button>
        </div>
      </div>

      {/* Alur Kerja PLN Cards */}
      <div className="p-4 border border-neo-border bg-neo-white rounded-sm shadow-[0_2px_0_#0a0a0a] text-xs">
        <strong className="block mb-1 text-sm font-bold text-neo-black">Alur Pemrosesan PLN GeoMatch:</strong>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-neo-border">
          <div className="p-2 border border-neo-border bg-white rounded-xs">
            <strong>1. ACMT + LPB</strong>
            <p className="text-[11px]">Cleaning data bertumpuk multi-bulan & gabung jadi Master.</p>
          </div>
          <div className="p-2 border border-neo-border bg-white rounded-xs">
            <strong>2. Exclude PDPJ</strong>
            <p className="text-[11px]">Keluarkan data yang sudah verif dari Master.</p>
          </div>
          <div className="p-2 border border-neo-border bg-white rounded-xs">
            <strong>3. Master Sisa</strong>
            <p className="text-[11px]">Menghasilkan daftar calon pelanggan yang belum valid.</p>
          </div>
          <div className="p-2 border border-neo-border bg-white rounded-xs">
            <strong>4. Koordinat Kosong</strong>
            <p className="text-[11px]">Titik tanpa IDPEL dicocokkan ke Master Sisa via Radius Spasial.</p>
          </div>
        </div>
      </div>

      {successInfo && (
        <div className="p-4 border border-[#16a34a] bg-[#dcfce7] rounded-sm text-sm font-medium shadow-[0_2px_0_#16a34a] space-y-2">
          <div className="text-[#16a34a] font-bold">✓ {successInfo}</div>
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              onClick={() => navigate("/process")}
              className="px-3 py-1.5 border border-neo-border bg-neo-black text-white text-xs font-semibold rounded-sm shadow-[0_1px_0_#0a0a0a] hover:bg-[#222]"
            >
              ⚙️ Lanjut ke Input Manual & Matching →
            </button>
            <button
              onClick={() => navigate("/candidates")}
              className="px-3 py-1.5 border border-neo-border bg-white text-neo-black text-xs font-semibold rounded-sm shadow-[0_1px_0_#0a0a0a] hover:bg-[#e5e4e7]"
            >
              🗺️ Langsung Buka Review & Peta Spasial →
            </button>
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="p-4 border border-[#dc2626] bg-[#fee2e2] text-[#dc2626] rounded-sm text-sm font-medium">
          Error: {errorMessage}
        </div>
      )}

      {/* 1. Pilih Dataset yang akan diupload */}
      <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
        <h2 className="text-sm font-bold mb-2">1. Pilih Data yang Ingin Diunggah</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {(["pascabayar", "prabayar", "pdpj", "koordinat_kosong"] as DatasetType[]).map((type) => {
            const state = datasetStates[type];
            const locked = state.status === "locked";
            return (
              <button
                key={type}
                type="button"
                disabled={pipelineActive || batchProcessing}
                onClick={() => setCurrentDataset(type)}
                className={`p-3 text-left border border-neo-border rounded-sm transition ${
                  currentDataset === type
                    ? "bg-neo-black text-white shadow-[0_2px_0_#0a0a0a]"
                    : "bg-white text-neo-black hover:bg-[#e5e4e7]"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="font-bold text-xs">{DATASET_CONFIG[type].title}</div>
                  <span className={`text-[10px] font-bold ${locked ? "text-[#16a34a]" : "opacity-70"}`}>
                    {locked ? "LOCKED" : state.status === "reviewing" ? "REVIEW" : "BELUM"}
                  </span>
                </div>
                <div className="text-[10px] opacity-80 mt-1 line-clamp-2">{DATASET_CONFIG[type].desc}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. File Upload & Shortcut Muat Contoh */}
      <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold">2. Upload File (XLSX / CSV) - {currentConfig.title}</h2>
          <button
            type="button"
            disabled={pipelineActive || batchProcessing || currentState.status === "locked"}
            onClick={handleLoadDummyToForm}
            className="px-3 py-1.5 border border-neo-border bg-[#e5e4e7] hover:bg-[#d4d3d6] text-xs font-bold rounded-sm text-neo-black shadow-[0_2px_0_#0a0a0a]"
          >
            📋 Muat Contoh Data [{currentDataset.toUpperCase()}]
          </button>
        </div>

        <input
          type="file"
          accept=".csv, .xlsx, .xls"
          disabled={pipelineActive || batchProcessing || currentState.status === "locked"}
          onChange={handleFileUpload}
          className="block w-full text-sm text-neo-black file:mr-4 file:py-2 file:px-4 file:rounded-sm file:border file:border-neo-border file:text-sm file:font-semibold file:bg-neo-white file:text-neo-black hover:file:bg-[#e5e4e7] cursor-pointer disabled:opacity-50"
        />
        {currentState.file && (
          <p className="text-xs text-[#16a34a] font-medium">
            File terpilih: <strong>{currentState.file.name}</strong> ({Math.round(currentState.file.size / 1024)} KB)
          </p>
        )}
        {currentState.status === "locked" && (
          <p className="text-xs text-[#16a34a] font-bold">✓ Dataset terkunci. Pilih dataset lain untuk melanjutkan.</p>
        )}
      </div>

      {/* 3. Auto-Filter Kolom */}
      {currentState.headers.length > 0 && (
        <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h2 className="text-sm font-bold">3. Penyaringan Kolom Otomatis</h2>
              <p className="text-xs text-neo-border">Sistem otomatis mendeteksi kolom yang relevan dari file Anda.</p>
            </div>
            <span className="px-2 py-1 neo-highlight border border-[#16a34a] bg-[#dcfce7] text-[#16a34a] text-[10px] font-bold rounded-xs">
              ✓ Auto-Filtered
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
            {currentConfig.fields.map((field) => (
              <div key={field.key} className="flex flex-col gap-1">
                <label className="text-xs font-semibold text-neo-black">
                  {field.label} <span className="text-[#dc2626]">*</span>
                </label>
                <select
                  disabled={pipelineActive || batchProcessing || currentState.status === "locked"}
                  value={currentState.mapping[field.key] || ""}
                  onChange={(e) => updateDataset(currentDataset, { mapping: { ...currentState.mapping, [field.key]: e.target.value } })}
                  className="border border-neo-border p-1.5 rounded-sm text-xs bg-white disabled:opacity-50"
                >
                  <option value="">-- Pilih Kolom File --</option>
                  {currentState.headers.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Pratinjau 5 Baris Data */}
      {currentState.previewRows.length > 0 && (
        <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] overflow-x-auto">
          <h2 className="text-sm font-bold mb-2">4. Pratinjau Data (5 Baris Pertama)</h2>
          <table className="w-full text-left text-xs border border-neo-border">
            <thead className="bg-[#e5e4e7] border-b border-neo-border">
              <tr>
                {currentState.headers.map((h) => (
                  <th key={h} className="p-2 border-r border-neo-border">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {currentState.previewRows.map((row, idx) => (
                <tr key={idx} className="border-b border-neo-border hover:bg-neo-white">
                  {currentState.headers.map((h) => (
                    <td key={h} className="p-2 border-r border-neo-border">
                      {row[h] !== undefined ? String(row[h]) : "-"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 5. Lock/Keep Button per Dataset */}
      {currentState.status === "reviewing" && (
        <div className="flex flex-col sm:flex-row items-center justify-between p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] gap-3">
          <div>
            <span className="text-xs text-[#16a34a] font-bold block">✓ Kolom Terpetakan & Data Siap Di-Keep</span>
            <p className="text-[11px] text-neo-border">Kunci dataset ini, lalu lanjut upload dataset berikutnya.</p>
          </div>
          <button
            type="button"
            disabled={loading || pipelineActive || batchProcessing}
            onClick={handleLockDataset}
            className="w-full sm:w-auto px-6 py-2.5 border border-neo-border bg-[#16a34a] text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] disabled:opacity-50 hover:bg-[#15803d] flex items-center justify-center gap-2"
          >
            <span>🔒 {loading ? "Menyimpan dataset..." : "Keep & Lock Dataset"}</span>
          </button>
        </div>
      )}

      {/* 6. Batch Process - Process All Locked Datasets */}
      {lockedCount >= 2 && datasetStates.koordinat_kosong.status === "locked" && (
        <div className="p-4 border-2 border-[#16a34a] bg-[#dcfce7] rounded-sm shadow-[0_4px_0_#16a34a] space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[#16a34a]">✓ {lockedCount} Dataset Terkunci - Siap Diproses</h3>
              <p className="text-xs text-neo-border mt-1">
                Sistem akan membentuk master, exclude PDPJ, dan mencocokkan koordinat kosong.
              </p>
            </div>
            <button
              type="button"
              disabled={loading || pipelineActive || batchProcessing}
              onClick={handleBatchProcess}
              className="px-6 py-2.5 border border-neo-border bg-neo-black text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] disabled:opacity-50 hover:bg-[#1a1a1a]"
            >
              {batchProcessing ? batchProgress : "🔐 Konfirmasi Dataset & Lanjut ke Review"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
