# Validasi dan pelengkapan PDPJ — tahap 2

Menu **Data PDPJ** (`/pdpj`) sekarang terpisah dari Data Master dan Data Koreksi. Berkas yang berhasil diimpor belum otomatis dianggap sudah benar: pemeriksaan keberadaan IDPEL dilakukan setelah konfirmasi mapping.

## Alur penggunaan

1. Siapkan Prabayar, Pascabayar, dan/atau DIL di menu Data Master.
2. Buka Data PDPJ, unggah CSV/XLSX, pilih sheet Excel bila diperlukan, lalu konfirmasi mapping. IDPEL dipertahankan sebagai teks. Unggahan yang menunggu mapping dapat dilanjutkan tanpa mengunggah ulang.
3. Isi nama **Petugas untuk riwayat**. Jalankan **Periksa IDPEL ke master**. Secara bawaan semua berkas master yang sudah dikonfirmasi dipakai; pilihan sumber dapat disesuaikan sebelum pemeriksaan dimulai.
4. Periksa ringkasan dan tabel. Keberadaan IDPEL, kelengkapan koordinat, serta hasil review ditampilkan terpisah. Filter dan pencarian berlaku pada tabel; kartu ringkasan tetap menghitung seluruh pemeriksaan.
5. Klik **Detail** untuk melihat data awal, nilai saat ini, data asli, seluruh rekomendasi sumber, dan riwayat perubahan.
6. Pilih kolom dari rekomendasi lalu **Terapkan kolom pilihan**, atau buka formulir manual. Kolom dapat diambil dari beberapa sumber melalui aksi pelengkapan terpisah.
7. Setelah masalah selesai, pilih **Selesaikan validasi PDPJ**. Tindakan ini menyetujui seluruh baris yang sudah lengkap dan mengunci pemeriksaan. Popup keberhasilan baru muncul setelah penyimpanan berhasil.
8. Buka Data Koreksi, pilih PDPJ yang sudah selesai divalidasi sebagai acuan pengecualian master, lalu lanjutkan alur koreksi yang tersedia.

## Aturan pemeriksaan

Untuk dataset besar, tombol **Lanjutkan dengan pengecualian massal** dapat
menyelesaikan pemeriksaan sambil mencatat seluruh baris yang masih bermasalah
sebagai pengecualian untuk tindak lanjut. Dialog menampilkan jumlah baris dan
mewajibkan nama petugas, alasan, serta persetujuan eksplisit. Perubahan jumlah
masalah atau revisi pemeriksaan membuat permintaan ditolak agar ditinjau ulang.

Baris yang sudah siap disetujui; pengecualian lama beserta alasannya tetap
dipertahankan. Data asli, nilai saat ini, dan daftar masalah tidak dihapus atau
diubah menjadi nilai yang dianggap valid. Setiap keputusan dicatat pada riwayat
baris. Setelah selesai, PDPJ dapat dipilih pada Data Koreksi dan Peta Koreksi.
Seluruh IDPEL PDPJ yang tersedia tetap dikecualikan dari kandidat, termasuk
IDPEL pada baris pengecualian. Peninjauan berikutnya menggunakan **Periksa ulang
PDPJ**, yang meminta peninjauan ulang keputusan pengecualian.

Penyelesaian standar tetap mensyaratkan tidak ada masalah yang belum ditangani.
Kedua jalur penyelesaian memvalidasi dan menyimpan secara bertahap dalam satu
transaksi; kegagalan penyimpanan membatalkan seluruh perubahan dan riwayat baru.

- IDPEL dicari pada setiap observasi dari sumber master yang dipilih. Observasi tanpa koordinat maupun dengan koordinat tidak valid tetap dapat membuktikan keberadaan IDPEL. Nilai koordinat sumber yang tidak valid tidak dapat dipilih untuk pelengkapan.
- Status IDPEL: **ditemukan**, **tidak ditemukan**, **kosong**, atau **format bermasalah**. IDPEL ditemukan dengan koordinat kosong tetap berstatus ditemukan.
- Untuk penyelesaian biasa, IDPEL harus ditemukan di master, pasangan koordinat harus lengkap dan valid, dan kesalahan format pada atribut yang terisi harus diselesaikan. Nama, alamat, tarif, dan atribut lain yang kosong tidak diwajibkan seluruhnya.
- IDPEL yang berulang dalam PDPJ menjadi catatan informasi, termasuk jika jenis pelanggan sama/berbeda atau koordinat berbeda. Duplikasi tidak menghalangi persetujuan baris maupun penyelesaian validasi dan tidak memerlukan alasan pengecualian. Semua baris dan nilainya tetap disimpan. Masalah format, kelengkapan koordinat, atau IDPEL yang tidak ditemukan tetap diperiksa terpisah.
- Rekomendasi menampilkan file, jenis master, baris, sheet, periode, serta atribut yang tersedia. Seluruh observasi disimpan; pagination detail menampilkan sepuluh rekomendasi per halaman.
- Pelengkapan tidak menimpa nilai terisi secara diam-diam. Pemilihan rekomendasi yang mengganti nilai memerlukan centang persetujuan dan alasan. Perubahan manual atas nilai terisi juga memerlukan alasan.
- Jika IDPEL diubah secara manual, sistem mencari rekomendasi untuk IDPEL baru pada sumber pemeriksaan yang sama. Rekomendasi IDPEL sebelumnya tetap tersimpan sebagai riwayat dan tidak bisa diterapkan ke IDPEL baru.
- Baris yang belum dapat diselesaikan dapat diberi **pengecualian kelengkapan** dengan alasan wajib. Pengecualian tidak menyatakan data menjadi lengkap. IDPEL yang diketahui pada baris pengecualian tetap dilindungi dari penggunaan ulang sebagai kandidat koreksi.
- Selesai pemeriksaan otomatis berbeda dari selesai validasi oleh petugas. Pemeriksaan awal hanya menyimpan temuan; penyelesaian validasi memerlukan semua masalah sudah diperbaiki atau diberi alasan pengecualian.

## Versi, sumber, dan riwayat

Migrasi `f6ac81d43e20` memindahkan temuan duplikasi lama pada pemeriksaan yang masih berjalan ke `warnings`, sehingga jumlah masalah dan tombol penyelesaian mengikuti aturan baru. Revisi pemeriksaan tersebut bertambah sekali untuk menolak permintaan lama yang belum dimuat ulang. Nilai sumber dan riwayat keputusan tetap dipertahankan. Temuan tersimpan pada pemeriksaan selesai tidak ditulis ulang; API menampilkan duplikasinya sebagai catatan informasi dan mempertahankan keputusan pengecualian historis.

Setiap pemeriksaan menyimpan daftar batch master yang dipakai, nilai awal PDPJ, nilai saat ini, rekomendasi per observasi sumber, dan riwayat aksi. Riwayat menyimpan nilai sebelum/sesudah, kolom yang dipilih, asal rekomendasi atau pengisian manual, nama petugas, alasan, dan waktu.

Pemeriksaan selesai tidak dapat diedit. **Periksa ulang PDPJ** membuat versi baru, mempertahankan nilai hasil pelengkapan sebelumnya untuk diperiksa ulang, dan menghitung kembali temuan terhadap sumber yang dipilih. Keputusan pengecualian perlu ditinjau ulang. Versi dan riwayat sebelumnya tetap tersedia melalui pilihan versi pemeriksaan. Pemeriksaan yang masih berjalan harus diselesaikan sebelum sumbernya diganti.

Mapping PDPJ maupun master yang sudah digunakan pemeriksaan dibekukan. Perubahan mapping memerlukan unggahan batch baru. Baris mentah dari unggahan tetap utuh; koreksi disimpan pada data pemeriksaan.

Penyimpanan menggunakan nomor revisi dan penguncian transaksi. Jika petugas lain telah mengubah pemeriksaan, permintaan dengan revisi lama ditolak dan UI meminta muat ulang. SQLite menggunakan kunci tulis transaksi, sedangkan PostgreSQL menggunakan penguncian baris.

Nama petugas saat ini adalah label yang diisi pengguna atau berasal dari sesi frontend. Proyek masih menggunakan scaffold autentikasi; label audit ini belum merupakan identitas yang diverifikasi oleh OIDC.

## Hubungan dengan proses koreksi

`/upload/batch-process` dan `/upload/auto-pipeline` mengharuskan PDPJ yang dipakai sudah selesai divalidasi. Proses menyimpan `pdpj_review_id` serta batch sumber master yang digunakan dalam pemeriksaan tersebut. Unggahan master berikutnya tidak mengubah sumber proses yang sudah dipilih.

Tanpa pilihan versi eksplisit, backend mengambil pemeriksaan terbaru untuk berkas PDPJ tersebut dan menolak jika belum selesai. Backend tidak berpindah diam-diam ke versi selesai yang lebih lama. Pilihan versi selesai tertentu dapat dikirim secara eksplisit. Pilihan master eksplisit yang berbeda dari sumber validasi ditolak agar pemeriksaan dan proses koreksi memakai cakupan yang sama.

Pengecualian master menggunakan IDPEL **saat ini** dari PDPJ selesai, termasuk baris dengan alasan pengecualian kelengkapan. Perbaikan IDPEL pada PDPJ karena itu benar-benar memengaruhi kandidat yang dapat dipakai.

`/process/prepare-master-sisa` juga menolak PDPJ yang belum selesai divalidasi. Snapshot dan pekerjaan lama tetap dipertahankan. Jalur matching lama tanpa PDPJ masih tersedia untuk data legacy; dataset kategori koreksi baru mewajibkan PDPJ selesai melalui [tahap 3](data-koreksi.md).

## Penyimpanan dan API

Migrasi tambahan `d901c38ae240` menambahkan tabel berikut tanpa menghapus data sebelumnya:

| Tabel | Isi |
| --- | --- |
| `pdpj_reviews` | Versi pemeriksaan, batch PDPJ, daftar sumber master, revisi, status dan penyelesaian |
| `pdpj_rows` | Nilai awal/saat ini, keberadaan IDPEL, masalah, review dan alasan pengecualian |
| `pdpj_recommendations` | Snapshot observasi master beserta sumber dan kesalahan validasinya |
| `pdpj_changes` | Riwayat nilai sebelum/sesudah dan keputusan per baris |

| Endpoint | Fungsi |
| --- | --- |
| `GET /pdpj/batches` | Daftar unggahan PDPJ |
| `GET /pdpj/batches/{batch_id}` | Pratinjau dan mapping tersimpan |
| `GET /pdpj/batches/{batch_id}/reviews` | Versi pemeriksaan berkas |
| `POST /pdpj/reviews` | Mulai pemeriksaan pada sumber master terpilih |
| `GET /pdpj/reviews/{id}` | Ringkasan dan sumber pemeriksaan |
| `GET /pdpj/reviews/{id}/rows` | Tabel, filter, pencarian, dan pagination |
| `GET /pdpj/reviews/{id}/rows/{row_id}` | Data awal/saat ini, rekomendasi, data asli, dan riwayat |
| `PATCH /pdpj/reviews/{id}/rows/{row_id}` | Simpan koreksi manual |
| `POST /pdpj/reviews/{id}/rows/{row_id}/apply` | Terapkan kolom rekomendasi terpilih |
| `POST /pdpj/reviews/{id}/rows/{row_id}/decision` | Persetujuan baris, pengecualian, atau pembukaan kembali |
| `POST /pdpj/reviews/{id}/complete` | Selesaikan dan kunci validasi |

Mutasi sesudah pemeriksaan dibuat menyertakan `revision` dan `actor`. Perubahan nilai juga menerima `reason`. Permintaan rekomendasi menyertakan ID rekomendasi, daftar kolom, dan persetujuan `overwrite` jika diperlukan. Permintaan dengan kombinasi ID pemeriksaan/baris/rekomendasi yang tidak sesuai ditolak.

## Pengujian

Jika konfirmasi mapping gagal karena penyimpanan database, API membatalkan
transaksi dan memberikan pesan khusus: HTTP 503 untuk kegagalan I/O, izin akses,
atau database sibuk; HTTP 507 untuk penyimpanan penuh. Unggahan yang sebelumnya
berhasil tersimpan tetap tersedia. Setelah penyimpanan pulih, ulangi konfirmasi
mapping pada formulir yang sama atau gunakan **Lanjutkan mapping**.

Pada SQLite, jangan menghapus file `-journal`, `-wal`, atau `-shm` secara manual
untuk mengatasi error. Cadangkan database beserta journal yang menyertainya
sebelum pemulihan; SQLite memakai journal untuk memulihkan transaksi yang terhenti.
Cadangan lokal di `backend/backups/` dan file journal dikecualikan dari Git.

Pengujian backend mencakup seluruh endpoint PDPJ, seluruh rekomendasi sumber termasuk koordinat kosong/tidak valid, duplikasi, koreksi IDPEL, penimpaan eksplisit, riwayat, pengecualian beralasan, penguncian setelah selesai, revisi lama, pembekuan mapping, pemeriksaan ulang, integrasi pipeline, serta migrasi dan reset berelasi.

Pengujian browser memakai database sementara dan server terpisah. Skenario mencakup impor PDPJ hingga selesai, pemilihan rekomendasi, koreksi manual, pengecualian, perlindungan nilai terisi, pemeriksaan ulang, kelanjutan mapping pada mobile, serta pencocokan yang mengecualikan IDPEL PDPJ setelah validasi.

```powershell
cd backend
venv/Scripts/python.exe -m pytest tests -q --cov=app --cov-report=term-missing
venv/Scripts/python.exe -m mypy app --explicit-package-bases --ignore-missing-imports
cd ../frontend
npm.cmd run build
npm.cmd run lint
cd ..
backend/venv/Scripts/python.exe -m pytest frontend/tests/e2e -q
```

Pengujian integrasi database tahap ini memakai SQLite. PostgreSQL/PostGIS dan integrasi identitas OIDC belum diuji pada lingkungan ini.

Pemisahan **IDPEL Tidak Ketemu** dan **IDPEL Kosong**, pemeriksaan benturan, ringkasan, dan kandidat tersimpan sudah tersedia pada [tahap 3](data-koreksi.md). Berikutnya adalah interaksi peta koreksi.
