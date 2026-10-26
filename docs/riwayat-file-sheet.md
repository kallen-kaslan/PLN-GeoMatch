# Riwayat file dan impor sheet

Formulir impor bersama untuk Data Master, PDPJ, dan kedua kategori Data Koreksi menyimpan file asli secara terpisah dari batch data acuan.

1. Unggah file sekali, atau pilih dari **Riwayat berkas unggahan**.
2. Pilih **Sheet yang diimpor**. Semua sheet dalam file tetap tersedia setelah halaman dimuat ulang.
3. Periksa pratinjau, periode, dan pemetaan kolom.
4. Tekan **Simpan dan validasi** untuk mengaktifkan sheet tersebut. Sheet lain tetap belum tersimpan sebagai acuan.
5. Buka kembali formulir dan pilih file dari riwayat untuk menyimpan sheet berikutnya, tanpa mengirim file asli lagi.

Status pada dropdown:

- `✓ Sudah disimpan`: batch sheet sudah selesai dipetakan dan divalidasi. Sheet yang dipilih juga diberi latar hijau dan tombol penyimpanan dinonaktifkan.
- `◷ Belum divalidasi`: terdapat batch sementara, misalnya konfirmasi mapping sebelumnya gagal. Batch yang sama dilanjutkan, bukan digandakan.
- `Belum disimpan`: belum terdapat batch sheet untuk kategori dan periode yang dipilih.

Ceklis mengikuti **file, sheet, kategori, dan periode**. Sheet yang disimpan untuk DIL tidak ditandai sudah tersimpan untuk PDPJ. File berisi byte identik dikenali dengan SHA-256 sehingga unggah ulang tidak menciptakan salinan riwayat baru. Nama file sama dengan isi berbeda tetap merupakan riwayat berbeda.

Membuka file atau pratinjau sheet tidak membuat `UploadBatch` maupun `SourceRecord`. Saat tombol simpan ditekan, server membuat batch berstatus `needs_mapping`; batch tersebut baru berstatus `completed` setelah konfirmasi mapping dan validasi berhasil. Pembacaan master dan pemrosesan tetap membatasi acuan pada batch yang sudah selesai. Kegagalan parsing atau penyimpanan baris membatalkan seluruh transaksi sheet, sementara file asli tetap tersedia untuk mencoba kembali. Hasil validasi masih dapat memuat baris bermasalah sesuai aturan impor yang sudah ada; ceklis menunjukkan validasi telah dijalankan, bukan jaminan semua baris sempurna.

Sheet yang sudah selesai tidak dapat diimpor dua kali untuk cakupan yang sama. Endpoint impor mengembalikan batch yang sudah ada; UI menolak penyimpanan ulang. Mapping sheet arsip yang sudah selesai tidak dapat diubah menjadi mapping lain melalui endpoint konfirmasi. Permintaan identik tetap idempoten.

## Penyimpanan dan migrasi

Migrasi `c8d72fe610ab` menambah `upload_file_archives` dan `upload_sheet_imports`, tanpa menebak identitas file dari nama atau mengubah batch lama. File asli disimpan dengan nama internal acak pada `UPLOAD_STORAGE_DIR`, default `backend/storage/uploads`. Direktori ini diabaikan Git. Backup dan pemindahan aplikasi perlu membawa direktori tersebut bersama database; beberapa worker perlu mengakses direktori yang sama.

Reset data juga menghapus tautan sheet, metadata riwayat, dan file arsip yang terkait. Pembacaan sheet menggunakan parser streaming yang sama dengan impor lama, termasuk batas 500 MB, CSV encoding, header kosong di awal, dimensi XLSX yang keliru, dan nomor baris sumber. Nama file pengguna tidak digunakan sebagai path penyimpanan.

Unggahan dari sebelum fitur ini hanya menyimpan sheet terpilih dan tidak memiliki file asli. Sheet lain pada file lama tidak dapat direkonstruksi. Unggah file aslinya sekali untuk memasukkannya ke riwayat baru; batch lama tetap dipertahankan dan tidak ditautkan otomatis hanya berdasarkan nama file.

## API

| Endpoint | Fungsi |
| --- | --- |
| `GET /upload/files` | Daftar file asli, seluruh nama sheet, dan status impor per kategori/periode |
| `POST /upload/files` | Simpan file asli tanpa membuat batch acuan |
| `GET /upload/files/{id}/preview?sheet_name=...` | Baca pratinjau tanpa perubahan data |
| `POST /upload/files/{id}/import-sheet` | Buat/lanjutkan batch sementara dari file tersimpan |
| `POST /upload/confirm-mapping` | Terapkan mapping dan validasi, lalu selesaikan batch |

Endpoint unggah lama tetap kompatibel. Pengujian baru mencakup riwayat setelah reload, impor sheet berikutnya tanpa multipart upload tambahan, ceklis per kategori/periode, pencegahan duplikasi, kegagalan konfirmasi, rollback penulisan, sheet kosong, file asli hilang/pemulihan, dan reset dengan foreign key aktif.
