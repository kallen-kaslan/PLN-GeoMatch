# Perbaikan fondasi data

Perubahan ini menyiapkan pemisahan fitur berikutnya tanpa mengganti susunan halaman.

## Perilaku data

- Master gabungan mempertahankan IDPEL ketika salah satu atau kedua koordinat kosong. Snapshot Master Sisa juga mempertahankannya. Matching spasial hanya memakai observasi dengan pasangan koordinat yang valid.
- Semua jalur ekstraksi menggunakan mapping batch yang sama: pembentukan master, pengecualian PDPJ, dan target matching. Pilihan kolom eksplisit mengalahkan alias, termasuk jika nilai kolom pilihan kosong.
- Data sumber tetap disimpan dalam bentuk aslinya. Konfirmasi mapping memperbarui IDPEL terindeks, status validitas, dan daftar kesalahan per field; jumlah baris valid tidak lagi disamakan dengan jumlah baris yang diunggah.
- CSV/Excel dibaca sebagai teks agar IDPEL yang disimpan sebagai teks, termasuk nol di depan, tetap utuh. Angka yang sudah kehilangan format/presisi dalam berkas sumber tidak direkonstruksi dengan tebakan.
- Master Sisa menggunakan `master_snapshots`. Proses menyimpan `master_snapshot_id`, `target_batch_id`, dan pilihan batch sumber pipeline. Worker memakai sumber yang sudah ditetapkan saat permintaan dibuat.
- Dataset yang sudah dipakai snapshot/proses atau sudah ditetapkan untuk pipeline antrean tidak dapat diubah mapping-nya. Unggah batch baru untuk mapping berbeda.
- Pencarian ulang membuat `matching_runs` dan generasi kandidat baru. Publikasi hasil dilakukan dalam satu transaksi. Generasi sebelumnya dan keputusan petugasnya tetap tersimpan; generasi historis hanya dapat dibaca.
- Pengiriman ulang pekerjaan dengan `run_id` yang sama tidak membuat kandidat ganda dan tidak mereset keputusan yang sudah tersimpan.
- Kandidat, ringkasan, dan ekspor selalu mengikuti proses dan generasi yang diminta. Proses tidak ditemukan menghasilkan 404; proses yang tidak mempunyai kandidat tetap mengembalikan daftar kosong.

## API yang terkait

| Endpoint | Perilaku |
| --- | --- |
| `POST /upload/confirm-mapping` | Validasi mapping dan baris; respons mencakup `valid_rows`, `error_rows`, dan maksimal 100 rincian kesalahan tanpa nilai IDPEL mentah |
| `POST /process/prepare-master-sisa` | Membuat snapshot baru dan mengembalikan `master_snapshot_id`; `pdpj_batch_id` opsional |
| `GET /process/master-snapshots` | Daftar snapshot untuk pemilihan sumber eksplisit |
| `POST /process/run-matching` | Mendukung `master_snapshot_id`; jika tidak dikirim, snapshot terbaru ditetapkan sebelum antrean dibuat |
| `POST /process/{id}/rerun` | Membuat versi pencarian baru menggunakan sumber proses yang sama; menerima `radius_meters` dan `max_candidates` |
| `GET /process/{id}/runs` | Riwayat versi pencarian, parameter, status, dan penanda versi aktif |
| `GET /process/{id}/candidates?generation=1` | Membaca kandidat versi tertentu; tanpa parameter memakai versi hasil aktif |
| `GET /process/{id}/summary?generation=1` | Ringkasan versi tertentu |
| `GET /process/{id}/export?generation=1` | Ekspor versi tertentu |

Ketika versi baru gagal, versi hasil aktif sebelumnya tetap tersedia. Radius dan ringkasan historis dibaca dari versi pencariannya sendiri. Ekspor tetap mengikuti format CSV lama, dengan cakupan kandidat dibatasi pada satu generasi.

## Database lama

Migrasi Alembic baru: `7adf4a6e9120`. Jalur kompatibilitas saat backend mulai menggunakan perubahan skema yang sama secara idempoten. Migrasi menambah kolom dan tabel sambil mempertahankan baris lama; tidak mereset database.

Kandidat lama menjadi generasi pertama. Master Sisa global lama dipertahankan sebagai snapshot historis. Sumber proses lama tidak ditebak karena skema sebelumnya tidak mencatat relasinya. Proses tersebut tetap dapat dibaca/diekspor, tetapi pencarian ulang memerlukan proses baru dengan sumber yang diketahui.

Batas jumlah kandidat pada pencarian lama yang tidak tercatat ditampilkan sebagai `null`. Data dan parameter historis yang tidak diketahui tidak diisi dengan nilai asumsi.

Untuk instalasi yang dikelola dengan Alembic, jalankan `alembic upgrade head` dari folder `backend` menggunakan konfigurasi database yang sesuai. Restart backend dan worker bersamaan agar keduanya menggunakan model dan format pekerjaan yang sama. Pekerjaan antrean dari versi aplikasi lama perlu ditinjau sebelum dikirim ulang.

## Verifikasi

Pasang alat pengujian melalui `pip install -r requirements-dev.txt` pada virtual environment backend. Pengujian menggunakan database SQLite dalam memori dan tidak menggunakan database kerja.

```powershell
cd backend
venv/Scripts/python.exe -m pytest tests -v --cov=app --cov-report=term-missing
venv/Scripts/python.exe -m mypy app --explicit-package-bases --ignore-missing-imports
```

Skenario regresi mencakup mapping custom, IDPEL dengan nol di depan, master tanpa koordinat, pengecualian PDPJ, sumber pekerjaan antrean, isolasi antarproses, pencarian ulang, pengiriman ulang worker, kegagalan proses, ekspor historis, dan alur upload sampai keputusan petugas. Migrasi diuji dari skema Alembic lama, termasuk saat foreign key SQLite aktif, serta pengulangan upgrade tanpa duplikasi data.

Pengujian tersebut belum menggantikan integrasi langsung pada PostgreSQL atau broker Celery. Perilaku worker diuji dengan pemanggilan task pada fixture terisolasi; fallback HTTP diuji ketika pengiriman ke broker gagal.

Hasil verifikasi: 45 pengujian lulus, coverage backend 80%, dan coverage modul ekstraksi/pembentukan master/pengecualian/matching/pipeline masing-masing setidaknya 85%. Pengiriman serentak untuk pekerjaan matching maupun pipeline juga diuji agar hanya satu himpunan kandidat diterbitkan.
