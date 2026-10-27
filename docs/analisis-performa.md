# Analisis waktu proses

## Optimasi yang diterapkan pada 27 Oktober 2026

- Migrasi `e5fa92c30b71` menambahkan empat indeks untuk akses batch/identitas sumber, kandidat per proses/generasi/target/rank, dan snapshot/latitude. Pemasangan idempoten tersedia saat startup dan lewat Alembic. Indeks sudah diverifikasi pada SQLite lokal saat tidak ada pekerjaan aktif; jumlah baris sumber tetap nol setelah reset sebelumnya.
- Nama kolom dicatat pada `UploadBatch.source_headers`. Mapping tidak lagi membaca seluruh JSON untuk menemukan header. Batch lama tetap membaca gabungan seluruh nama kolom sebelum mencatat hasilnya.
- Cache terbatas menyimpan pemetaan alamat kolom, bukan nilai sel. Fallback alias saat sel kosong, mapping eksplisit, nol di depan, dan interpretasi koordinat tetap diperiksa per baris.
- Kandidat/evidence ditulis maksimal 400 per kelompok dan hasil target maksimal 100. Hasil `RETURNING` dipasangkan melalui target/rank, tanpa mengandalkan urutan database. Observasi diambil sekaligus per kelompok. Publikasi generasi tetap satu transaksi, termasuk rollback ketika kegagalan terjadi setelah sebagian kelompok ditulis.
- Pembuatan PDPJ memuat/menyimpan 400 baris per kelompok, termasuk nilai pemeriksaan sebelumnya dan rekomendasi. Duplikasi tetap diperiksa terhadap seluruh review. Perubahan satu baris hanya menyegarkan kelompok IDPEL lama/baru yang terdampak, sambil mempertahankan audit.
- Master Sisa membaca sumber bertahap dan menulis bulk. Master gabungan mempertahankan observasi lengkap pada data snapshot, tanpa menggandakannya lagi dalam `normalized_data`.
- Endpoint SQL sinkron memakai threadpool FastAPI sehingga tidak menahan event loop API. Konfigurasi PostgreSQL, Redis, dan Celery tidak diganti oleh optimasi ini; threadpool berbeda dari antrean worker terpisah.

Log `uvicorn.error.performance` mencatat `stage`, `status`, `duration_ms`, serta ID internal/jumlah baris yang diizinkan. Tahap mencakup `upload.read_and_store`, `upload.validate_and_map`, `pdpj.create_review`, `master.build`, `master.exclude_pdpj`, `corrections.match_and_store`, dan `pipeline.total`. Isi sel, nama pelanggan/file, SQL, dan pesan exception tidak dicatat. Waktu transfer browser ke server tidak termasuk waktu pemrosesan ini.

Perbandingan terisolasi dengan baseline `19e2e1ca90a7ccbd258ea47ed5961af95bc4b587` memakai SQLite dalam memori, skema/indeks yang sama pada kedua jalur, 500 target dan 3.500 kandidat:

| Pengukuran | Baseline | Sesudah optimasi |
| --- | --- | --- |
| Pemeriksaan koreksi, satu pengukuran | 2,0034 detik | 0,2531 detik |
| Statement INSERT kandidat | 3.500 | 9 |
| Ekstraksi 10.000 baris, median tiga pengulangan | 0,6134 detik | 0,2341 detik |

Nilai/status target, kandidat, rank, jarak, dan evidence dibandingkan dan identik. Angka ini menunjukkan pengurangan overhead pada skenario uji; bukan jaminan percepatan yang sama untuk file 500 MB, I/O disk, atau beban pengguna bersamaan. Ulangi dari direktori `backend`:

```powershell
venv/Scripts/python.exe -m tests.benchmark_processing --baseline 19e2e1ca90a7ccbd258ea47ed5961af95bc4b587 --targets 500
```

Runner hanya menjalankan commit lokal tepercaya yang dipilih secara eksplisit dan memakai database dalam memori. Pengujian juga mencakup urutan `RETURNING` terbalik, rollback penulisan parsial, duplikasi/perubahan identitas melintasi kelompok, dan respons endpoint ringan ketika pemeriksaan PDPJ sedang menunggu.

Penyimpanan evidence bersama secara penuh, snapshot lintas proses dengan identitas versi sumber yang aman, dan migrasi PostgreSQL/PostGIS tetap merupakan pekerjaan lanjutan. Radius dan rumus jarak tidak diubah pada tahap ini.

## Analisis awal pada 26 Oktober 2026

Pemeriksaan dilakukan pada 26 Oktober 2026 dengan membaca kode, konfigurasi, metadata database, serta query plan pada salinan database. Proses aktif tidak dihentikan. Perubahan indeks maupun mode jurnal belum diterapkan pada database aktif.

## Temuan

| Temuan | Bukti | Dampak |
| --- | --- | --- |
| Data berukuran besar | Database lokal sekitar 18,03 GiB; pemeriksaan sebelumnya mencatat sekitar 1,5 juta baris sumber | Pembacaan berulang, salinan JSON, dan penulisan snapshot menambah waktu I/O |
| Backend memakai SQLite fallback | Impor konfigurasi backend menghasilkan dialect `sqlite`, walaupun konfigurasi URL mengarah PostgreSQL | Penulisan besar berbagi satu database lokal dan dapat menahan pembacaan |
| Database aktif sedang terkunci | Percobaan SELECT metadata menghasilkan `database is locked` | Pembacaan status/daftar dapat menunggu saat pekerjaan menulis |
| Redis tidak merespons | Ping lokal berakhir dengan timeout; `ALLOW_SYNC_FALLBACK=true` | Bila pengiriman antrean gagal, pipeline dijalankan lewat thread aplikasi API |
| Filter sumber per batch belum memiliki indeks | Model dan salinan database hanya mempunyai indeks ID dan IDPEL; query plan filter `batch_id` menunjukkan `SCAN source_records` | Pengambilan satu batch dapat memindai data batch lain |
| Indeks kandidat belum mengikuti cakupan pembacaan | Query detail memakai proses, generasi, dan target; query plan salinan hanya memakai indeks generasi | Banyak kandidat harus disaring setelah pembacaan indeks |
| Pembentukan master menyimpan semua observasi di memori | `master_builder.py` menampung dictionary deduplikasi dan daftar seluruh observasi | Pembacaan dengan `yield_per` tetap diikuti penumpukan observasi di memori |
| Isi observasi disalin berulang | Master gabungan menyimpan `data` dan `normalized_data` dengan daftar observasi; evidence setiap kandidat menyalin observasi lagi | Volume database dan pekerjaan serialisasi bertambah |
| Penulisan kandidat melakukan flush per kandidat | `corrections/engine.py` memanggil `db.flush()` setelah setiap kandidat | Jumlah perjalanan SQL meningkat mengikuti jumlah pasangan target/kandidat |
| Penyaringan spasial baru memakai pita latitude | Kandidat dalam pita latitude diperiksa dengan Haversine satu per satu | Kandidat yang jauh dalam arah longitude tetap melewati perhitungan jarak |

Pipeline membentuk master dan Master Sisa ketika proses belum mempunyai snapshot. **Periksa ulang pada proses yang sama sudah memakai snapshot proses tersebut**. Optimasi pemakaian ulang berikutnya perlu ditujukan pada proses berbeda dengan sumber yang benar-benar identik, bukan menganggap semua pencarian saat ini selalu membangun master ulang.

## Pengukuran terisolasi

Uji SQLite dalam memori memakai 50.000 baris sintetis, payload 512 byte per baris, dan pengambilan 400 baris pada batch terakhir. Median diambil dari 10 pengulangan:

| Kondisi | Median waktu query | Query plan |
| --- | --- | --- |
| Tanpa indeks batch | 4,258 ms | `SCAN source_records` |
| Indeks `(batch_id, id)` | 0,279 ms | `SEARCH ... USING INDEX ... (batch_id=?)` |

Hasil baris identik. Perbedaan sekitar 15 kali berlaku untuk query terisolasi ini. Durasi pipeline penuh dan waktu tiap tahap belum diukur; angka ini bukan estimasi percepatan seluruh rekonsiliasi.

## Urutan optimasi

1. Tambahkan indeks sesuai filter: `source_records(batch_id, id)`, pencarian identitas sumber sesuai kebutuhan `batch_id/idpel`, `match_candidates(process_id, generation, target_record_id, rank)`, dan `master_sisa_records(snapshot_id, latitude, id)`. Verifikasi query plan serta biaya penulisan setelah penambahan indeks. Pembuatan indeks pada database aktif perlu dijadwalkan setelah pekerjaan penulisan selesai.
2. Kelompokkan penulisan kandidat dan evidence, dengan korelasi ID kandidat yang benar. Pertahankan transaksi publikasi hasil, seluruh kandidat yang memenuhi radius, dan riwayat pilihan.
3. Pisahkan observasi sumber menjadi snapshot bersama yang dirujuk kandidat. Hindari menyalin JSON observasi lengkap untuk setiap kandidat dan setiap proses; data awal dan audit tetap tersedia melalui referensi snapshot yang tidak berubah.
4. Pakai ulang snapshot master lintas proses hanya jika batch sumber, versi validasi PDPJ, serta versi interpretasi/normalisasi sumber identik. Pemulihan koordinat juga harus masuk identitas versi sumber agar snapshot sebelum perbaikan tidak digunakan kembali secara keliru.
5. Tambahkan penyaringan spasial dua dimensi sebelum perhitungan jarak tepat. Pada PostgreSQL/PostGIS gunakan indeks spasial untuk pencarian radius. Optimasi tetap harus benar di batas radius, kutub, dan pergantian bujur, serta mempertahankan semua kandidat dalam radius.
6. Pulihkan koneksi PostgreSQL/PostGIS dan jalankan worker Celery dengan broker yang tersedia. Worker memisahkan pekerjaan berat dari layanan API; pengurangan durasi komputasi tetap memerlukan optimasi query dan algoritme di atas. Menambah worker saat masih memakai SQLite dapat memperbesar antrean penulisan.
7. Catat durasi tahap pembentukan master, pengecualian PDPJ, pencarian spasial, dan penyimpanan; sertakan jumlah baris/kandidat tanpa mencetak IDPEL atau isi pelanggan. Gunakan hasil pengukuran untuk menentukan optimasi berikutnya.

Langkah awal yang paling langsung adalah indeks dan penulisan berkelompok, diikuti pengurangan salinan observasi. Mengecilkan radius dapat mengurangi jumlah kandidat untuk kebutuhan operasional yang sesuai, tetapi radius tetap harus mengikuti ketelitian pencarian yang dibutuhkan pengguna.

## Reset ketika database terkunci

Pada mode SQLite, pekerjaan penulisan yang lama dapat menahan reset. Kegagalan pada SELECT daftar arsip berarti percobaan reset berhenti sebelum penghapusan dimulai. Endpoint reset sekarang mengambil hak tulis sebelum membaca daftar arsip, menjalankan pekerjaan sinkron pada threadpool, dan mengembalikan HTTP 503 dengan pesan tunggu proses impor/pemeriksaan selesai ketika SQLite masih sibuk. Respons tidak menyertakan SQL mentah maupun parameter data. Penghapusan database tetap berada dalam satu transaksi; penghapusan file arsip hanya dilakukan setelah commit berhasil.

Tunggu pekerjaan selesai sebelum mencoba kembali. Jika pengguna memutuskan membatalkan pekerjaan yang macet, hentikan backend dan worker Celery milik proyek, tutup aplikasi lain yang membuka database tersebut, lalu jalankan backend kembali sampai startup selesai sebelum mencoba Reset. Me-restart frontend saja tidak menghentikan transaksi backend. Pekerjaan atau antrean lama perlu diperiksa sebelum worker diaktifkan kembali.

Perbaikan pesan error tidak membatalkan pekerjaan aktif atau membebaskan kuncinya secara paksa. Pengujian memakai dua koneksi ke SQLite sementara: satu menahan kunci eksklusif, dan koneksi API ditolak tanpa menghapus baris/file; setelah kunci dilepas, reset yang diminta kembali berhasil.

## Backend 502 saat startup

Pada pemulihan lokal berikutnya, backend gagal startup karena satu baris `correction_candidate_evidence` tidak lagi mempunyai induk di `match_candidates` maupun `master_sisa_records`. Pemeriksaan integritas menolak melanjutkan, sehingga port 8000 tidak melayani API. Baris tersebut dicadangkan secara utuh dan diverifikasi pada `backend/backups/startup-recovery-20261026-075301-444540/orphan-candidate-evidence.json`, kemudian diisolasi dari tabel aktif. Baris itu sebelumnya sudah tidak dapat ditampilkan sebagai kandidat karena data induknya tidak ada; data sumber dan riwayat yang mempunyai relasi valid dipertahankan.

Proses backend lama dengan `--reload` juga masih aktif dan mengunci database. Setelah proses lama dihentikan dengan izin pengguna, satu backend baru dijalankan tanpa reload otomatis. Frontend berjalan di port 5173 dan mengarah ke `127.0.0.1:8000`. Default proxy juga memakai alamat IPv4 tersebut agar konsisten dengan bind backend lokal.

Koneksi SQLite aplikasi sekarang mengaktifkan `PRAGMA foreign_keys=ON` supaya referensi induk yang tidak ada ditolak sebelum tersimpan. Pengujian mencakup penolakan baris yatim pada koneksi aplikasi dan migrasi dengan foreign key aktif.

Log serta PID proses lokal disimpan di `backend/.runtime/` dan diabaikan Git. Proses yang dijalankan pada pemulihan ini memakai folder sementara `backend/.runtime/tmp` di drive D: melalui `TEMP`, `TMP`, dan `SQLITE_TMPDIR`. Verifikasi dilakukan melalui root backend, OpenAPI, frontend, serta proxy API frontend; semuanya merespons HTTP 200.

## Startup dengan jutaan baris pada 27 Oktober 2026

Database aktif berukuran sekitar 13,82 GiB dengan 5.784.251 baris sumber dalam 15 batch. Membuka koneksi SQLite hanya membutuhkan sekitar 0,14 detik. Sebelum API menerima koneksi, startup lama menjalankan ulang migrasi kompatibilitas, pemeriksaan seluruh foreign key, dan pencarian versi normalisasi pada setiap baris JSON. Akibatnya aplikasi tampak belum terhubung meskipun koneksi database sudah terbuka.

Startup sekarang menyimpan tahap migrasi yang selesai di `app_schema_state`. Tahap yang versinya sudah sesuai dilewati pada startup berikutnya. Pemeriksaan foreign key tabel sumber memakai indeks `batch_id`, sementara bentuk relasi lain tetap diperiksa dengan pemeriksaan SQLite. `PRAGMA foreign_keys=ON` tetap berlaku pada setiap koneksi aplikasi.

`upload_batches.catalog_version` mencatat versi normalisasi seluruh batch. Batch lama yang belum memiliki penanda diverifikasi sekali melalui pembacaan metadata bertahap, maksimal 2.000 baris per kelompok. Sel asli hanya dimuat untuk baris yang perlu normalisasi ulang. Penanda batch dan tahap migrasi berada dalam transaksi yang sama dengan pekerjaan terkait sehingga kegagalan dapat dicoba lagi. Unggahan baru mencatat versi setelah pemetaan selesai; penomoran baris dan penanda pemulihan koordinat juga disimpan saat penulisan. Startup berikutnya cukup memeriksa metadata batch dan tahap migrasi.

Nilai `catalog_version=NULL` berarti belum diverifikasi, `0` berarti impor mentah dengan nomor baris yang sudah tersedia, dan nilai `NORMALIZATION_VERSION` berarti normalisasi batch selesai. Jika kode pemeliharaan menambahkan atau mengubah baris sumber langsung, kosongkan penanda batch terkait agar diperiksa ulang. Naikkan versi tahap di `startup_schema.py` ketika mengubah migrasi struktural dan naikkan `NORMALIZATION_VERSION` ketika mengubah interpretasi kolom. Penanda migrasi struktural dipertahankan ketika data pengguna direset.

Konfigurasi lokal sekarang menunjuk langsung ke berkas SQLite yang memang berisi data, menggunakan path absolut di `backend/.env`. Ini menghindari percobaan PostgreSQL yang tidak tersedia sebelum fallback. Tidak ada pemindahan database atau penghapusan data. Salinan lengkap sebelum perubahan disimpan di `backend/backups/before-startup-20261027-c7be330b/pln_geomatch.db` dan jumlah baris sumbernya diverifikasi.

Pengujian mencakup startup kedua tanpa pembacaan `source_records`, pemrosesan batch baru dan versi normalisasi lama, rollback sebelum penanda selesai, serta deteksi referensi induk yang tidak ada pada pemeriksaan melalui indeks maupun pemeriksaan SQLite biasa.

Pengukuran pada database aktif: pemeriksaan pertama memakai kode baru membutuhkan 412,355 detik; seluruh 15 batch sudah memakai normalisasi versi 3, dengan `changed=False` pada setiap batch. Jumlah baris sumber setelah commit tetap 5.784.251. Impor `app.main` melalui proses Python baru sesudahnya membutuhkan 2,341 detik, dengan tahap katalog hanya 4,681 ms. Angka pertama merupakan verifikasi satu kali menggunakan kode baru, bukan pengukuran startup versi lama. Perubahan versi normalisasi di masa depan dapat memerlukan pemeriksaan ulang batch.

Backend dan frontend kemudian dijalankan kembali tanpa jendela terminal; keduanya siap dalam 4,268 detik pada peluncuran lokal ini. Root backend, health, OpenAPI, halaman frontend, serta proxy `/api/health` memberikan HTTP 200. Redis tetap bersifat opsional pada konfigurasi lokal dan tidak menjadi syarat kesiapan API.

## Pembacaan daftar gagal ketika pemeriksaan menulis database

Pada pemeriksaan/koreksi berikutnya, mode jurnal database masih `delete`. Transaksi penulisan panjang dapat memegang kunci eksklusif setelah cache SQLite menulis halaman ke disk, sehingga SELECT daftar berkas master dan PDPJ ikut gagal dengan `SQLITE_BUSY`. Pemeriksaan proses menunjukkan satu pohon Uvicorn dengan reloader, bukan dua server API terpisah.

Koneksi SQLite sekarang disiapkan dengan `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`, dan `synchronous=FULL`. WAL memungkinkan koneksi pembaca melihat data yang sudah di-commit ketika koneksi penulis masih menyiapkan hasil baru. Hasil pemeriksaan tetap diterbitkan dalam satu transaksi, dan kegagalan tetap di-rollback. WAL tidak menambah jumlah penulis serentak: tindakan tulis yang bersamaan masih dapat menunggu atau ditolak sementara. Durabilitas dan validasi relasi tidak dikurangi.

Mode WAL diaktifkan sebelum inisialisasi skema. Jika database sudah memakai WAL, startup hanya membaca modenya. Perubahan mode memerlukan database yang tidak sedang ditulis; kegagalan memperoleh akses menampilkan pesan startup yang jelas. Database dalam memori untuk pengujian tetap memakai mode `memory`.

Penanganan error aplikasi mengubah `SQLITE_BUSY`, `SQLITE_LOCKED`, dan kode turunannya yang belum ditangani endpoint menjadi HTTP 503 dengan `Retry-After: 2`. Pesan menyarankan menunggu pemeriksaan atau koreksi selesai. Log hanya memuat kode error SQLite, tanpa SQL atau parameter pelanggan. Error operasional lain tetap diperlakukan sebagai error operasional lain, dan aplikasi tidak mencoba ulang aksi tulis secara otomatis.

Perbaikan diuji di salinan kode di luar direktori yang dipantau `--reload`. Delapan pengujian tambahan memakai koneksi SQLite sungguhan untuk memeriksa pembacaan PDPJ/master ketika writer aktif, visibilitas data sebelum/sesudah commit, rollback, foreign key, durabilitas, serta respons busy tanpa membocorkan SQL. Seluruh 190 tes backend lulus. Setelah pengguna menyetujui penghentian pemeriksaan yang belum selesai, worker dihentikan, SQLite memulihkan jurnalnya sendiri, dan jumlah sumber terverifikasi tetap 5.784.251 baris dalam 15 batch. Cadangan sebelum aktivasi WAL dibuat melalui SQLite Backup API pada `backend/backups/before-wal-20261027-locked-recovery/pln_geomatch.db`.

Untuk pencadangan ketika WAL aktif, gunakan SQLite Backup API agar isi `.db` dan transaksi yang sudah di-commit dalam WAL tercakup konsisten. Menyalin `.db` saja saat aplikasi masih berjalan dapat melewatkan perubahan di file `-wal`. Jangan menghapus file `-wal`, `-shm`, atau jurnal secara manual untuk mengatasi kunci database.

Pada database aktif, setelah cadangan selesai diverifikasi, mode `wal`, `foreign_keys=1`, `synchronous=2` (FULL), dan `busy_timeout=5000` terkonfirmasi. Backend baru siap dalam 3,24 detik. Health dan daftar PDPJ/prabayar/pascabayar/DIL menghasilkan HTTP 200, demikian juga daftar PDPJ dan prabayar melalui proxy frontend. Tidak ada proses atau matching run yang tersisa setelah rollback pemeriksaan terputus; pemeriksaan yang belum selesai perlu dimulai ulang oleh operator. Sebanyak 24 tes terkait konkurensi, relasi, penyimpanan upload, reset, dan startup juga lulus pada kode yang sudah diterapkan.
