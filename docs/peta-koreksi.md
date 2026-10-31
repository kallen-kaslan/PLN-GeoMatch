# Tahap 4: Peta Koreksi

Halaman `/peta-koreksi` melanjutkan [Data Koreksi](data-koreksi.md). Halaman ini tersedia melalui sidebar dan tautan **Buka Peta Koreksi** setelah ada baris pemeriksaan yang tersimpan, tanpa menunggu seluruh pemeriksaan selesai. Kategori, berkas, pemeriksaan, dan versi hasil tetap menjadi cakupan eksplisit.

Untuk pemeriksaan bertahap, peta memakai versi terbaru dan hanya memuat baris
yang sudah disimpan (`saved_only=true`). Jumlah tersedia dan jumlah seluruh
baris ditampilkan. Kandidat pada baris tersebut dapat ditinjau dan dipilih saat
pemeriksaan berjalan, dijeda, atau terhenti. Baris baru otomatis tersedia setelah
checkpoint bertambah. Pilihan tetap tersimpan saat pemeriksaan dilanjutkan dari
Data Koreksi; proses, versi, kandidat lama, dan riwayat pilihan dipertahankan.
Baris belum diperiksa belum masuk tahap peta. Perluasan radius menunggu seluruh
pemeriksaan selesai; radius dalam cakupan tersimpan tetap dapat digunakan.

## Interaksi

- Pilih kategori IDPEL Tidak Ketemu atau IDPEL Kosong, berkas, lalu pemeriksaan.
- Seluruh target berkoordinat dimuat, terpisah dari pagination tabel. Preview memakai kontrol yang sama dengan PDPJ: pilihan 10/25/50/100 baris, input nomor halaman, Enter atau **Buka halaman**, rentang baris, dan navigasi sebelumnya/berikutnya. Perubahan pencarian, filter hasil, radius, atau jumlah baris kembali ke halaman pertama. Target tanpa koordinat tetap ada di tabel dan hitungan, tanpa titik buatan.
- Hover titik memperlihatkan nama, IDPEL jika tersedia, nomor baris, dan jumlah kandidat. Tooltip menghilang saat kursor berpindah.
- Klik target di tabel atau peta untuk menyorot target. Titik lain menjadi abu-abu. Target pada koordinat sama menyediakan daftar baris pada popup yang dapat digulir.
- Tombol kandidat baru aktif setelah target yang memenuhi syarat dipilih. Target berbenturan PDPJ, data tidak valid, dan koordinat belum lengkap tidak dapat dicari melalui tombol ini.
- Tombol perluasan radius seluruh berkas dapat dijalankan tanpa memilih target. Pemilihan target hanya diperlukan untuk menampilkan atau menyetujui kandidat per baris.
- Setelah tombol ditekan, kandidat muncul pada peta dan kartu detail di bawahnya. Peta memuat seluruh kandidat, sedangkan kartu memakai pagination 10 kandidat. Popup kandidat mengarahkan pengguna ke kartu yang sesuai, termasuk halaman kandidat lain.
- Detail memperlihatkan data target, kandidat, jarak dari koordinat awal, serta seluruh observasi sumber master yang disimpan saat pemeriksaan.

Pencarian tabel menyaring daftar tanpa membatasi titik seluruh berkas. Kandidat baru diperlihatkan setelah tombol ditekan; mengubah target atau radius menyembunyikan hasil pemetaan sebelumnya sampai pengguna menekan tombol lagi.

Ringkasan radius membaca hasil Data Koreksi yang sudah tersimpan. Kartu
menampilkan total baris, baris tersimpan, baris dengan/tanpa kandidat, belum
diperiksa, benturan PDPJ, data bermasalah, koordinat belum lengkap, dan jumlah
kandidat. Jumlah kandidat berbeda dari jumlah baris yang mempunyai kandidat.
Filter hasil berlaku pada tabel dan titik peta, termasuk untuk menemukan semua
baris **Tanpa kandidat dalam radius**.

Mengubah radius di dalam cakupan tersimpan otomatis memperbarui ringkasan,
status baris, jumlah kandidat per baris, dan informasi titik dari kandidat yang
memenuhi radius tersebut. Pembacaan ini tidak membuat versi baru atau mengubah
pilihan petugas. Target yang mempunyai kandidat pada radius besar dapat menjadi
tanpa kandidat pada radius kecil; benturan dan data bermasalah tetap terpisah.
Filter hasil dan radius ikut dipulihkan dari URL setelah refresh.

**Filter radius** dibatasi maksimal radius versi tersimpan yang dipilih. Jika
versi tersebut 100 m, input di atas 100 m dikembalikan ke 100 m dan disertai
pesan batas. URL lama yang membawa radius di atas batas juga ditampilkan pada
batas tersimpan. Mengedit filter tidak membuat pemeriksaan baru.

Untuk pemeriksaan lebih luas, gunakan input terpisah **Radius perluasan** dan
tombol perluasan seluruh berkas. Radius baru wajib lebih besar dari radius
versi terbaru, maksimum 100.000 m, dan nama petugas wajib terisi. Perluasan
tersedia pada versi terbaru setelah pemeriksaan aktif selesai. Draf radius
perluasan tidak mengubah filter atau hasil tampilan. Setelah proses baru
dibuat, filter dan batasnya mengikuti radius versi baru tersebut.

Jika radius lebih besar daripada cakupan tersimpan, hasil belum dianggap
tersedia sebelum perluasan dijalankan. Begitu versi baru dibuat, peta utama
hanya menampilkan **satu ringkasan radius terbaru**, termasuk hitungan sementara
dari checkpoint versi baru. Tabel dan titik juga memakai baris tersimpan pada
versi terbaru; hasil radius lama tidak ditampilkan sebagai cadangan. Baris yang
belum diperiksa tidak dimasukkan sebagai tanpa kandidat. Saat belum ada baris
versi baru tersimpan, peta menjelaskan bahwa target masih menunggu pemeriksaan.
Perbandingan menyebut jumlah tanpa kandidat pada radius versi sebelumnya dan
jumlah baris tersebut yang kini sudah memperoleh kandidat. Misalnya, dari
80 baris tanpa kandidat pada 100 m, hanya baris yang benar-benar ditemukan pada
hasil 150 m yang dihitung sebagai baru memperoleh kandidat.

## Radius dan versi

Radius hingga cakupan versi terpilih menyaring kandidat tersimpan melalui `radius_meters` pada endpoint detail. Pembacaan ini tidak memuat ulang tabel master. Permintaan radius melebihi cakupan versi ditolak oleh API pembacaan.

Dropdown **Versi radius pemeriksaan** menampilkan seluruh versi pada pemeriksaan
yang sama, misalnya `100 m · Versi 1 · Selesai` dan `150 m · Versi 2 · Selesai`.
Secara bawaan peta mengikuti versi terbaru. Memilih versi lain mengubah radius,
ringkasan, tabel, kandidat, serta riwayat pilihan hingga versi tersebut tanpa
menjalankan pencarian baru. Pilihan versi disimpan pada URL dan pulih setelah
refresh. Versi historis hanya dapat dibaca; kembali ke versi terbaru untuk
menyimpan pilihan baru atau memperluas radius.

Filter radius pada hasil yang sudah selesai tetap aktif, termasuk saat versi
radius yang lebih baru sedang diproses. Ringkasan dan kandidat dapat disaring
dalam cakupan radius versi selesai tersebut tanpa memulai pemeriksaan baru.
Perubahan keputusan dan perluasan baru tetap mengikuti batas versi terbaru.

**Unduh hasil radius … m XLSX** mengekspor seluruh hasil versi radius tersimpan
yang dipilih. Filter radius tampilan yang lebih kecil tidak mengubah radius
pemeriksaan pada ekspor. Nama file memuat kategori, proses, radius, dan versi,
misalnya `hasil_koreksi_idpel_kosong_4_radius_100m_v1.xlsx`. Lembar utama tetap
polos dengan sepuluh kolom yang disepakati. **Informasi** mencantumkan radius,
versi, dan status; **Pemeriksaan Radius** mencantumkan status serta jumlah
kandidat setiap target pada versi tersebut. Tautan Hasil Koreksi dan Riwayat
Proses membawa pilihan versi yang sama.

Untuk memperbesar radius melampaui cakupan, tombol menjelaskan bahwa pemeriksaan akan diperluas. Implementasi memakai pencarian ulang **seluruh berkas** yang sudah tersedia pada tahap 3, bukan pekerjaan tersembunyi per titik. Hasil disimpan sebagai versi baru dengan master dan PDPJ yang tetap terikat. Status aktual dipantau sampai selesai; versi sebelumnya tetap dapat dibaca saat pekerjaan berjalan atau gagal.

Perluasan dari peta memakai pemeriksaan bertahap (`incremental=true`) yang sama
dengan Data Koreksi. Panel menampilkan versi, radius seluruh berkas, tahap
persiapan/pencocokan/validasi/penyelesaian, persentase, jumlah baris tersimpan,
posisi terakhir, durasi kerja, dan animasi ketika bagian aktif sedang diproses.
Panel pemeriksaan di peta hanya tampil untuk perluasan radius yang belum
selesai. Pemeriksaan awal tetap dipantau untuk memperbarui ringkasan tanpa
menampilkan rincian pemeriksaan. Setelah perluasan selesai,
peta menampilkan ringkasan hasil radius tanpa panel pemeriksaan 100% dan
rincian persiapan master. Rincian lengkap tetap tersedia di Data Koreksi.
Hasil sebagian versi terbaru langsung tersedia di peta. Pilihan sebelumnya
tetap disimpan dan ditampilkan ketika baris targetnya tersedia pada versi baru.
Versi terdahulu tetap bisa dibaca melalui tautan historis yang eksplisit.

Pencocokan bertahap memakai pembanding PDPJ ringkas yang dipakai ulang selama
versi/revisi PDPJ dan interpretasi sumbernya sama. Cache dibatasi satu versi
per engine database dan tidak menyimpan ORM atau seluruh bukti sumber. Data
lengkap hanya dimuat untuk benturan yang nyata pada bagian aktif. Publikasi
sebagian tetap mencadangkan baris sumber yang belum diperiksa sesuai posisi
publikasi, meskipun pemeriksaan PDPJ asal dilanjutkan. Versi atau revisi yang
berubah membangun pembanding baru; reset unggahan membersihkan cache. Setelah
backend dimulai ulang, pembanding dibangun lagi pada pemakaian pertama.
Radius, perhitungan jarak, urutan kandidat, dan aturan benturan tetap sama.

Estimasi adalah **perkiraan waktu kerja tersisa untuk tahap aktif**, bukan
janji waktu selesai seluruh pemeriksaan. Estimasi memakai jumlah baris dan
durasi tahap yang sudah diukur dan tersimpan. Waktu persiapan dan waktu jeda
tidak dicampur ke kecepatan pencocokan. Sebelum tersedia pengukuran tahap,
panel menjelaskan bahwa data belum cukup. Jumlah kandidat dan beban server
dapat mengubah perkiraan. Pekerjaan lama tanpa checkpoint menampilkan animasi
dan waktu sejak permintaan, tanpa persentase atau estimasi buatan.

Kategori, berkas, pemeriksaan, target terpilih, radius, dan permintaan tampil
kandidat disimpan pada URL; label petugas tersimpan dalam sesi browser.
Setelah refresh, kontrol menunggu pemulihan status dari server. Jika bagian
masih aktif, animasi dan tombol jeda tetap tersedia. Jika bagian sudah selesai
tetapi tidak ada penggerak proses aktif, panel menawarkan **Lanjutkan
pemeriksaan koreksi** dari checkpoint tersebut. Refresh tidak membuat versi
pencarian baru. Jeda menunggu bagian aktif tersimpan; proses dapat dilanjutkan
dari peta atau Data Koreksi. Respons status yang lebih lama tidak boleh
menimpa checkpoint terbaru.

Pilihan aktif tetap tersimpan ketika radius berubah atau versi baru diterbitkan. Ringkasan pilihan menampilkan versi dan jarak asalnya, termasuk ketika kandidat tersebut berada di luar radius tampilan terbaru. Versi historis dapat dipetakan tetapi pilihan tidak dapat diubah dari versi tersebut.

## Pilihan dan audit

Migrasi `a4b19c7e6201` menambahkan tabel `correction_decisions`. Setiap perubahan menambah satu kejadian yang berisi:

- Pemeriksaan, target, versi pencarian, revisi pilihan, dan kandidat terpilih atau pembatalan.
- Snapshot data target sebelum koreksi serta kandidat lengkap dengan jarak dan sumbernya.
- Label petugas, alasan, waktu UTC, dan kunci permintaan untuk pengiriman ulang yang idempoten.

Kejadian dengan revisi tertinggi merupakan keadaan pilihan aktif. Setiap target mempunyai paling banyak satu pilihan aktif dalam satu pemeriksaan. Mengganti atau membatalkan pilihan memerlukan alasan. Histori sebelumnya tidak ditimpa. Pemilihan kandidat dari target, kategori, pemeriksaan, atau versi lain ditolak. Permintaan dengan revisi lama juga ditolak; UI memuat ulang pilihan agar pengguna dapat meninjau perubahan.

Pada pemeriksaan bertahap, perubahan pilihan hanya diterima untuk baris yang
sudah tersimpan pada versi terbaru. Versi historis tetap hanya dapat dibaca.
Pencarian lama tanpa checkpoint yang masih antre/berjalan tetap menolak
perubahan pilihan. Endpoint keputusan massal/tunggal, pencarian ulang, dan
finalisasi pada alur lama tidak dapat dipakai untuk melewati audit kategori
koreksi baru. Alur target lama tetap tersedia melalui rutenya.

Identitas petugas masih memakai label pengguna seperti tahap PDPJ. Aturan satu IDPEL master untuk beberapa target berbeda belum ditetapkan; tahap ini membatasi satu pilihan per target, belum keunikan IDPEL di seluruh hasil.

## API

| Endpoint | Fungsi |
| --- | --- |
| `GET /corrections/{kind}/map-summary?process_id=...&generation=...&radius_meters=...` | Hitungan seluruh berkas dan kandidat per target pada radius tersimpan; perbandingan versi serta hasil sebagian tanpa membaca ulang master |
| `GET /corrections/{kind}/records/{record_id}?process_id=...&generation=...&radius_meters=...` | Kandidat tersimpan dalam radius, dengan pagination |
| `GET /corrections/{kind}/checks/{process_id}/records/{record_id}/choice?generation=...` | Pilihan dan riwayat hingga versi terpilih; tanpa generation membaca keadaan terkini |
| `POST /corrections/{kind}/checks/{process_id}/records/{record_id}/choice` | Pilih/ganti/batalkan dengan `generation`, `expected_revision`, `candidate_id`, `actor`, `reason`, dan `request_key` |

Pengiriman `candidate_id: null` membatalkan pilihan. Peta historis membaca
keputusan hingga versi yang dipilih dan menonaktifkan perubahan. Keputusan pada
versi radius yang lebih baru tidak dimasukkan ke tampilan atau ekspor versi lama.

## Renderer dan verifikasi

`MapProvider` membatasi integrasi peta di `frontend/src/lib/correction-map.ts`. Implementasi mempertahankan Leaflet yang sudah digunakan proyek. Distribusi 1.9.4, lisensi BSD, CSS, dan ikon disimpan di `frontend/public/vendor/leaflet-1.9.4`; JavaScript/CSS tetap memakai hash SRI resmi pada HTML. Tile OpenStreetMap memerlukan internet. Apabila renderer gagal dimuat, pesan tampil dan alur tabel/pilihan tetap tersedia. Isi tooltip dan popup dibuat dengan `textContent`, sehingga data sumber tidak ditafsirkan sebagai HTML.

Pengujian backend mencakup penggunaan snapshot tanpa pembacaan master, batas radius, satu pilihan aktif, penggantian/pembatalan, snapshot audit, idempotensi, revisi lama, cakupan yang salah, pencarian berjalan, perluasan radius, versi historis, pelindungan endpoint lama, migrasi, dan reset dengan foreign key aktif. Pengujian browser memakai API dan database sementara untuk tooltip, titik bertumpuk, seluruh titik di luar halaman tabel, kedua kategori, kartu kandidat, pilihan dan riwayat, perluasan/pengurangan radius, tampilan historis, serta mobile ketika renderer tidak tersedia.

**Hasil Koreksi** per kategori dan ekspor pilihan aktif sudah tersedia melalui
tautan **Lihat Hasil Koreksi**, termasuk hasil sebagian. Riwayat Proses membaca
pilihan dan jumlah baris tersimpan dari pemeriksaan yang sama. Perbandingan
target/kandidat, ekspor, dan jejak perubahan dijelaskan di
[hasil-koreksi.md](hasil-koreksi.md). Hasil dari alur lama tetap tersedia.
