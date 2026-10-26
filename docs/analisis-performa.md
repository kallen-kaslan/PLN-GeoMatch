# Analisis waktu proses

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
