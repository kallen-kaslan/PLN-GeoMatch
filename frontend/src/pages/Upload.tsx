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

export default function UploadPage() {
  const navigate = useNavigate();
  const [datasetType, setDatasetType] = useState<DatasetType>("pascabayar");
  const [file, setFile] = useState<File | null>(null);
  const [, setUploadSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [headers, setHeaders] = useState<string[]>([]);
  const [previewRows, setPreviewRows] = useState<Record<string, any>[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});

  // State status
  const [resetting, setResetting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<string | null>(null);

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

  // Auto filter kolom sendiri (User-Oriented)
  const autoFilterColumns = (fileHeaders: string[], type: DatasetType) => {
    const config = DATASET_CONFIG[type];
    const initialMapping: Record<string, string> = {};

    config.fields.forEach((field) => {
      const match = fileHeaders.find((h) => {
        const clean = h.trim().toLowerCase().replace(/[_\s-]/g, "");
        return field.aliases.some((alias) => clean === alias || clean.includes(alias));
      });
      if (match) {
        initialMapping[field.key] = match;
      }
    });

    setMapping(initialMapping);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setUploadSuccess(false);
    setErrorMessage(null);
    setSuccessInfo(null);

    const ext = selectedFile.name.split(".").pop()?.toLowerCase();

    if (ext === "csv") {
      Papa.parse(selectedFile, {
        header: true,
        preview: 5,
        complete: (results) => {
          if (results.meta.fields) {
            setHeaders(results.meta.fields);
            setPreviewRows(results.data as Record<string, any>[]);
            autoFilterColumns(results.meta.fields, datasetType);
          }
        },
      });
    } else if (ext === "xlsx" || ext === "xls") {
      const reader = new FileReader();
      reader.onload = (evt) => {
        const bstr = evt.target?.result;
        const wb = XLSX.read(bstr, { type: "binary" });
        const wsName = wb.SheetNames[0];
        const ws = wb.Sheets[wsName];
        const data = XLSX.utils.sheet_to_json<Record<string, any>>(ws, { header: 1 });

        if (data.length > 0) {
          const fileHeaders = (data[0] as unknown[]).map(String);
          const rows = data.slice(1, 6).map((row) => {
            const obj: Record<string, any> = {};
            fileHeaders.forEach((h, i) => {
              obj[h] = (row as any[])[i];
            });
            return obj;
          });

          setHeaders(fileHeaders);
          setPreviewRows(rows);
          autoFilterColumns(fileHeaders, datasetType);
        }
      };
      reader.readAsBinaryString(selectedFile);
    }
  };

  // Muat dummy ke form per jenis dataset
  const handleLoadDummyToForm = () => {
    const sample = DUMMY_SAMPLES[datasetType];
    const dummyHeaders = Object.keys(sample[0]);
    const csvContent = Papa.unparse(sample);
    const dummyBlob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const dummyFile = new File([dummyBlob], `${datasetType}_sample.csv`, { type: "text/csv" });

    setFile(dummyFile);
    setHeaders(dummyHeaders);
    setPreviewRows(sample);
    autoFilterColumns(dummyHeaders, datasetType);
    setUploadSuccess(false);
    setErrorMessage(null);
    setSuccessInfo(`Data contoh [${DATASET_CONFIG[datasetType].title}] dimuat otomatis ke formulir.`);
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
      setFile(null);
      setHeaders([]);
      setPreviewRows([]);
      setMapping({});
      setSuccessInfo(res.data.message);
    } catch (err: any) {
      setErrorMessage(err.message || "Gagal reset.");
    } finally {
      setResetting(false);
    }
  };

  const handleSubmit = async () => {
    if (!file) return;

    setLoading(true);
    setPipelineActive(true);
    setPipelineTitle(`Mengunggah & Memproses [${DATASET_CONFIG[datasetType].title}]...`);
    setPipelineStepIndex(0);
    setErrorMessage(null);
    setUploadSuccess(false);

    try {
      // Langkah 1: Upload file mentah
      setPipelineStepIndex(0);
      const formData = new FormData();
      formData.append("file", file);
      formData.append("dataset_type", datasetType);

      const uploadRes = await api.post("/upload/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const batchId = uploadRes.data.id;

      // Langkah 2: Konfirmasi kolom mapping
      setPipelineStepIndex(1);
      await api.post("/upload/confirm-mapping", {
        batch_id: batchId,
        column_mapping: mapping,
      });

      // Langkah 3 & 4: Jalankan Auto Pipeline (Matching / Master update)
      setPipelineStepIndex(2);
      await new Promise((r) => setTimeout(r, 350));
      setPipelineStepIndex(3);

      const pipelineRes = await api.post(`/upload/auto-pipeline?batch_id=${batchId}`);
      const targetProcessId = pipelineRes.data.process_id || 1;

      // Langkah 5: Selesai & Langsung navigasi ke Review
      setPipelineStepIndex(4);
      setSuccessInfo(pipelineRes.data.message || "Pemrosesan & pencocokan berhasil!");

      setTimeout(() => {
        navigate(`/candidates?process_id=${targetProcessId}`);
      }, 700);
    } catch (err: any) {
      setErrorMessage(err.message || "Gagal memproses dan mencocokkan data.");
      setPipelineActive(false);
    }
  };

  const currentConfig = DATASET_CONFIG[datasetType];

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
          {(["pascabayar", "prabayar", "pdpj", "koordinat_kosong"] as DatasetType[]).map((type) => (
            <button
              key={type}
              type="button"
              disabled={pipelineActive}
              onClick={() => {
                setDatasetType(type);
                if (headers.length > 0) autoFilterColumns(headers, type);
              }}
              className={`p-3 text-left border border-neo-border rounded-sm transition ${
                datasetType === type
                  ? "bg-neo-black text-white shadow-[0_2px_0_#0a0a0a]"
                  : "bg-white text-neo-black hover:bg-[#e5e4e7]"
              }`}
            >
              <div className="font-bold text-xs">{DATASET_CONFIG[type].title}</div>
              <div className="text-[10px] opacity-80 mt-1 line-clamp-2">{DATASET_CONFIG[type].desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 2. File Upload & Shortcut Muat Contoh */}
      <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold">2. Upload File (XLSX / CSV) - {currentConfig.title}</h2>
          <button
            type="button"
            disabled={pipelineActive}
            onClick={handleLoadDummyToForm}
            className="px-3 py-1.5 border border-neo-border bg-[#e5e4e7] hover:bg-[#d4d3d6] text-xs font-bold rounded-sm text-neo-black shadow-[0_2px_0_#0a0a0a]"
          >
            📋 Muat Contoh Data [{datasetType.toUpperCase()}]
          </button>
        </div>

        <input
          type="file"
          accept=".csv, .xlsx, .xls"
          disabled={pipelineActive}
          onChange={handleFileUpload}
          className="block w-full text-sm text-neo-black file:mr-4 file:py-2 file:px-4 file:rounded-sm file:border file:border-neo-border file:text-sm file:font-semibold file:bg-neo-white file:text-neo-black hover:file:bg-[#e5e4e7] cursor-pointer"
        />
        {file && (
          <p className="text-xs text-[#16a34a] font-medium">
            File terpilih: <strong>{file.name}</strong> ({Math.round(file.size / 1024)} KB)
          </p>
        )}
      </div>

      {/* 3. Auto-Filter Kolom Sendiri (User-Oriented) */}
      {headers.length > 0 && (
        <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a]">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h2 className="text-sm font-bold">3. Penyaringan Kolom Otomatis (User-Oriented)</h2>
              <p className="text-xs text-neo-border">
                Sistem otomatis mendeteksi kolom yang relevan dari file Anda.
              </p>
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
                  disabled={pipelineActive}
                  value={mapping[field.key] || ""}
                  onChange={(e) => setMapping({ ...mapping, [field.key]: e.target.value })}
                  className="border border-neo-border p-1.5 rounded-sm text-xs bg-white"
                >
                  <option value="">-- Pilih Kolom File --</option>
                  {headers.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Pratinjau 5 Baris Data */}
      {previewRows.length > 0 && (
        <div className="p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] overflow-x-auto">
          <h2 className="text-sm font-bold mb-2">4. Pratinjau Data (5 Baris Pertama)</h2>
          <table className="w-full text-left text-xs border border-neo-border">
            <thead className="bg-[#e5e4e7] border-b border-neo-border">
              <tr>
                {headers.map((h) => (
                  <th key={h} className="p-2 border-r border-neo-border">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {previewRows.map((row, idx) => (
                <tr key={idx} className="border-b border-neo-border hover:bg-neo-white">
                  {headers.map((h) => (
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

      {/* 5. Submit Button */}
      {headers.length > 0 && (
        <div className="flex flex-col sm:flex-row items-center justify-between p-4 border border-neo-border rounded-sm bg-white shadow-[0_4px_0_#0a0a0a] gap-3">
          <div>
            <span className="text-xs text-[#16a34a] font-bold block">
              ✓ Kolom Terpetakan & Data Siap Diproses
            </span>
            <p className="text-[11px] text-neo-border">
              Sistem akan otomatis menyimpan, menjalankan alur rekonsiliasi, dan langsung mengalihkan ke Peta Spasial Review.
            </p>
          </div>
          <button
            type="button"
            disabled={loading || pipelineActive}
            onClick={handleSubmit}
            className="w-full sm:w-auto px-6 py-2.5 border border-neo-border bg-neo-black text-white text-xs font-bold rounded-sm shadow-[0_2px_0_#0a0a0a] disabled:opacity-50 hover:bg-[#1a1a1a] flex items-center justify-center gap-2"
          >
            <span>🚀 Konfirmasi, Cocokkan Spasial & Buka Review</span>
            <span>→</span>
          </button>
        </div>
      )}
    </div>
  );
}
