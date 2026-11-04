# Konteks PLN GeoMatch

Ringkasan diperiksa 2026-11-03. Ini peta untuk menelusuri kode, bukan pengganti
pemeriksaan aktual. Jangan menganggap isi database, status proses, atau branch
dalam percakapan lama masih sama.

## Lingkungan dan keputusan pengguna
- Windows, PowerShell terminal VS Code. Folder asal/cadangan:
  `D:\MAGANG\validasi\PLN-GeoMatch`; hasil gabungan main + diohaw + IDPEL Kosong:
  `D:\MAGANG\validasi\PLN-GeoMatch-integrasi`. Periksa cwd dan status Git dahulu.
- Frontend React/TypeScript/Vite; backend FastAPI/SQLAlchemy; CSV/XLSX memakai
  pembaca di backend, dengan pratinjau juga di frontend.
- `.env` lokal saat diperiksa mengarah ke SQLite. Fokus pengguna tetap SQLite;
  pindah PostgreSQL pernah dibahas tetapi ditunda. Default konfigurasi/README
  menyebut PostgreSQL, sehingga bukan bukti database yang sedang digunakan.
- Script root `npm.cmd run dev` menjalankan backend melalui
  `backend/venv/Scripts/python.exe` pada port 8000 dan frontend pada 5173.
  Periksa `package.json` dan keberadaan dependensi sebelum memberi panduan.

## Alur utama dan lokasi kode
1. Data Master: impor Prabayar/Pascabayar/DIL, pilih sheet, deteksi kolom otomatis,
   simpan dan validasi. Pilihan banyak sheet diproses berurutan; sheet yang sudah
   disimpan pada lingkup impor terkait dinonaktifkan.
   UI: `frontend/src/components/master/MasterImport.tsx`,
   `frontend/src/lib/import-master-sheets.ts`, `frontend/src/pages/Master.tsx`.
   Pembacaan/normalisasi/penyimpanan: `backend/app/modules/upload/`.
2. Data PDPJ: impor, pemetaan kolom, periksa IDPEL terhadap master terpilih,
   review/pelengkapan, selesaikan validasi. Sumber master terikat pada pemeriksaan.
   UI: `frontend/src/pages/Pdpj.tsx`; rincian: `docs/validasi-pdpj.md`.
3. Data Koreksi: impor target kategori IDPEL Tidak Ketemu/IDPEL Kosong; pilih
   berkas koreksi, PDPJ selesai divalidasi, petugas, dan radius; jalankan pemeriksaan.
   Persiapan master gabungan, pengecualian IDPEL PDPJ (Master Sisa), dan indeks
   observasi dapat berlangsung sebelum baris target mulai diperiksa.
   UI: `frontend/src/pages/Corrections.tsx`; backend:
   `backend/app/modules/corrections/`, `backend/app/modules/spatial/`.
   Fase 1 IDPEL Kosong: halaman awal memakai `EmptyCorrectionsOverview.tsx` dan
   API `/corrections/idpel_kosong/overview/{summary,records}`. Semua unggahan
   selesai digabung per baris sumber, memakai hasil tersimpan terbaru per baris
   serta keputusan terakhir lintas pemeriksaan; hasil lama tetap terlihat saat
   proses baru belum menyimpan hasil. Hanya cari/filter status, tanpa filter berkas.
   Ringkasan statis (tidak bisa diklik): total, belum diproses, koordinat bermasalah,
   tanpa kandidat, kandidat ditemukan. Kandidat ditemukan menghitung baris dengan
   kandidat pada hasil terbaru, terlepas dari pilihan petugas. Baris terhalang aturan
   lama masuk belum diproses; alasannya tersedia di detail. Pilihan tetap disimpan,
   tanpa status terpisah/kolom IDPEL di tabel. Kolom No menampilkan urutan tabel sesuai halaman (1, 2, 3, dst.); ID sumber tetap internal.
   IDPEL Kosong kini memakai alur nyata dua tahap: Unggah data / Cari kandidat.
   `EmptyCorrectionUpload.tsx` menyimpan batch/tahap/analysis_id di URL agar
   versi proses tidak berganti ketika ada analisis lain, memulihkan unggahan
   setelah refresh; `EmptyCorrectionFileStep.tsx` memilih sheet manual dan
   menampilkan lima baris asli, tanpa pemetaan manual. Berkas diarsipkan,
   impor sheet idempoten, Simpan dan berikutnya mengonfirmasi mapping otomatis.
   `EmptyRadiusWorkflow.tsx` menghubungkan API nyata ke `EmptyCandidatePreview.tsx`
   (nama file lama; kini panel murni tanpa fixture/timer simulasi).
   Analisis dimulai manual. Backend memakai satu versi PDPJ selesai validasi
   terbaru yang masih berlaku, menyimpan versi dan sumber master pilihannya.
   `radius_analysis.py` menyiapkan Master Sisa tanpa IDPEL PDPJ serta indeks
   seluruh observasi PR/PC/DIL. Snapshot/indeks dipakai ulang untuk cakupan,
   pencarian, dan unggahan lain dengan acuan sama. Pencarian langsung matching;
   tidak mengulang pengecualian atau mengganti sumber ketika radius dipilih.
   Rekomendasi adalah maksimum jarak kandidat terdekat, dibulatkan ke atas
   kelipatan 5 m (minimal 5 m), dengan batas analisis/pilihan radius 100.000 m.
   Baris tanpa kandidat sampai batas itu diberi keterangan; tanpa rekomendasi
   penuh. Koordinat tidak valid dan IDPEL terisi dihitung terpisah.
   `empty_jobs.py` menjalankan pekerjaan server memakai sesi per thread dan
   kunci OS/advisory lintas proses. Hasil/checkpoint per baris disimpan atomik
   bersama seluruh kandidat/bukti. Jeda menunggu baris aktif selesai; persiapan
   master/validasi akhir memakai bagian terbatas. Refresh/putus koneksi browser
   tidak menghentikan worker. Setelah backend berhenti, Lanjutkan memulihkan
   checkpoint; GET tidak otomatis menjalankan pekerjaan. Waktu dari pekerjaan
   nyata tersimpan, tanpa durasi jeda. Radius terkunci setelah pencarian dibuat.
   Navigasi di luar panel; footer tahap 2 Sebelumnya/Lihat hasil (aktif sesudah
   validasi hasil/publikasi selesai). Daftar proses tertunda kembali ke alur ini
   bila ada analysis_id; workspace lama tetap tersedia untuk riwayat lama.
   API `/corrections/idpel_kosong/radius-analyses/workflow` untuk pemulihan baca
   saja; `/{id}/analysis-job` dan `/{id}/search-job` memulai/jeda/lanjut.
   Model tabel analisis terdaftar di startup; migrasi `e63b2c740d19` sudah ada
   di kode. Jangan menjalankan migrasi/seed/impor lokal tanpa perintah pengguna.
   Penggabungan mempertahankan tema diohaw, impor banyak sheet, pencarian teks,
   dan fitur riwayat. `history/deletion.py` melindungi worker IDPEL Kosong,
   menghapus anak analisis sebelum induk, dan melepas tautan pencarian yang
   dihapus agar analisis selesai tetap dapat dipakai ulang. Database pengguna
   tidak dipakai tes; sumber cadangan tetap utuh. Inisialisasi file kunci Windows
   di `app/processing_activity.py` mengambil kunci sebelum menulis byte awal,
   agar pembacaan status bersamaan dengan permintaan jeda tidak gagal.
   Rincian dan batas: `docs/idpel-kosong-radius.md`.
4. Peta Koreksi: tampilkan kandidat tersimpan, tinjau sumber, petugas memilih
   kandidat; keputusan disimpan dan dapat ditampilkan/diekspor melalui hasil.
   UI: `frontend/src/pages/CorrectionMap.tsx`, `frontend/src/pages/Result.tsx`.

## Aturan pencarian yang perlu dijaga
- Pemeriksaan koreksi baru memakai `candidate_policy=2`: seluruh observasi valid
  dari sumber PR/PC/DIL yang terikat pada snapshot Master Sisa. Proses lama dapat
  memakai kebijakan berbeda; selalu periksa run yang sedang dibahas.
- Jarak Haversine dalam meter dibandingkan dengan radius permintaan. Perbedaan
  jumlah angka desimal koordinat tidak mensyaratkan kecocokan teks/prefix.
- Observasi dalam radius dikelompokkan per IDPEL; observasi terdekat mewakili
  kandidat dan sumber lainnya disimpan sebagai bukti. Kandidat tidak otomatis
  menjadi keputusan petugas. Periksa konflik/validitas sebelum menjelaskan hasil.
- `Pemeriksaan tersimpan` memilih proses; `Versi hasil` memilih generasi dalam
  proses. Mengubah dropdown hasil tidak menjalankan pencarian baru. Periksa ulang
  menghasilkan versi baru; jeda/lanjut memakai checkpoint proses terkait.
- Analisis radius IDPEL Kosong memakai data nyata. Batas 100.000 m; tanpa
  rekomendasi penuh bila masih ada target valid tanpa kandidat. Radius unggahan
  baru tidak mengubah hasil/radius unggahan lama.
- IDPEL Kosong mencari berdasarkan koordinat, tanpa benturan meter/survei atau
  validasi atribut lain. IDPEL terisi tetap tidak sesuai kategori; pengecualian
  master milik PDPJ tetap berlaku. IDPEL Tidak Ketemu memakai aturan sebelumnya.

## Rujukan sesuai kebutuhan
- Impor: `docs/data-master.md`, `docs/riwayat-file-sheet.md`, `docs/koordinat-xy.md`.
- Pencarian: `docs/data-koreksi.md`, `docs/koreksi-seluruh-observasi.md`.
- Persiapan/hasil: `docs/fondasi-data.md`, `docs/peta-koreksi.md`,
  `docs/hasil-koreksi.md`, `docs/analisis-performa.md`.
- Berkas sumber lokal: `gabungan_pra_pasca_pdpj.xlsx` dan
  `DIL_SALDO_MASK_UP_202606_53311.xlsx`. Tidak perlu membaca seluruh workbook
