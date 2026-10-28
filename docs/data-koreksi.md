# Data Koreksi — tahap 3

Data Koreksi sekarang memiliki dua halaman terpisah:

- **IDPEL Tidak Ketemu**: `/koreksi/idpel-tidak-ketemu`.
- **IDPEL Kosong**: `/koreksi/idpel-kosong`.

Sidebar memiliki submenu untuk kedua kategori. Tautan lama `/upload` diarahkan ke halaman IDPEL Tidak Ketemu. Kategori mengikuti jenis unggahan asal dan tetap dipertahankan meskipun hasil pemeriksaan berbeda dari perkiraan awal.

## Penggunaan

1. Selesaikan validasi PDPJ melalui menu Data PDPJ.
2. Buka kategori koreksi yang sesuai, unggah CSV/XLSX, pilih sheet bila perlu, lalu konfirmasi mapping. Unggahan yang terhenti pada mapping dapat dilanjutkan tanpa duplikasi berkas.
3. Pada IDPEL Tidak Ketemu, kolom IDPEL wajib dipetakan. Pada IDPEL Kosong, kolom IDPEL boleh tidak tersedia. Koordinat boleh kosong pada kedua kategori agar semua baris tetap dapat diperiksa.
4. Petakan **nomor meter**, **nomor agenda**, dan **referensi survei / ID titik** secara terpisah. Nomor agenda tetap disimpan sebagai informasi dan boleh sama dengan PDPJ. Meter dan referensi survei tetap dipakai untuk memeriksa benturan.
5. Pilih PDPJ selesai divalidasi, isi nama petugas, dan tentukan radius. Jalankan pemeriksaan.
6. Tunggu sampai hasil tersimpan. Popup selesai mengikuti status backend, bukan penghitung waktu tampilan.
7. Tinjau kartu ringkasan, pencarian, filter, dan tabel. Klik **Detail** pada baris untuk melihat data asli, hasil pemeriksaan, benturan, serta kandidat tersimpan di bawah tabel.
8. Gunakan **Periksa ulang** untuk membuat versi pencarian berikutnya pada sumber yang sama. Pilih versi lama pada **Versi hasil** untuk melihat hasil sebelumnya. Pilihan PDPJ yang berbeda menghasilkan pemeriksaan baru.

Pemeriksaan selesai tidak berarti semua baris sudah memiliki kandidat atau sudah dipilih hasilnya. Baris bermasalah tetap terlihat dan mempunyai alasan hasil.

## Progres dan penyimpanan bertahap

Kedua kategori menampilkan panel progres dengan persentase desimal, tahap aktif,
jumlah baris koreksi tersimpan, validasi akhir tersimpan, baris sumber terakhir,
durasi, dan waktu pembaruan. Tahapnya adalah persiapan master, pemeriksaan benturan
dan kandidat, validasi hasil tersimpan, lalu penyimpanan penyelesaian pemeriksaan.
Animasi tetap berjalan selama bagian aktif diproses/disimpan dan saat menunggu jeda.

UI meminta maksimal 100 baris per bagian. Kandidat, bukti sumber, hasil baris,
dan checkpoint disimpan dalam transaksi yang sama. **Hentikan sementara koreksi**
menunggu transaksi aktif selesai, lalu menjeda pengiriman bagian berikutnya.
**Lanjutkan pemeriksaan koreksi** memakai run dan snapshot sumber yang sama,
termasuk setelah halaman dibuka ulang atau koneksi terputus. Jika satu bagian
gagal disimpan, hasil bagian sebelumnya tetap tersedia dan bagian gagal dicoba
ulang tanpa menggandakan kandidat.

Refresh memulihkan aktivitas server beserta checkpoint melalui
`GET /corrections/{kind}/checks/{id}/progress` setiap dua detik. Animasi dan
tombol mengikuti permintaan yang masih aktif, termasuk persiapan master,
pencocokan, validasi, dan penyelesaian. Ketika bagian aktif selesai tetapi
halaman lama sudah ditutup, tampil **Menunggu dilanjutkan dari hasil tersimpan**.
Tombol lanjut tidak mengirim pekerjaan baru selama bagian sebelumnya masih
aktif. Jeda dari halaman baru menunggu bagian itu selesai disimpan. Pemantauan
ringan ini tidak menjalankan ulang master atau ringkasan setiap dua detik.

Aktivitas nyata dibedakan dari status checkpoint: SQLite memakai kunci berkas
antarproses, PostgreSQL memakai advisory lock pada koneksi khusus. Kunci
dilepas otomatis ketika proses server keluar; checkpoint dan hasil tetap
tersimpan. Permintaan jeda mencegah bagian berikutnya mendahului penyimpanan
status jeda. Status yang belum dapat diperiksa ditampilkan sebagai tidak pasti.

Tabel, ringkasan, filter, dan detail langsung membaca hasil bagian yang sudah
tersimpan, termasuk saat proses berjalan, dijeda, atau terhenti. Versi terbaru
ditampilkan sebagai **hasil sementara** sampai validasi akhir dan penyelesaian
berhasil disimpan. Hanya baris yang belum diproses berstatus **Belum diperiksa**.
Versi lama yang sudah selesai tetap tersedia melalui pilihan versi hasil.
Setelah ada baris tersimpan, **Buka Peta Koreksi** tersedia untuk versi tersebut.
Pemilihan kandidat dapat dilakukan pada baris tersimpan dalam versi terbaru,
termasuk saat pemeriksaan berjalan, dijeda, atau terhenti. Baris yang belum
diproses belum ditawarkan di peta. Pemeriksaan berikutnya melanjutkan checkpoint
yang sama dan mempertahankan seluruh pilihan kandidat yang sudah disimpan.

Persiapan master juga bertahap: satu permintaan menyimpan maksimal 2.000 baris
pekerjaan, dibaca dalam blok maksimal 400 baris. Panel menampilkan jumlah sumber
master yang dibaca, berkas aktif, normalisasi tersimpan yang dipakai ulang,
IDPEL unik, pemeriksaan pengecualian PDPJ, master gabungan tersimpan, dan master
sisa tersedia. Progres keseluruhan mencakup pekerjaan persiapan tersebut.

Persiapan memakai normalisasi unggahan yang sesuai versinya, lalu menyimpan
penunjuk observasi terpilih per IDPEL di database. Seluruh riwayat observasi tetap
berada pada sumber asli; bukti lengkap baru dibaca untuk kandidat yang ditemukan.
Karena itu persiapan tidak menampung seluruh riwayat jutaan baris di RAM atau
menyalinnya lagi ke setiap baris master gabungan. Aturan periode terbaru,
prioritas Prabayar/Pascabayar, pelengkapan dari DIL, dan pengecualian PDPJ tetap
dipertahankan.

Snapshot belum selesai ditandai tidak siap dan tidak ditawarkan untuk pencarian.
Setelah siap, snapshot dapat digunakan ulang untuk pemeriksaan lain dengan
sumber, mapping, periode, versi normalisasi, dan versi PDPJ yang sama. Snapshot
dengan sumber berbeda tidak dipakai sebagai pengganti. Jeda, kegagalan, dan buka
ulang halaman mempertahankan checkpoint persiapan, termasuk pembentukan master
sisa. Migrasi `d24ea5037f96` menambahkan penyimpanan persiapan tanpa mengubah
snapshot atau keputusan koreksi lama.

Validasi akhir memeriksa jumlah kandidat dan bukti terhadap setiap hasil baris,
kemudian menyimpan checkpoint validasinya. Persentase tidak mencapai 100% sebelum
status penyelesaian berhasil disimpan. Hasil bagian yang sudah tersimpan dapat
digunakan di tabel dan peta sebelum seluruh run lolos validasi; hasil tersebut
diberi penanda sementara. Perluasan radius menunggu pemeriksaan selesai agar
kelanjutan baris tetap memakai sumber, radius, dan versi yang sama.

UI mengirim `incremental: true` pada pembuatan/pemeriksaan ulang, lalu memanggil
`POST /corrections/{kind}/checks/{id}/advance` dengan `run_id`, revisi checkpoint,
dan ukuran bagian. Endpoint `/pause` dan `/resume` mengontrol run yang sama.
Permintaan dengan revisi atau run lama ditolak. Pemanggil lama tanpa flag tersebut
tetap menggunakan dispatch dan kontrak pemrosesan sebelumnya. Migrasi
`c13d94f26e85` menambahkan checkpoint tanpa mengubah run historis.

## Pemeriksaan benturan dan kategori

Pemeriksaan memakai nilai PDPJ **saat ini** dari versi validasi selesai yang dipilih, termasuk perbaikan manual sebelumnya.

| Kondisi | Hasil |
| --- | --- |
| IDPEL sama dengan PDPJ | Benturan; pencarian kandidat tidak dijalankan |
| Nomor meter sama dengan nomor meter PDPJ | Benturan; pencarian tidak dijalankan |
| Nomor agenda sama dengan nomor agenda PDPJ | Diperbolehkan; pencarian kandidat tetap dijalankan |
| Referensi survei sama dengan referensi survei PDPJ | Benturan; pencarian tidak dijalankan |
| Nilai agenda kebetulan sama dengan nilai meter | Tidak dianggap benturan antartipe |
| Koordinat sama, tetapi tidak ada benturan identitas | Peringatan; pencarian tetap berjalan |
| IDPEL terisi pada unggahan IDPEL Kosong | Data perlu diperbaiki; kategori asal tidak dipindah otomatis |
| IDPEL kosong pada unggahan IDPEL Tidak Ketemu | Data perlu diperbaiki |
| IDPEL ternyata ditemukan dalam sumber master | Ditandai ditemukan; kategori asal tetap IDPEL Tidak Ketemu |

Referensi dibandingkan setelah spasi tepi dibersihkan dan huruf diseragamkan. Nol di depan tetap dipertahankan: `000123` berbeda dari `123`. Nilai kosong dan referensi yang seluruhnya nol tidak dipakai sebagai bukti benturan. Nomor meter KWH dan prepaid turut diperiksa sebagai identitas meter.

Kesamaan nomor agenda tidak menghalangi pencarian maupun pemilihan kandidat pada kedua kategori koreksi, termasuk bila kolom agenda dipetakan melalui referensi generik lama. Untuk hasil yang sebelumnya terhalang nomor agenda, gunakan **Periksa ulang** agar aturan baru diterapkan pada versi berikutnya. Hasil historis tetap dipertahankan, termasuk keterangan benturan yang berlaku saat hasil tersebut dibuat.

Referensi generik yang jenisnya tidak dapat dipastikan tidak dipakai untuk menuduh benturan secara otomatis. Untuk kolom khusus pada berkas Anda, pilih mapping jenis referensi secara eksplisit. Pemeriksaan PDPJ lama tetap dapat memakai jenis referensi yang dikenali dari header asal; nilai yang sudah diganti melalui pelengkapan tidak dibangkitkan kembali dari sel lama.

Detail benturan menyimpan jenis alasan, nilai yang sama, nomor baris PDPJ, dan snapshot data PDPJ terkait. Baris tidak dihapus dari sumber.

## Master dan kandidat

Pemeriksaan menggunakan daftar sumber master yang sudah tersimpan pada validasi PDPJ. Master gabungan dan Master Sisa dibentuk sebagai snapshot proses tersendiri. IDPEL milik PDPJ dikecualikan sebelum pencarian kandidat; IDPEL pada baris PDPJ dengan pengecualian kelengkapan juga tetap dilindungi.

Keberadaan IDPEL diperiksa pada seluruh observasi sumber terpilih, termasuk identitas yang koordinatnya belum lengkap. Pencarian spasial hanya memakai Master Sisa dengan pasangan koordinat valid. Jarak dihitung dengan Haversine; penyaringan rentang lintang mengurangi perhitungan tanpa membuang kandidat yang memenuhi radius.

Seluruh kandidat dalam radius disimpan, diurutkan berdasarkan jarak dan IDPEL. Batas lima kandidat dari alur lama tidak diterapkan pada kategori baru. Target tanpa kandidat mempunyai **nol kandidat nyata**, bukan kandidat buatan seperti `TIDAK_DITEMUKAN` atau `DILUAR_RADIUS`.

Setiap kandidat menyimpan nilai master dan seluruh observasi sumbernya: file, jenis master, baris, sheet, periode, dan atribut sumber. Endpoint detail membaca snapshot kandidat ini. Membuka detail berulang kali tidak memuat ulang seluruh master.

Radius pemeriksaan harus lebih besar dari nol dan paling besar 100.000 meter. Perubahan radius melalui pemeriksaan ulang menghasilkan versi baru; hasil, jarak, dan pilihan kandidat pada versi lama tetap tersimpan. Unggahan master berikutnya tidak mengubah sumber proses yang sudah ada. Untuk memasukkan sumber baru, periksa ulang PDPJ terlebih dahulu lalu buat pemeriksaan koreksi dengan versi PDPJ tersebut.

## Status dan ringkasan

Setiap sumber target mempunyai hasil tersimpan untuk setiap versi pencarian:

- Belum diperiksa.
- Benturan dengan PDPJ.
- Data perlu diperbaiki.
- Koordinat belum lengkap.
- Kandidat ditemukan.
- Tanpa kandidat dalam radius.

Keberadaan IDPEL disimpan terpisah dari status pencarian: ditemukan, tidak ditemukan, kosong, atau format bermasalah. Target tanpa koordinat tidak diberi titik buatan pada `0,0`.

Kartu menghitung baris target, bukan jumlah kandidat. Cakupannya mengikuti kategori, berkas, pemeriksaan, dan versi hasil. Pencarian, filter tabel, dan pagination tidak mengubah hitungan kartu. Hitungan koordinat belum lengkap dapat beririsan dengan benturan atau kesalahan data.

Pekerjaan mempunyai status antre, berjalan, selesai, atau gagal. Hasil versi baru dipublikasikan bersama seluruh status target dan kandidat dalam satu transaksi. Selama versi baru berjalan atau gagal, hasil versi terakhir yang selesai tetap tersedia. Permintaan ulang dengan kunci operasi yang sama tidak membuat pencarian ganda. Permintaan pemeriksaan ulang yang memakai ID versi kedaluwarsa ditolak.

Pengiriman tugas tidak memerlukan hasil Celery di Redis karena status aplikasi disimpan di database. Jika broker tidak tersedia, pemrosesan lokal hanya dilakukan saat `ALLOW_SYNC_FALLBACK=true`. Jika tidak diizinkan atau pekerjaan gagal, status gagal disimpan dan petugas dapat memeriksa ulang secara eksplisit. Kegagalan tugas lama tidak menimpa status pencarian baru.

Untuk menjalankan aplikasi lokal tanpa Redis, tambahkan `ALLOW_SYNC_FALLBACK=true` di `backend/.env`, lalu mulai ulang backend agar pengaturan terbaca. Pemrosesan cadangan memakai pipeline dan transaksi yang sama, berjalan pada thread terpisah dari event loop HTTP, dan dapat memerlukan beberapa menit untuk data besar. Isi **Petugas untuk riwayat**, lalu klik **Periksa ulang** pada pemeriksaan yang gagal; tidak perlu mengunggah ulang atau memvalidasi ulang PDPJ yang sudah selesai. Pembacaan sumber master dan PDPJ dilakukan bertahap agar seluruh objek sumber tidak dimuat ke memori sekaligus.

Versi pencarian menyimpan `failure_code`: `worker_unavailable` berarti pengiriman ke broker gagal sebelum pemrosesan, sedangkan `processing_failed` berarti pipeline gagal. Penyebab antrean ditampilkan beserta tindakan perbaikan dan tetap tersedia setelah halaman dimuat ulang. Nilai parameter SQL dan isi data pelanggan tidak dicetak ke log kegagalan. Untuk instalasi dengan worker, biarkan fallback nonaktif serta jalankan Redis dan Celery seperti biasa.

## Penyimpanan dan kompatibilitas

Migrasi `f21a85db4e09` menambahkan jenis dataset `idpel_tidak_ketemu` dan `idpel_kosong`, beserta tabel:

| Tabel | Isi |
| --- | --- |
| `correction_checks` | Kategori dan versi PDPJ yang terikat ke proses |
| `correction_attempts` | Kunci operasi dan nama petugas untuk setiap versi pencarian |
| `correction_targets` | Hasil setiap baris per versi, termasuk tanpa koordinat/kandidat |
| `correction_candidate_evidence` | Nilai serta observasi sumber kandidat yang dibekukan |

Proses, versi pencarian, dan kandidat memakai entitas fondasi yang sudah ada. Mapping sumber yang sudah digunakan proses dibekukan. Data asli tidak ditimpa.

Unggahan lama dengan jenis `target` atau `koordinat_kosong` tidak ditebak kategorinya. Data dan riwayatnya tetap tersimpan pada alur lama; untuk kategori baru, unggah berkas ke halaman yang sesuai. Endpoint matching lama tidak dapat dipakai untuk melewati persyaratan PDPJ pada dataset kategori baru.

Nama petugas tetap merupakan label audit pengguna sebagaimana tahap PDPJ. Identitas OIDC belum menjadi bagian implementasi tahap ini.

## API

Gunakan `{kind}` berupa `idpel_tidak_ketemu` atau `idpel_kosong`:

| Endpoint | Fungsi |
| --- | --- |
| `GET /corrections/ready-pdpj` | PDPJ yang pemeriksaan terbarunya selesai |
| `GET /corrections/{kind}/batches` | Berkas pada kategori terpilih |
| `GET /corrections/{kind}/batches/{id}` | Pratinjau dan kelanjutan mapping |
| `GET /corrections/{kind}/checks?batch_id=...` | Daftar pemeriksaan suatu berkas |
| `POST /corrections/{kind}/checks` | Buat dan jalankan pemeriksaan |
| `GET /corrections/{kind}/checks/{id}` | Status aktual dan seluruh versi pencarian |
| `POST /corrections/{kind}/checks/{id}/retry` | Pencarian ulang tanpa menghapus versi lama |
| `GET /corrections/{kind}/summary` | Ringkasan seluruh baris dalam cakupan |
| `GET /corrections/{kind}/records` | Tabel, pencarian, filter, dan pagination |
| `GET /corrections/{kind}/records/{id}` | Data sumber, benturan, dan kandidat tersimpan |

Ringkasan dan daftar menerima `batch_id`, `process_id`, dan `generation`. Detail menerima `process_id` dan `generation`, serta pagination kandidat. Kombinasi kategori/berkas/proses/versi yang tidak sesuai ditolak; hasil kosong tidak dialihkan ke proses lain.

## Verifikasi dan tahap berikutnya

Pengujian backend mencakup kedua kategori, mapping, seluruh baris tanpa koordinat/kandidat, benturan per jenis referensi, peringatan koordinat sama, pelindungan IDPEL PDPJ, kandidat lebih dari lima, snapshot sumber, riwayat radius, permintaan ganda, revisi lama, status antre/gagal, migrasi, dan reset berelasi.

Pengujian browser memakai API dan SQLite sementara. Skenarionya mencakup impor kedua kategori, popup penyelesaian aktual, benturan, detail sumber kandidat, pagination tabel/kandidat, hitungan kartu, navigasi kategori, pemeriksaan ulang radius, versi hasil lama, dan tampilan mobile. Fixture memakai broker lokal yang sengaja tidak tersedia untuk menguji fallback tanpa mengirim pekerjaan ke layanan pengguna.

Perintah pengujian tetap mengikuti [validasi-pdpj.md](validasi-pdpj.md). Integrasi database diuji dengan SQLite; PostgreSQL/PostGIS dan pekerja Celery yang benar-benar terhubung ke broker belum dijalankan pada lingkungan ini.

Tahap 4 sudah diimplementasikan pada [peta-koreksi.md](peta-koreksi.md): seluruh titik sesuai kategori, tooltip hover, pemilihan target dari tabel/titik, pengaturan radius, pemakaian kandidat tersimpan, serta pilihan aktif dan riwayatnya. Tahap berikutnya adalah Hasil Koreksi dan ekspor per kategori.
