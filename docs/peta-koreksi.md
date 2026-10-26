# Tahap 4: Peta Koreksi

Halaman `/peta-koreksi` melanjutkan [Data Koreksi](data-koreksi.md). Halaman ini tersedia melalui sidebar dan tautan **Buka Peta Koreksi** pada pemeriksaan yang sudah mempunyai hasil. Kategori, berkas, pemeriksaan, dan versi hasil tetap menjadi cakupan eksplisit.

## Interaksi

- Pilih kategori IDPEL Tidak Ketemu atau IDPEL Kosong, berkas, lalu pemeriksaan.
- Seluruh target berkoordinat dimuat, terpisah dari pagination tabel 25 baris. Target tanpa koordinat tetap ada di tabel dan hitungan, tanpa titik buatan.
- Hover titik memperlihatkan nama, IDPEL jika tersedia, nomor baris, dan jumlah kandidat. Tooltip menghilang saat kursor berpindah.
- Klik target di tabel atau peta untuk menyorot target. Titik lain menjadi abu-abu. Target pada koordinat sama menyediakan daftar baris pada popup yang dapat digulir.
- Tombol kandidat baru aktif setelah target yang memenuhi syarat dipilih. Target berbenturan PDPJ, data tidak valid, dan koordinat belum lengkap tidak dapat dicari melalui tombol ini.
- Setelah tombol ditekan, kandidat muncul pada peta dan kartu detail di bawahnya. Peta memuat seluruh kandidat, sedangkan kartu memakai pagination 10 kandidat. Popup kandidat mengarahkan pengguna ke kartu yang sesuai, termasuk halaman kandidat lain.
- Detail memperlihatkan data target, kandidat, jarak dari koordinat awal, serta seluruh observasi sumber master yang disimpan saat pemeriksaan.

Pencarian tabel menyaring daftar tanpa membatasi titik seluruh berkas. Kandidat baru diperlihatkan setelah tombol ditekan; mengubah target atau radius menyembunyikan hasil pemetaan sebelumnya sampai pengguna menekan tombol lagi.

## Radius dan versi

Radius hingga cakupan versi terpilih menyaring kandidat tersimpan melalui `radius_meters` pada endpoint detail. Pembacaan ini tidak memuat ulang tabel master. Permintaan radius melebihi cakupan versi ditolak oleh API pembacaan.

Untuk memperbesar radius melampaui cakupan, tombol menjelaskan bahwa pemeriksaan akan diperluas. Implementasi memakai pencarian ulang **seluruh berkas** yang sudah tersedia pada tahap 3, bukan pekerjaan tersembunyi per titik. Hasil disimpan sebagai versi baru dengan master dan PDPJ yang tetap terikat. Status aktual dipantau sampai selesai; versi sebelumnya tetap dapat dibaca saat pekerjaan berjalan atau gagal.

Pilihan aktif tetap tersimpan ketika radius berubah atau versi baru diterbitkan. Ringkasan pilihan menampilkan versi dan jarak asalnya, termasuk ketika kandidat tersebut berada di luar radius tampilan terbaru. Versi historis dapat dipetakan tetapi pilihan tidak dapat diubah dari versi tersebut.

## Pilihan dan audit

Migrasi `a4b19c7e6201` menambahkan tabel `correction_decisions`. Setiap perubahan menambah satu kejadian yang berisi:

- Pemeriksaan, target, versi pencarian, revisi pilihan, dan kandidat terpilih atau pembatalan.
- Snapshot data target sebelum koreksi serta kandidat lengkap dengan jarak dan sumbernya.
- Label petugas, alasan, waktu UTC, dan kunci permintaan untuk pengiriman ulang yang idempoten.

Kejadian dengan revisi tertinggi merupakan keadaan pilihan aktif. Setiap target mempunyai paling banyak satu pilihan aktif dalam satu pemeriksaan. Mengganti atau membatalkan pilihan memerlukan alasan. Histori sebelumnya tidak ditimpa. Pemilihan kandidat dari target, kategori, pemeriksaan, atau versi lain ditolak. Permintaan dengan revisi lama juga ditolak; UI memuat ulang pilihan agar pengguna dapat meninjau perubahan.

Saat pencarian baru masih antre/berjalan, perubahan pilihan ditolak. Endpoint keputusan massal/tunggal, pencarian ulang, dan finalisasi pada alur lama tidak dapat dipakai untuk melewati audit kategori koreksi baru. Alur target lama tetap tersedia melalui rutenya.

Identitas petugas masih memakai label pengguna seperti tahap PDPJ. Aturan satu IDPEL master untuk beberapa target berbeda belum ditetapkan; tahap ini membatasi satu pilihan per target, belum keunikan IDPEL di seluruh hasil.

## API

| Endpoint | Fungsi |
| --- | --- |
| `GET /corrections/{kind}/records/{record_id}?process_id=...&generation=...&radius_meters=...` | Kandidat tersimpan dalam radius, dengan pagination |
| `GET /corrections/{kind}/checks/{process_id}/records/{record_id}/choice` | Pilihan aktif dan riwayat lintas versi |
| `POST /corrections/{kind}/checks/{process_id}/records/{record_id}/choice` | Pilih/ganti/batalkan dengan `generation`, `expected_revision`, `candidate_id`, `actor`, `reason`, dan `request_key` |

Pengiriman `candidate_id: null` membatalkan pilihan. Pembacaan riwayat selalu menyajikan pilihan aktif terkini dan seluruh revisi, meskipun peta sedang menampilkan pencarian historis; UI memberi label pembanding dan menonaktifkan perubahan.

## Renderer dan verifikasi

`MapProvider` membatasi integrasi peta di `frontend/src/lib/correction-map.ts`. Implementasi mempertahankan Leaflet yang sudah digunakan proyek. Distribusi 1.9.4, lisensi BSD, CSS, dan ikon disimpan di `frontend/public/vendor/leaflet-1.9.4`; JavaScript/CSS tetap memakai hash SRI resmi pada HTML. Tile OpenStreetMap memerlukan internet. Apabila renderer gagal dimuat, pesan tampil dan alur tabel/pilihan tetap tersedia. Isi tooltip dan popup dibuat dengan `textContent`, sehingga data sumber tidak ditafsirkan sebagai HTML.

Pengujian backend mencakup penggunaan snapshot tanpa pembacaan master, batas radius, satu pilihan aktif, penggantian/pembatalan, snapshot audit, idempotensi, revisi lama, cakupan yang salah, pencarian berjalan, perluasan radius, versi historis, pelindungan endpoint lama, migrasi, dan reset dengan foreign key aktif. Pengujian browser memakai API dan database sementara untuk tooltip, titik bertumpuk, seluruh titik di luar halaman tabel, kedua kategori, kartu kandidat, pilihan dan riwayat, perluasan/pengurangan radius, tampilan historis, serta mobile ketika renderer tidak tersedia.

Tahap 5 berikutnya adalah **Hasil Koreksi** per kategori dan ekspor berdasarkan pilihan aktif, dengan perbandingan data sebelum/sesudah serta riwayat kandidat. Halaman hasil lama belum diganti pada tahap ini.
