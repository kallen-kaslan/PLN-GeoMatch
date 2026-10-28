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
6. **Ekspor hasil CSV** mengekspor sesuai pencarian/filter, secara bawaan hanya
   pilihan aktif. CSV memuat kolom target sebelum koreksi dan kandidat terpilih
   secara terpisah, jarak, versi/revisi, petugas, waktu UTC, alasan, dan bukti sumber.
7. **Buka Riwayat Proses** menampilkan rekap pemeriksaan serta riwayat keputusan.
   Tautan peta pada proses koreksi membawa kategori, berkas, dan pemeriksaan yang tepat.

Halaman hasil tanpa ID memilih pemeriksaan yang mempunyai pilihan tersimpan
terbaru, kemudian mengikat ID tersebut di URL. Kategori bisa diganti melalui
tab. Pemeriksaan dari alur lama tetap memakai tampilan dan ekspor lama.

## Sumber hasil dan arti hitungan

- Pilihan aktif adalah keputusan dengan revisi tertinggi untuk satu target pada
  satu pemeriksaan. Mengganti kandidat tidak menambah jumlah target terpilih.
- Pembatalan mengosongkan pilihan aktif; keputusan sebelumnya tetap ada dalam
  riwayat. Belum ada pilihan aktif mencakup target yang dibatalkan atau belum dipilih.
- Satu keputusan menyimpan data target dan snapshot kandidat/bukti saat dipilih.
  Halaman hasil dan CSV membacanya kembali tanpa mengambil ulang master atau
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

CSV mempertahankan teks IDPEL pada berkas. Saat mengimpor ke spreadsheet,
pilih tipe teks untuk kolom IDPEL agar nol di depan tetap terlihat. Sel teks
yang berpotensi ditafsirkan sebagai formula diberi awalan apostrof pada ekspor;
nilai tersimpan di database tetap utuh.

## API

| Endpoint | Isi |
| --- | --- |
| `GET /corrections/{kind}/checks/{id}/results` | Ringkasan dan hasil dengan pencarian, filter, pagination |
| `GET /corrections/{kind}/checks/{id}/results/history` | Jejak keputusan, opsional `record_id` |
| `GET /corrections/{kind}/checks/{id}/results/export` | CSV sesuai pencarian dan filter |
| `GET /history/processes` | Rekap proses lama dan koreksi, termasuk pilihan serta progres sebagian |

Hasil dan ekspor menerima `generation` opsional: pilihan yang terbaca adalah
revisi terakhir sampai versi tersebut. Riwayat tetap memuat seluruh perubahan.
Endpoint ringkasan/ekspor lama `/process/{id}/summary` dan `/process/{id}/export`
meneruskan proses koreksi ke sumber hasil yang sama; proses lama tetap kompatibel.

Frontend memperbarui hasil dan riwayat secara berkala; penyimpanan pilihan
menginvalidasi cache agar hasil langsung dibaca saat berpindah dari peta.
