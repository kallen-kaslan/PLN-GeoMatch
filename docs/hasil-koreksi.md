# Hasil Koreksi dan Riwayat Proses

Pilihan dari **Peta Koreksi** langsung tersedia di menu **Hasil Rekonsiliasi**
dan **Riwayat Proses**, termasuk ketika pemeriksaan baru selesai sebagian.
Tidak ada penyalinan data atau pemilihan kandidat otomatis saat halaman dibuka.

## Alur penggunaan

1. Jalankan atau lanjutkan pemeriksaan di Data Koreksi.
2. Buka Peta Koreksi untuk baris yang sudah tersimpan, pilih target, isi petugas,
   lalu simpan kandidat pilihan.
3. Klik **Lihat Hasil Koreksi**. Halaman menampilkan kategori, berkas, pemeriksaan,
   versi pencarian, dan PDPJ yang menjadi acuannya.
4. Tinjau target sebelum koreksi, kandidat terpilih, jarak, petugas, waktu,
   versi pilihan, dan bukti sumber. **Riwayat** pada baris membuka jejak perubahan
   target tersebut. **Tampilkan seluruh riwayat** mengembalikan daftar semua target.
5. Gunakan pencarian atau filter: kandidat dipilih, semua baris, belum ada pilihan
   aktif, pilihan dibatalkan, atau belum diproses. Ringkasan menghitung seluruh
   pemeriksaan dan tidak berubah karena pencarian maupun pagination tabel.
6. **Ekspor hasil XLSX** mengekspor sesuai pencarian/filter, secara bawaan hanya
   pilihan aktif. Format polos seperti tabel sumber: nama kolom di baris pertama,
   data mulai baris kedua, tanpa warna, penebalan, filter otomatis, atau pembekuan
   baris. Lebar kolom disesuaikan agar judul mudah dibaca.
7. **Buka Riwayat Proses** menampilkan rekap pemeriksaan serta riwayat keputusan.
   Tautan peta pada proses koreksi membawa kategori, berkas, dan pemeriksaan yang tepat.
   Tombol **XLSX** pada proses mengunduh hasil pilihan aktif secara langsung.
   **Unduh riwayat XLSX** pada panel riwayat mengunduh seluruh perubahan proses,
   atau hanya target yang sedang dipilih, termasuk penggantian dan pembatalan.

Halaman hasil tanpa ID memilih pemeriksaan yang mempunyai pilihan tersimpan
terbaru, kemudian mengikat ID tersebut di URL. Kategori bisa diganti melalui
tab. Pemeriksaan dari alur lama tetap memakai tampilan dan ekspor lama.

Dropdown **Versi radius pemeriksaan** pada Hasil Koreksi memilih hasil radius
tersimpan dalam pemeriksaan yang sama. Tautan dari peta membawa `generation`
yang sedang dibuka. Tabel, pilihan aktif, riwayat, dan ekspor dibatasi hingga
versi tersebut, sehingga keputusan pada radius baru tidak mengubah isi file
historis. Memilih versi lama tidak membuat pemeriksaan baru.

Nama file XLSX memuat radius dan versi, misalnya
`hasil_koreksi_idpel_kosong_4_radius_100m_v1.xlsx` atau
`riwayat_koreksi_idpel_kosong_4_radius_150m_v2.xlsx`. Header unduhan dari server
dipakai agar nama browser mengikuti isi file. Angka desimal radius memakai
garis bawah pada nama file. Status hasil sebagian tetap dicantumkan pada
lembar informasi.

## Sumber hasil dan arti hitungan

- Pilihan aktif adalah keputusan dengan revisi tertinggi untuk satu target pada
  satu pemeriksaan. Mengganti kandidat tidak menambah jumlah target terpilih.
- Pembatalan mengosongkan pilihan aktif; keputusan sebelumnya tetap ada dalam
  riwayat. Belum ada pilihan aktif mencakup target yang dibatalkan atau belum dipilih.
- Satu keputusan menyimpan data target dan snapshot kandidat/bukti saat dipilih.
  Halaman hasil dan XLSX membacanya kembali tanpa mengambil ulang master atau
  mengubah sel asli unggahan.
- Jumlah target diambil dari berkas sumber. Baris tersimpan dan hasil pencarian
  dibaca dari versi pemeriksaan, termasuk saat `current_generation` masih nol.
  Baris yang belum diproses dihitung terpisah dari hasil tanpa kandidat.
- Hasil sebagian diberi label sampai seluruh pemeriksaan selesai. Pemeriksaan
  selesai tidak otomatis berarti semua target sudah mempunyai pilihan kandidat.
- Melanjutkan pemeriksaan mempertahankan pilihan yang sudah tersimpan.
  Perluasan radius membuat versi pencarian baru, sementara pilihan sebelumnya
  tetap terlihat dengan versi asalnya sampai diganti atau dibatalkan.
- Riwayat mencatat pemilihan, penggantian, pembatalan, revisi, versi, petugas,
  alasan, dan waktu. Hasil tidak mencampur keputusan dari pemeriksaan/kategori lain.

## Susunan XLSX

Sheet utama **Hasil Koreksi** memuat kolom berikut secara berurutan:

| Kolom | Isi |
| --- | --- |
| `noagenda` | Nomor agenda target asli sesuai mapping; tidak diganti nomor meter |
| `idpelanggan` | IDPEL kandidat yang disetujui; kosong untuk baris tanpa pilihan aktif |
| `verif` | Nilai verif target asli; tidak diubah menjadi status persetujuan |
| `jenispelanggan` | Jenis pelanggan kandidat; memakai nilai target jika tidak tersedia |
| `latitudey` | Latitude target sebelum koreksi |
| `longitudex` | Longitude target sebelum koreksi |
| `sumber file (sheet)` | Nama berkas dan sheet observasi dengan koordinat kandidat pilihan |
| `sel (baris ke berapa)` | Nomor baris asli pada sheet master tersebut, termasuk baris header |
| `x_acc` | Longitude (bujur/X) kandidat yang disetujui |
| `y_acc` | Latitude (lintang/Y) kandidat yang disetujui |

Jika beberapa observasi memiliki koordinat yang sama, sumber utama kandidat
dipakai bila identitas barisnya tersedia dan koordinatnya cocok. Jika koordinat
berasal dari pelengkapan sumber lain, seluruh bukti dengan pasangan koordinat
yang cocok dicantumkan, dipisahkan baris baru. Sumber dengan koordinat berbeda
tidak ditampilkan sebagai sumber koordinat yang disetujui. Sumber yang tidak
tercatat dibiarkan kosong, tidak ditebak dari master saat ini.

Sheet **Data Target** menyimpan IDPEL awal, atribut, koordinat, nama file/sheet,
dan baris target. **Observasi Sumber** memuat seluruh bukti kandidat dengan
penanda `koordinat_dipakai`. **Keputusan Aktif** menyertakan status, versi,
revisi, petugas, waktu UTC, alasan, dan jarak. **Informasi** menjelaskan kolom
serta cakupan filter/pencarian, radius, versi, dan status pemeriksaan. Lembar
**Pemeriksaan Radius** memuat status pencocokan dan jumlah kandidat setiap
target yang diekspor pada radius versi terpilih. **Keputusan Aktif** juga
mencantumkan `radius_pilihan_meter`, karena pilihan yang dipertahankan dapat
berasal dari radius sebelumnya. Ekspor riwayat menggunakan sheet
**Riwayat Pilihan**: sepuluh kolom utama ditambah baris target, IDPEL awal,
status, versi, revisi, petugas, waktu UTC, alasan, dan radius saat pilihan
disimpan pada setiap kejadian.

IDPEL, nomor agenda, dan koordinat ditulis sebagai teks XLSX agar nol di depan
dan digit desimal tetap utuh tanpa pembulatan tambahan. Teks seperti `=SUM(...)`
tetap teks, tidak dijalankan sebagai formula. Nilai tersimpan tidak diubah.
XLSX ditulis per baris; keluaran besar memakai file sementara sebelum dikirim.

## API

| Endpoint | Isi |
| --- | --- |
| `GET /corrections/{kind}/checks/{id}/results` | Ringkasan dan hasil dengan pencarian, filter, pagination |
| `GET /corrections/{kind}/checks/{id}/results/history` | Jejak keputusan, opsional `record_id` |
| `GET /corrections/{kind}/checks/{id}/results/export` | XLSX sesuai pencarian dan filter |
| `GET /corrections/{kind}/checks/{id}/results/history/export` | XLSX seluruh riwayat, opsional `record_id` |
| `GET /history/processes` | Rekap proses lama dan koreksi, termasuk pilihan serta progres sebagian |

Hasil dan ekspor menerima `generation` opsional: pilihan yang terbaca adalah
revisi terakhir sampai versi tersebut. Riwayat tetap memuat seluruh perubahan.
Endpoint ringkasan/ekspor lama `/process/{id}/summary` dan `/process/{id}/export`
meneruskan proses koreksi ke sumber hasil yang sama. Proses lama menerima
`format=xlsx` dari UI; pemanggil CSV lama tetap kompatibel tanpa parameter ini.

Frontend memperbarui hasil dan riwayat secara berkala; penyimpanan pilihan
menginvalidasi cache agar hasil langsung dibaca saat berpindah dari peta.
