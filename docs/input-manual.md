# Input Manual

Menu **Input Manual & Matching** (`/process`) memasukkan satu titik lapangan ke
alur Data Koreksi. Isi nama sesi, referensi survei/ID titik, Latitude (Y),
Longitude (X), dan radius. IDPEL awal, nomor agenda, serta nomor meter bersifat
opsional. Koordinat menerima tanda desimal titik maupun koma.

Klik **Simpan & Buka Data Koreksi**. IDPEL awal yang kosong masuk kategori
**IDPEL Kosong**; IDPEL yang terisi masuk kategori **IDPEL Tidak Ketemu**.
Referensi titik dipetakan sebagai referensi survei, terpisah dari nomor meter.
Data disimpan sebagai satu baris sumber dengan identitas dan nol di depan tetap
utuh. Tombol dinonaktifkan selama penyimpanan dan validasi.

Di Data Koreksi, pilih versi PDPJ yang selesai divalidasi, isi petugas untuk
riwayat, lalu jalankan pemeriksaan. Radius dari formulir manual diteruskan ke
halaman tersebut. Pemeriksaan menggunakan sumber master pada versi PDPJ yang
dipilih serta progres dan kontrol jeda/lanjut yang sama dengan unggahan koreksi.
Semua kandidat dalam radius dapat ditinjau.

Buka Peta Koreksi untuk memilih kandidat. Pilihan dan perubahannya tersimpan
dalam riwayat keputusan. Hasil Koreksi dan Riwayat Proses menggunakan ekspor
standar: satu sheet **Hasil Koreksi**, tanpa `verif`, dengan `y_akhir` dan
`x_akhir`. Lihat [format hasil](hasil-koreksi.md).

Untuk pemeriksaan banyak titik dari berkas, gunakan tautan kategori Data Koreksi
di atas formulir. Proses manual baru menggunakan alur kategori ini; proses lama
yang telah tersimpan tetap dapat dibuka melalui riwayat.
