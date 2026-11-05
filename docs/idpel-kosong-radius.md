# IDPEL Kosong: unggah, analisis radius, dan pencarian kandidat

Alur nyata dua tahap diaktifkan pada `EmptyCorrectionUpload.tsx`. Fixture angka,
progres berbasis timer, dan dropdown keadaan sudah dilepas. Panel tampilan lama
`EmptyCandidatePreview.tsx` kini komponen murni penerima data backend;
`EmptyRadiusWorkflow.tsx` mengatur pembacaan progres dan perintah eksplisit.

## Tahap unggah

Pengguna memilih unggah baru atau arsip, lalu memilih sheet secara manual.
Lima baris pertama ditampilkan melalui raw-preview tanpa normalisasi tampilan.
Simpan dan berikutnya mengimpor sheet lalu mengonfirmasi mapping otomatis.
Arsip berdasarkan hash berkas dan impor berdasarkan file/jenis/sheet/periode
mencegah penggandaan saat permintaan dikirim ulang. Batch disimpan pada URL
sebelum konfirmasi mapping; refresh memulihkan statusnya. Kembali dari tahap 2
memulihkan pilihan sheet tersimpan dan bisa melanjutkan tanpa impor ulang.
URL juga menyimpan analysis_id; pembacaan eksplisit mengunci versi proses
sehingga analisis baru pada batch yang sama tidak mengganti layar/hasil lama.

## Acuan dan pengecualian

Mulai analisis memilih satu versi PDPJ selesai validasi terbaru yang masih
berlaku (pemeriksaan kerja terkini per berkas atau publikasinya yang disetujui).
Versi PDPJ, daftar sumber master, dan batch target terikat sejak analisis dibuat.
Nama pengguna aplikasi dipakai untuk label audit sesuai mekanisme aplikasi yang
ada. Tidak ada pemilihan PDPJ/petugas tambahan di UI ini.

Master gabungan dibuat dari PR/PC/DIL terpilih. Master Sisa mengecualikan IDPEL
PDPJ pada versi tersebut, termasuk identitas sumber yang masih menunggu validasi
pada publikasi parsial. Indeks observasi hanya memuat koordinat dari IDPEL yang
masih eligible. Semua observasi milik IDPEL PDPJ terbuang, bukan hanya satu titik.
Persiapan dan indeks disimpan serta digunakan ulang berdasarkan acuan identik,
termasuk oleh unggahan koreksi lain. Data master/PDPJ baru tidak mengganti acuan
proses yang sudah berjalan.

## Analisis dan radius

Analisis menyimpan kandidat terdekat serta jarak Haversine setiap baris. Kueri
menggunakan batas lintang/bujur konservatif yang menangani kutub/dateline, lalu
menghitung jarak tepat. Rekomendasi = maksimum jarak terdekat dibulatkan ke atas
kelipatan 5 m, minimal 5 m. Batas analisis dan radius manual 100.000 m. Jika ada
baris valid belum memiliki kandidat sampai batas itu, rekomendasi penuh tidak
tersedia; rekomendasi sebagian dan jumlah baris tersebut ditampilkan.

Koordinat kosong/tidak valid tidak ikut rekomendasi. IDPEL yang terisi tidak
sesuai kategori dan dipisahkan dari masalah koordinat. Atribut lain tidak
menghalangi pencarian IDPEL Kosong. Aturan IDPEL Tidak Ketemu tetap memakai
pemeriksaan identitas/benturan semula.

Input otomatis terisi rekomendasi setelah analisis selesai. Cakupan radius
manual dibaca dari jarak yang sudah disimpan; tidak mencari ke master ulang.
Memiliki kandidat berarti minimal satu kandidat di dalam radius. Tanpa kandidat
dalam radius menghitung baris valid di luar cakupan, termasuk yang belum mendapat
kandidat sampai batas analisis. Koordinat bermasalah ditampilkan terpisah.

Mulai pencarian menyimpan radius dan membuat satu pemeriksaan idempoten dengan
snapshot serta indeks yang sama. Tahap pencarian langsung matching; tidak
mengulang persiapan/pengecualian. Semua kandidat dalam radius disimpan, satu per
IDPEL dengan observasi terdekat sebagai wakil dan bukti sumber lainnya. Radius
terkunci setelah pemeriksaan dibuat, dan hasil unggahan lama tidak diubah.

## Eksekusi, jeda, dan pemulihan

`empty_jobs.py` menjalankan thread backend dengan sesi database sendiri.
Kunci OS/advisory database memilih satu worker per analisis lintas proses.
Pengamatan status tidak mengambil alih pekerjaan atau membatalkan worker.
Browser hanya memberi perintah dan membaca status; refresh, pindah halaman,
atau putus koneksi browser tidak menghentikan pekerjaan.

Analisis dan matching menyelesaikan satu baris per transaksi. Kandidat, bukti,
hasil, cursor, hitungan, dan waktu kerja tersimpan bersama. Kegagalan menggulung
balik transaksi baris aktif; hasil sebelumnya tetap tersedia. Persiapan master
serta validasi/publikasi akhir menggunakan bagian terbatas yang sudah ada.

Permintaan jeda memberi sinyal lintas proses sebelum menunggu kunci tulis
SQLite. Worker menyelesaikan unit aktif, menyimpan hasilnya, lalu tidak mengambil
baris berikutnya. Status menjeda ditampilkan dekat progres dan di kanan atas.
Setelah jeda tersimpan, Lanjutkan menjalankan checkpoint yang sama. Waktu kerja
tersimpan meliputi unit berhasil, termasuk persiapan, tanpa waktu jeda/idle.

Jika backend berhenti, transaksi aktif dibatalkan dan kunci OS dilepas. GET
memulihkan checkpoint tanpa memulai pekerjaan. UI menawarkan Lanjutkan saat
status tersimpan running tetapi worker sudah tidak aktif. Tidak perlu unggah
ulang. Daftar proses tertunda mengarah ke alur dua tahap untuk analysis_id;
riwayat lama tanpa analisis tetap memakai workspace lama.

Empat kartu hasil menghitung baris: kandidat ditemukan, tanpa kandidat, belum
diproses (termasuk baris aktif), dan koordinat bermasalah. Kesalahan kategori
tersedia terpisah pada keterangan/detail. Lihat hasil aktif setelah validasi
jumlah kandidat/bukti dan publikasi selesai, bukan hanya saat cursor mencapai
baris terakhir.

## API dan pemeriksaan

`/corrections/idpel_kosong/radius-analyses/workflow?batch_id=...` adalah GET baca
saja, dengan radius_meters opsional untuk cakupan dan analysis_id untuk versi
tertentu (harus sesuai batch). POST pada koleksi membuat
analisis idempoten. `/{id}/analysis-job` dan `/{id}/search-job` menerima perintah
running/paused. Endpoint advance/state lama dipertahankan untuk kompatibilitas.
Model analisis sudah terdaftar pada startup dan migrasi `e63b2c740d19` tersedia.
Perubahan ini tidak menjalankan migrasi, seed, atau impor database pengguna.

Tes backend memakai SQLite memori/file sementara, tanpa impor `app.main`:
`python -B -m unittest tests.test_empty_workflow tests.test_radius_analysis tests.test_empty_correction_overview tests.test_raw_upload_preview -v`.
Cakupan meliputi unggah idempoten, isi asli, pengecualian PDPJ, observasi ganda,
rekomendasi/cakupan, sumber tetap, jeda saat baris aktif, rollback/resume,
pengamatan status bersamaan, API, dan aturan kategori lama. TypeScript diperiksa
tanpa emit dan frontend diperiksa dengan oxlint. Pengujian browser serta beban
jutaan baris belum dilakukan.

## Pemeriksaan integrasi main + diohaw

- Penghapusan riwayat melindungi worker aktif, menjaga analisis yang masih dipakai pencarian, dan melepas tautan pencarian terhapus agar data unggahan tetap bisa dilanjutkan. Regresi: `backend/tests/test_empty_history.py`.
- Status proses Windows mengambil kunci sebelum inisialisasi file untuk menghindari benturan dengan probe/jeda. Regresi: `backend/tests/test_processing_activity.py`.
- Tes browser alur dua tahap, pilihan sheet manual, head asli, card proses tertunda, rekomendasi, refresh, dan pengecualian PDPJ: `frontend/tests/e2e/test_empty_workflow_browser.py`.
- Pada integrasi 2026-11-03: 354 tes backend, 7 tes browser, 6 tes unit frontend, TypeScript/lint, dan build frontend lolos. Data browser/tes bersifat sementara; ini bukan benchmark jutaan baris.
