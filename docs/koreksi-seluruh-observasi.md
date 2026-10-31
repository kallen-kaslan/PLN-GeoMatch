# Pencarian koreksi dari seluruh observasi koordinat

Pemeriksaan koreksi baru, baik IDPEL Tidak Ketemu maupun IDPEL Kosong, mencari seluruh observasi valid dari sheet/periode PR/PC dan DIL yang sudah dipilih pada PDPJ acuan. Koordinat PDPJ, master gabungan, dan keputusan sebelumnya tetap dipertahankan.

## Aturan pencarian

- Pengecualian IDPEL yang tercakup PDPJ dan pemeriksaan benturan identitas tetap berlaku.
- Setiap observasi koordinat diperiksa dengan jarak Haversine penuh terhadap radius permintaan. Radius tetap dalam meter; pembulatan hanya untuk tampilan hasil baru.
- Setelah pemeriksaan radius, observasi dikelompokkan menurut IDPEL. Satu IDPEL ditampilkan sekali per target menggunakan observasi dengan jarak terdekat.
- Kandidat menyimpan koordinat, ID record sumber, berkas, sheet, baris, periode, dan seluruh observasi sumbernya. Ekspor memakai koordinat dan sumber observasi terpilih.
- Perbedaan lokasi antar sumber lebih dari 50 meter dari observasi terpilih ditampilkan sebagai peringatan untuk ditinjau petugas. Jarak terdekat tidak otomatis membuktikan identitas pelanggan.

## Versi dan proses yang sedang berjalan

`matching_runs.candidate_policy` memisahkan aturan setiap pemeriksaan:

- `1`: satu koordinat acuan per IDPEL, termasuk seluruh pemeriksaan sebelum migrasi. Jeda/lanjut mempertahankan aturan dan checkpoint tersebut.
- `2`: seluruh observasi. Digunakan oleh pemeriksaan baru dan pemeriksaan ulang setelah perubahan ini.

Untuk memakai aturan baru pada proses lama yang baru menyimpan sebagian baris, hentikan sementara sampai bagian aktif tersimpan, lalu pilih **Periksa ulang dengan seluruh observasi** pada Data Koreksi. Sistem membuat generasi baru dari baris pertama, mempertahankan hasil generasi lama, dan menolak lanjut pada generasi yang sudah digantikan. Proses yang masih aktif harus dijeda terlebih dahulu. Tidak perlu unggah ulang atau validasi ulang PDPJ.

Pilihan yang sudah disetujui menyimpan snapshot sendiri. Pemeriksaan baru tidak mengganti IDPEL atau koordinat persetujuan tersebut secara otomatis. Hasil dan ekspor tetap memakai keputusan yang tersimpan sampai petugas memilih perubahan.

## Persiapan dan kinerja

Indeks observasi disiapkan bertahap dari normalisasi sumber yang tersimpan, dengan transaksi dan cursor per bagian. Progres menampilkan jumlah sumber diperiksa serta koordinat kandidat tersimpan; jeda/refresh melanjutkan dari checkpoint. Persiapan awal menambah waktu sebelum pencarian target dimulai.

Indeks dipisahkan menurut snapshot Master Sisa dan digunakan kembali oleh pemeriksaan berikutnya pada snapshot yang sama. Pencarian per bagian mengambil rentang lintang melalui indeks, lalu tetap memeriksa jarak yang sebenarnya. Pemrosesan lokal/worker juga menggunakan bagian terbatas, sehingga tidak memuat semua observasi sebagai objek sekaligus.

Aturan ini mendekati pola pencarian notebook Kaggle. Kesamaan seluruh jumlah hasil tetap memerlukan kesamaan berkas, sheet, mapping, dan pengecualian PDPJ pada kedua sistem.
