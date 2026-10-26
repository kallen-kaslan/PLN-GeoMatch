# Pembacaan koordinat X/Y

Pada beberapa file PLN, `KOORDINAT_X` berisi lintang (misalnya `-6,2`) dan `KOORDINAT_Y` berisi bujur (misalnya `108,5`). Deteksi lama selalu menganggap Y sebagai latitude. Akibatnya, nilai bujur lebih dari 90 ditolak sebagai latitude dan koordinat Y terlihat kosong pada hasil impor.

Formulir sekarang menggunakan label **Latitude (lintang)** dan **Longitude (bujur)**. Deteksi mapping membaca contoh nilai, sehingga pasangan X/Y dengan urutan tersebut dipetakan sebagai latitude dari X dan longitude dari Y. Pemilihan sheet dari riwayat file menggunakan deteksi yang sama. Pasangan dengan urutan standar X=bujur, Y=lintang tetap didukung.

Backend memeriksa ulang pasangan kolom X/Y, termasuk untuk klien API dan mapping lama. Penyesuaian dilakukan hanya ketika:

- Kedua kolom merupakan pasangan `X`/`Y` atau `KOORDINAT_X`/`KOORDINAT_Y`.
- Kedua nilai merupakan angka hingga, termasuk desimal koma.
- Calon lintang melewati 90 tetapi tidak melewati 180, sedangkan calon bujur berada dalam rentang lintang.

Jika kedua orientasi masih mungkin, sistem mempertahankan mapping yang dipilih. Kolom bernama `LAT`, `LON`, `latitudey`, atau `longitudex` tidak ditukar otomatis. Nilai di luar rentang, tidak terbaca, atau pasangan tidak lengkap tetap mengikuti validasi sebelumnya. Sel sumber dan nama kolom asli tetap dipertahankan.

## Pemulihan data lama

Migrasi `d4e91ba620f3` menjalankan pemulihan bertahap terhadap sumber yang sudah selesai diimpor. Hanya pasangan yang memenuhi syarat di atas dan latitude hasil normalisasinya masih kosong yang diperbaiki. Nilai normalisasi, status validasi baris, dan hitungan valid/bermasalah pada batch diperbarui. Data asli, mapping awal, sheet yang belum dikonfirmasi, dan snapshot historis pemeriksaan tidak ditimpa.

Tabel `coordinate_repairs` mencatat batch yang sudah diperiksa agar startup berikutnya tidak memindai ulang jutaan baris. Pemrosesan membaca maksimal 1.000 baris per kelompok. Pemulihan juga dijalankan oleh kompatibilitas skema saat backend dimulai.

Snapshot hasil pemeriksaan lama tetap memakai data saat snapshot tersebut dibuat. Untuk menghasilkan hasil berdasarkan sumber yang dipulihkan, gunakan pemeriksaan baru; pencarian ulang yang masih memakai snapshot lama tidak mengubah snapshot tersebut.

Pengujian mencakup urutan PLN dan standar, desimal koma, mapping eksplisit, kolom bernama latitude/longitude, angka tidak valid, pasangan ambigu, impor API, pemulihan batch lama, penghitungan ulang validasi, idempotensi, pelindungan sheet belum dikonfirmasi, serta impor XLSX dan pergantian sheet dari riwayat melalui browser.
