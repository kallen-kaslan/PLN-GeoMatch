# Aturan kerja Codex

Baca `PROJECT_CONTEXT.md` sebelum mengerjakan tugas di repositori ini. Baca dokumen
rujukan yang relevan saja; jangan memuat semua dokumentasi setiap kali.

## Jawaban harus berdasarkan pemeriksaan
- Sebelum menjelaskan perilaku proyek, periksa kode aktual yang terkait dari UI,
  pemanggilan API, backend, sampai penyimpanan bila relevan. Telusuri dependensinya;
  jangan menyimpulkan dari nama fungsi, README, atau ingatan percakapan saja.
- Cantumkan lokasi file yang mendukung penjelasan. Bedakan fakta kode, kondisi
  runtime/data yang sudah diperiksa, dan hal yang belum diketahui.
- Jangan berasumsi atau mengarang hasil pemeriksaan. Jika belum terverifikasi,
  katakan demikian. Contoh ilustrasi harus jelas diberi label sebagai contoh.
- Untuk angka aktual, isi database, status proses, versi, atau branch terbaru,
  periksa sumbernya kembali. Catatan konteks bukan bukti keadaan terkini.

## Batas tindakan
- Pemeriksaan baca saja diperbolehkan untuk menjawab pertanyaan. Jangan menjalankan
  tindakan yang mengubah keadaan tanpa persetujuan pengguna untuk tindakan itu.
- Permintaan eksplisit seperti "ubah kode" atau "buat file ini" memberi izin
  hanya untuk lingkup tersebut; tidak perlu meminta izin yang sama lagi.
- Diskusi, pertanyaan, atau permintaan panduan bukan izin mengubah kode. Instalasi,
  start aplikasi, build/test yang menulis artefak, migrasi, seed, impor, perubahan
  database, dan operasi Git yang mengubah keadaan memerlukan izin sesuai lingkup.
- Hindari mengimpor modul aplikasi saat hanya memeriksa data: inisialisasi dapat
  mengubah skema. Gunakan koneksi database baca saja jika diperlukan.
- Jangan menimpa pekerjaan pengguna, menghapus data, atau menampilkan rahasia `.env`.

## Cara menjawab dan menjaga konteks
- Gunakan bahasa Indonesia yang jelas dan singkat. Jelaskan bertahap sesuai
  pertanyaan; gunakan label tombol yang benar serta proses setelah tombol diklik.
- Perintah harus cocok untuk PowerShell terminal VS Code. Sebutkan direktori
  tempat menjalankannya; jangan menganggap dependensi atau venv sudah tersedia.
- Jangan memakai analogi kecuali diminta. Jangan menyebut rencana sebagai fitur
  yang sudah diterapkan. Jangan menjanjikan ingatan otomatis seluruh percakapan.
- Jaga kedua file panduan ini ringkas. Saat perubahan dokumentasi diizinkan,
  perbarui bagian relevan tanpa menimpa isi lain atau menyalin seluruh percakapan.
  Simpan rincian teknis di `docs/`, bukan memperpanjang konteks awal.
