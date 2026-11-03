# Pencarian data

Perbaikan ini hanya mencakup pencarian pada master, PDPJ, koreksi, hasil koreksi,
dan filter lokal peta. Login, pemilihan periode master, rumus jarak, radius,
checkpoint pemrosesan, persetujuan, serta format ekspor tidak diganti.

## Penyebab lambat

Pencarian sebelumnya mengevaluasi beberapa kolom JSON dengan pola `%teks%` dan
mengulang evaluasi untuk jumlah hasil serta halaman yang dipilih. Indeks IDPEL
biasa tidak menyelesaikan pencarian potongan teks di tengah nama/kode. Frontend
memakai `useDeferredValue`, yang tidak menjamin jeda request ketika mengetik.

## Perubahan

- Kolom pencarian server menunggu 350 ms setelah ketikan terakhir. Kata kunci
  kosong mengembalikan daftar tanpa menunggu jeda. Request lama tetap memakai
  AbortSignal, dan hasil untuk kata kunci lama tidak ditampilkan sebagai hasil baru.
- SQLite memakai indeks FTS5 trigram untuk mempersempit ID baris terlebih dahulu.
  Filter substring asli tetap dijalankan pada kandidat ID, sehingga arti literal
  `%`, `_`, backslash, cakupan berkas/proses/versi, serta pagination tetap terjaga.
- Profil `source` mencakup sumber master/koreksi; `pdpj` mencakup isian PDPJ;
  `target` dan `decision` mendukung pencarian hasil, kandidat terpilih, dan petugas.
  Kolom nomor meter KWH/prepaid juga dicari pada PDPJ dan koreksi.
- Peta menyimpan hasil normalisasi teks dalam memo dan menerapkan filter setelah
  jeda, tanpa mengubah sumber kandidat atau batas radiusnya.
- Pencarian admin tetap lokal atas data pengguna simulasi yang sudah ada.

FTS menggunakan [tokenizer trigram SQLite](https://www.sqlite.org/fts5.html#the_trigram_tokenizer).
Kata kunci setidaknya tiga karakter dapat memakai indeks substring. Kata kunci
pendek tetap didukung, tetapi pencarian sangat umum dapat membutuhkan lebih banyak
pembacaan. PostgreSQL, SQLite tanpa dukungan trigram, serta database uji in-memory
mempertahankan jalur filter asli.

## Persiapan data lama dan konsistensi

Pencarian pertama memasang indeks turunan `quick_search_v1_*` dan cursor pada
`quick_search_progress`. Data lama dipersiapkan dengan transaksi maksimal 1.000
baris per bagian. Halaman menampilkan jumlah baris yang disiapkan dan memeriksa
progres setiap detik; selama itu respons ditandai `search_index.ready=false`,
bukan hasil pencarian kosong yang final. Proses yang terhenti dilanjutkan dari
cursor tersimpan. Tidak ada pemindaian penuh JSON di request pencarian saat
persiapan besar berlangsung.

Trigger menjaga indeks ketika baris sumber/isian/keputusan ditambah, diedit, atau
dihapus. Pembaruan dan rollback indeks mengikuti transaksi data yang sama. Proses
background hanya membaca data aplikasi dan menulis indeks/cursor turunan.
Pembuatan indeks memakai ruang database tambahan dan berbagi kapasitas penulisan
SQLite selama persiapan. Pengembalian kode Git tidak menghapus indeks database.

## Pengujian

`backend/tests/test_search_index.py` membandingkan hasil jalur indeks dengan filter
asli pada SQLite berkas, termasuk substring, case, karakter literal, scope,
pagination, insert/edit/delete/rollback, persiapan background, PDPJ, keputusan dan
versi hasil. Rencana query memeriksa penggunaan indeks trigram.

Persiapan juga diuji pada rentang baris master gabungan yang tidak ikut dicari:
cursor terus maju, jumlah pembacaan tetap dibatasi per transaksi, dan persiapan
tidak dianggap selesai hanya karena satu bagian tidak berisi sumber yang relevan.

`frontend/tests/e2e/test_search_browser.py` menguji master, PDPJ, kedua kategori
koreksi, peta, hasil, dan admin; mencakup jeda request, pencarian meter, penghapusan
kata kunci, serta pemeliharaan pagination dan scope pemeriksaan.

## Pengukuran lokal

Setelah persiapan 5.854.608 baris pada database lokal selesai, pemanggilan fungsi
backend dengan halaman 25 baris menghasilkan pengukuran berikut. Waktu ini tidak
mencakup jaringan, render browser, atau jeda ketikan 350 ms.

| Pencarian | Waktu fungsi backend |
| --- | --- |
| IDPEL lengkap pada master DIL | 0,070 detik; 1 hasil |
| IDPEL lengkap pada master prabayar | 0,025 detik; 1 hasil |
| Nama pada PDPJ | 0,265 detik; 5 hasil |
| IDPEL lengkap pada PDPJ | 0,021 detik; 1 hasil |
| Nama pada koreksi IDPEL kosong | 0,039 detik; 2 hasil |
| Nama pada koreksi IDPEL tidak ditemukan | 0,016 detik; 1 hasil |

Pola umum seperti `123` menghasilkan 22.449 sampai 75.010 hasil per jenis master.
Contoh tersebut memerlukan sekitar 4,6 sampai 47,8 detik, tergantung jenis sumber
dan kondisi cache disk. Indeks mempersempit pencarian, tetapi penghitungan tepat
dan pemeriksaan filter sumber atas puluhan ribu kecocokan tetap memerlukan I/O.
Gunakan IDPEL/nomor meter lengkap atau potongan nama yang lebih spesifik untuk
pengecekan cepat. Pengukuran ini merupakan contoh lokal, bukan jaminan semua kata
kunci memiliki waktu yang sama.
