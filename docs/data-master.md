# Data Master — tahap 1

Tahap ini memisahkan pengelolaan referensi pelanggan dari unggahan PDPJ dan data koreksi. Menu **Data Master** memiliki halaman Prabayar, Pascabayar, dan DIL. Halaman `/upload` dipakai untuk PDPJ dan data koreksi yang sudah tersedia pada alur lama.

## Penggunaan

Perbaikan pembacaan `KOORDINAT_X`/`KOORDINAT_Y` dan pemulihan data lama dijelaskan pada [koordinat-xy.md](koordinat-xy.md). Beberapa file PLN memakai X untuk lintang dan Y untuk bujur; mapping kini mempertimbangkan nilai, bukan hanya nama kolom.

1. Buka salah satu jenis Data Master dan pilih **Unggah berkas**.
2. Pilih CSV atau XLSX. Untuk Excel, pilih sheet yang berisi data. Baris kosong di awal sheet dilewati; baris pertama yang terisi dipakai sebagai nama kolom, termasuk bila header berada di baris kedua atau lebih jauh. Pratinjau menampilkan posisi header dan nomor baris asli. Periode berkas opsional berformat `YYYY-MM`.
3. Periksa deteksi kolom dan sesuaikan mapping jika nama kolom berbeda. IDPEL wajib tersedia; koordinat boleh kosong.
4. Pilih **Simpan dan validasi master**. Baris bermasalah tetap disimpan dan dapat diperiksa melalui filter kondisi.
5. Gunakan pencarian, filter berkas, dan pagination. Tombol **Detail** menampilkan nilai hasil mapping, data asli, nama berkas, sheet, nomor baris, dan periode.

Jika unggahan sudah tersimpan tetapi konfirmasi mapping terhenti, pilih berkas yang bertanda **Menunggu mapping**, lalu **Lanjutkan mapping**. Berkas tersebut belum dipakai sebagai referensi sebelum mapping dikonfirmasi.

Ekspor Excel kadang menyimpan metadata area sheet yang tidak sesuai dengan sel sebenarnya, misalnya `A1` meskipun tabel berada di baris atau kolom lain. Pratinjau menggunakan alamat sel yang terbaca. Jika pratinjau browser tidak menemukan header, pembacaan cadangan melalui `POST /upload/preview` memindai sel asli pada sheet yang dipilih dan mengembalikan lima baris beserta posisi header. Pratinjau ini tidak membuat batch atau menyimpan baris ke database. Impor Excel juga membaca sel asli tanpa bergantung pada metadata area tersebut, sehingga nomor baris dan kolomnya tetap konsisten dengan pratinjau.

Kartu ringkasan menghitung seluruh baris pada jenis/berkas terpilih, terpisah dari pencarian dan halaman tabel. Baris dengan IDPEL valid tetapi koordinat kosong tetap lolos validasi identitas dan masuk hitungan **Koordinat belum lengkap**. IDPEL yang berulang tetap tersedia sebagai observasi sumber; tabel katalog tidak melakukan deduplikasi.

## Kolom DIL

Deteksi disesuaikan dengan daftar kolom DIL yang diberikan pengguna:

| Kolom sumber | Penggunaan |
| --- | --- |
| `IDPEL`, `NAMA` | Identitas pelanggan; IDPEL dipertahankan sebagai teks |
| `V_BULAN_REKAP` | Periode observasi, mendahului periode berkas bila terisi |
| `KOORDINAT_X`, `KOORDINAT_Y` | Longitude dan latitude; diperiksa sebagai angka dan rentang geografis |
| `NOMOR_GARDU` | Nomor/kode gardu |
| `KODEDLPD`, `KDDK`, `STATUS_DIL` | Atribut terpisah, menggunakan nama sumber; tidak disamakan dengan kode gardu atau kode DIL generik |
| `NOMOR_METER_KWH`, `NOMOR_METER_PREPAID` | Kedua nomor meter disimpan terpisah; referensi meter umum menggunakan KWH, lalu prepaid jika KWH kosong |
| `UNITUPI`, `UNITAP`, `UNITUP` | Identitas unit sesuai sumber |
| `NAMAPNJ`, `NOBANG`, `KETNOBANG`, `RT`, `RW` | Komponen alamat disimpan terpisah |
| `NAMA_GARDU`, `NAMA_PENYULANG` | Informasi jaringan sesuai sumber |
| `JENISLAYANAN`, `TARIF`, `DAYA` | Atribut layanan sesuai sumber |
| Seluruh kolom lainnya | Tetap disimpan pada data asli dan ditampilkan dalam detail |

Arti bisnis `KODEDLPD`, `KDDK`, dan nilai `STATUS_DIL` belum ditetapkan. `STATUS_DIL` ditampilkan sebagai atribut sumber, terpisah dari hasil validasi sistem. Kolom **Kode DIL** generik tetap tersedia untuk berkas khusus, tetapi tidak ditebak dari salah satu kode tersebut.

Kolom pemisah tanpa nama diberi label berdasarkan posisi, misalnya `Kolom_3`. Nama kolom berulang diberi akhiran `__2`, `__3`, dan seterusnya agar nilainya tidak saling menimpa. Pratinjau dan backend menggunakan aturan yang sama. CSV mendukung pemisah koma, titik koma, tab, atau pipa. Simpan kolom IDPEL dan meter sebagai teks pada berkas asal; angka yang sudah kehilangan nol di Excel tidak dapat dipulihkan melalui impor.

## Penyimpanan dan pemrosesan

CSV mendukung UTF-8 (dengan atau tanpa BOM), UTF-16 dengan BOM, dan Windows-1252
(ANSI yang umum digunakan ekspor Excel). Encoding dideteksi otomatis pada
pratinjau dan backend. Pemeriksaan dilakukan bertahap hingga akhir file agar
karakter non-UTF-8 yang muncul setelah pratinjau tetap terdeteksi. Karakter yang
gagal didekode tidak dibuang atau diganti diam-diam.

- `UploadBatch` menyimpan jenis master, periode, sheet, dan mapping. `SourceRecord` menyimpan nomor baris, sel asli, serta salinan hasil ekstraksi untuk pencarian dan filter SQL.
- Migrasi `c284bd7945a1` menambahkan metadata dan jenis DIL tanpa menghapus sumber lama. Proses kompatibilitas saat startup mengisi metadata sumber lama dan memperbarui salinan ekstraksi ketika versinya berubah.
- Pembentukan master gabungan mendukung DIL sebagai pelengkap Prabayar/Pascabayar maupun sebagai satu-satunya referensi. DIL dapat mengisi atribut atau pasangan koordinat yang belum lengkap, sementara koordinat lengkap dan jenis layanan yang sudah diketahui dipertahankan.
- Observasi terbaru DIL dipilih sebelum melengkapi master. Periode ringkas seperti `202610` dan periode ISO seperti `2026-10` dibandingkan sebagai tanggal, sementara nilai aslinya tetap tersimpan.
- Semua observasi valid dipertahankan bersama asalnya di snapshot master gabungan. Snapshot proses terdahulu tetap terpisah sebagaimana perbaikan fondasi.

API katalog tersedia pada `/master/{kind}` dengan `kind` berupa `prabayar`, `pascabayar`, atau `dil`:

| Endpoint GET | Kegunaan |
| --- | --- |
| `/batches` | Daftar berkas, termasuk yang menunggu mapping |
| `/batches/{batch_id}` | Metadata, mapping tersimpan, dan pratinjau |
| `/summary?batch_id=...` | Ringkasan per jenis atau berkas |
| `/records?batch_id=...&q=...&status=...&skip=...&limit=...` | Pencarian dan pagination; maksimum 100 baris per halaman |
| `/records/{record_id}` | Detail hasil ekstraksi dan data asli |

Parameter jenis/berkas yang tidak sesuai ditolak; hasil kosong tetap kosong. Unggahan dan konfirmasi tetap menggunakan `/upload/` dan `/upload/confirm-mapping`. Pipeline menerima pilihan `dil_batch_id` dan menyimpan sumber yang dipilih pada proses.

## Verifikasi

Backend menggunakan SQLite terisolasi untuk pengujian integrasi. Skenario meliputi tiga jenis master, mapping khusus, DIL aktual, kolom kosong/duplikat, beberapa pemisah CSV, sheet Excel, periode, pencarian, pagination, isolasi jenis, kelanjutan mapping, migrasi cache, asal observasi, dan pipeline dengan referensi DIL saja.

```powershell
cd backend
venv/Scripts/python.exe -m pytest tests -q --cov=app --cov-report=term-missing
venv/Scripts/python.exe -m mypy app --explicit-package-bases --ignore-missing-imports
cd ../frontend
npm.cmd run build
npm.cmd run lint
```

Pengujian browser memakai API, database SQLite sementara, dan Vite pada port tersendiri. Tes tidak menggunakan database aplikasi aktif. Dependensi opsional ada pada `backend/requirements-e2e.txt`; di Windows browser bawaan tes adalah Microsoft Edge. Atur `E2E_BROWSER_CHANNEL` untuk browser lain yang sudah terpasang.

```powershell
# Dari root proyek, setelah dependensi backend dan frontend terpasang
backend/venv/Scripts/python.exe -m pip install -r backend/requirements-e2e.txt
backend/venv/Scripts/python.exe -m pytest frontend/tests/e2e -q
```

Pengujian ini memeriksa unggah CSV, mapping manual, DIL XLSX dengan kolom aktual, pemilihan sheet, detail sumber, filter kondisi, isolasi jenis, kelanjutan unggahan, dan navigasi mobile. Integrasi PostgreSQL/PostGIS belum dijalankan pada tahap ini.

## Tahap berikutnya

Validasi PDPJ tersedia pada [tahap 2](validasi-pdpj.md), sedangkan pemisahan kategori koreksi dan kandidat tersimpan tersedia pada [tahap 3](data-koreksi.md). Berikutnya adalah interaksi peta dan hasil sebelum/sesudah sesuai analisis alur.
