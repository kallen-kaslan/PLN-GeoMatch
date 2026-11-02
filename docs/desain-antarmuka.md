# Antarmuka ruang kerja PLN GeoMatch

Pembaruan 2 November 2026 mengganti presentasi neo-brutalism dengan ruang kerja pemeriksaan yang lebih tenang. Perubahan berada pada frontend; kontrak API, sumber data, algoritma pencocokan, checkpoint, keputusan, dan format ekspor tetap digunakan.

## Fondasi visual

- Revisi palet memakai indigo, biru, dan violet: latar aplikasi `#F2F4F9`, area data putih, teks utama `#24314B`, teks pendukung `#5D6B83`, divider `#DCE3EF`. Palet ini menggantikan fondasi oranye dan grafit sebelumnya.
- Sidebar indigo `#1C2946`, menu aktif `#334872` dengan garis violet terang `#BEB4FF`. Logo memakai violet `#6A58C5`; tombol utama biru `#4256BE`, dengan hover `#35479F`. Panel konteks berkas, versi, dan pemeriksaan memakai lavender tipis `#EEF1FC`, sedangkan tabel tetap putih dengan header `#F0F3FA`.
- Warna identitas dipisahkan dari status: hijau untuk temuan positif, amber untuk perhatian, dan merah untuk masalah. Angka ringkasan di atas nol diberi warna sesuai kategorinya; angka nol tetap netral. Total utama memakai biru. Warna titik peta dan aturan legendanya dipertahankan.
- Border utama 1 px, radius kontrol 6 px, radius panel 8 px. Bayangan keras dan efek tombol timbul dihapus; bayangan lembut dipertahankan untuk elemen melayang.
- Font sistem Segoe UI/system-ui dan Cascadia Code/Consolas untuk identitas dan koordinat. Pilihan ini tidak memerlukan unduhan font atau permintaan jaringan tambahan. Tabel memakai 13 px, metadata 12 px, judul halaman sekitar 26 px.
- Target sentuh minimal 44 px pada perangkat dengan pointer kasar. Fokus keyboard terlihat dan reduced motion dihormati.

Token Tailwind berada di `frontend/src/index.css`, dengan konfigurasi kompatibel di `frontend/tailwind.config.js`. Komponen lama dipindahkan dari `border-neo-border` dan `text-neo-border` ke token border serta teks pendukung yang terpisah, sehingga divider ringan tidak membuat teks ikut terlalu pucat.

## Struktur aplikasi

Topbar 56 px memuat identitas aplikasi, konteks halaman, dan menu akun. Animasi dekoratif yang tidak mewakili status server dihapus.

Sidebar desktop 240 px dapat diperkecil menjadi 64 px. Navigasi dikelompokkan menjadi Data, Pemeriksaan, dan Hasil. Menu admin tetap mengikuti peran pengguna. Pada mobile, navigasi memakai dialog native agar fokus keyboard terkurung dan Escape menutup menu. Perpindahan route atau ukuran desktop menutup drawer.

Navigasi gelap menjadi pembatas ruang kerja. Panel pengaturan diberi tint ringan untuk membedakannya dari data yang sedang diperiksa. Teks tombol utama terhadap latarnya memiliki kontras 6,35:1; label pada panel konteks 4,78:1; teks navigasi 10,58:1; dan menu aktif 9,09:1. Pengukuran ini berlaku untuk pasangan warna tersebut, bukan audit aksesibilitas menyeluruh.

Konten aplikasi memiliki scroll sendiri agar navigasi tetap tersedia. Halaman peta memperoleh ruang lebih luas. Route dan tautan lama tetap berfungsi.

## Pemeriksaan data

Data PDPJ menempatkan berkas, petugas, versi, dan aksi pemeriksaan dalam satu baris konteks pada desktop. Pilihan sumber master tetap tersedia melalui rincian sumber.

Kartu jumlah data memakai komponen `MetricCard` bersama pada Dashboard, Master, PDPJ, Koreksi, Peta, Hasil, Kandidat, dan Admin. Setiap kartu memiliki label yang sejajar, angka tabular, garis aksen pendek, ikon kecil pada bidang lembut, serta bayangan ringan. Total utama memakai tint biru; temuan lain menggunakan warna status. Halaman dengan enam atau delapan metrik memakai kartu ringkas, dengan ikon disembunyikan pada kartu sempit agar angka tidak bertumpuk. Tampilan mobile memakai dua kolom. Kartu tidak memiliki efek mengambang saat hover karena bukan tombol. Ringkasan radius tetap memakai elemen definisi `dt` dan `dd`.

Detail PDPJ dan Koreksi memakai `InspectionDrawer` bersama. Detail dibuka di sisi kanan, memiliki fokus modal dan dukungan Escape, lalu mengembalikan fokus serta posisi tabel ketika ditutup. Isi perbandingan nilai, rekomendasi per kolom, pengisian manual, pengecualian, bukti, dan riwayat tetap tersedia. Menutup detail tidak menjalankan tindakan penyimpanan.

Panel progres mempertahankan pengamat aktivitas server, polling, revisi, dan penghentian setelah transaksi aktif selesai. Jumlah baris tersimpan, validasi akhir, posisi baris terakhir, dan durasi tetap terlihat. Rincian persiapan master serta penjelasan penyimpanan dapat dibuka tanpa selalu mendominasi layar. Pemeriksaan selesai tidak otomatis berarti petugas sudah menyetujui hasil. Nama petugas PDPJ dipertahankan dalam sesi tab agar refresh tidak menghapus isian.

## Ruang kerja peta

Pada desktop lebar, peta dan dock target berada di kiri; panel inspeksi target serta kandidat berada di kanan. Dock target dapat diciutkan dan area tabel dapat diubah tingginya. Kandidat ditampilkan dalam satu kolom dengan identitas, jarak, koordinat, dan sumber terpilih; nilai lengkap tetap tersedia melalui rincian kandidat.

Pada layar sempit tersedia tab Peta, Daftar, dan Detail, dengan navigasi keyboard panah, Home, dan End. Memilih target dari daftar atau titik langsung mengarahkan tampilan ke Peta dan memuat kandidat tersimpan secara otomatis. Panel target dan kandidat tersedia di bawah peta pada mobile; desktop tetap memakai panel berdampingan. Tombol Tampilkan kandidat target dihapus. Pergantian radius dan versi memperbarui kandidat otomatis, serta mengembalikan pagination kandidat ke halaman yang sesuai. Tab tersimpan pada URL bersama target, versi, dan radius sehingga dapat dipulihkan setelah refresh. Penyedia Leaflet yang sudah ada tetap mengamati perubahan ukuran kontainer. Tile dasar OpenStreetMap tetap memerlukan koneksi sebagaimana sebelumnya.

Pemuatan kandidat hanya membaca baris pada versi dan radius yang dipilih; tidak menjalankan pemeriksaan baru maupun menyimpan pilihan. Status memuat, kegagalan, dan target yang belum tersedia ditampilkan terpisah dari hasil tanpa kandidat. Target tanpa koordinat, berbenturan dengan PDPJ, atau bermasalah tidak memicu permintaan kandidat. Memilih kandidat tetap merupakan aksi persetujuan tersendiri.

Tombol **Lepas pilihan target** menghapus sorotan baris, titik aktif, dan tampilan kandidat, lalu mengembalikan fokus ke daftar target. Berkas, proses, versi, radius, pencarian, filter, dan halaman tabel dipertahankan. ID target dihapus dari URL sehingga refresh tidak memilihnya kembali. Tindakan ini tidak membatalkan keputusan kandidat tersimpan; pembatalan keputusan tetap memakai **Batalkan pilihan** beserta aturan alasannya. Pelepasan target tersedia setelah permintaan penyimpanan atau perluasan yang sedang aktif selesai.

Filter radius hanya membaca hasil dalam cakupan versi tersimpan. Perluasan tetap merupakan aksi terpisah untuk seluruh berkas, dengan kontrol yang dibuka secara eksplisit. Pemilihan kandidat tetap memerlukan nama petugas dan aturan alasan perubahan yang sama. Versi historis tetap hanya dapat dibaca.

## Dashboard dan halaman lain

Dashboard memakai riwayat yang sebenarnya untuk menunjukkan pekerjaan yang belum selesai ditinjau. Kegagalan memuat data ditampilkan sebagai kesalahan, bukan angka nol. Jumlah baris dijelaskan sebagai gabungan seluruh pemeriksaan, termasuk pemeriksaan ulang, bukan pelanggan unik.

Master, Hasil, Riwayat, Login, Admin, dan halaman pencocokan lama mengikuti token, kontrol, tabel, dan hierarki tipografi yang sama. Berkas XLSX dan nilai sumber tidak diformat ulang oleh perubahan tema.

## Validasi

Pengujian antarmuka menggunakan server dan database terisolasi. Skenario desain memeriksa drawer dan pengembalian fokus, nilai koordinat yang tetap utuh, posisi tabel, peta dan inspector berdampingan, tab mobile, overflow horizontal, navigasi mobile, serta perubahan viewport. Pengujian alur lama mencakup pemeriksaan PDPJ, koreksi, radius berversi, persetujuan, hasil sebagian, refresh, dan ekspor.
