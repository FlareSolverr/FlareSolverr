# Rawon profile-backed FlareSolverr patch

Patch lokal ini dibuat untuk kasus Cloudflare yang tidak cukup diselesaikan dengan cookie transplant biasa.

## Masalah yang disasar

Pada beberapa target seperti `chatgpt.com`, FlareSolverr standar bisa lolos di browser miliknya sendiri, tetapi clearance itu tidak otomatis nempel ke browser profile asli yang dipakai kerja sehari-hari.

Akibatnya:
- FlareSolverr terlihat sukses
- tetapi profile Chrome asli masih mentok di `Just a moment...`

## Tambahan fitur pada patch ini

### 1. `userDataDir`
Memaksa browser internal FlareSolverr memakai **folder profile Chrome asli**.

Praktisnya:
- FlareSolverr tidak lagi solve di profile sementara yang terpisah
- dia solve langsung di profile target yang memang ingin dipulihkan

### 2. `browserArgs`
Mengizinkan argumen Chrome tambahan per request/session.

Kegunaan:
- eksperimen fingerprint
- proxy flag tertentu
- opsi browser tambahan tanpa edit source tiap kali

### 3. `browserExecutablePath`
Mengizinkan override path Chrome/Chromium.

Kegunaan:
- host yang punya binary non-standar
- eksperimen pakai build browser tertentu

### 4. `userAgent` override lokal
Mengizinkan request/session memaksa UA tertentu pada browser yang diluncurkan FlareSolverr.

Catatan:
- ini patch lokal eksperimen
- upstream FlareSolverr v2 tidak memakai request `userAgent` sebagai perilaku resmi default

### 5. Session menyimpan launch settings
Mode `sessions.create` sekarang menyimpan setting penting ini:
- proxy
- user agent
- user data dir
- browser args
- browser executable path

Artinya session berikutnya tetap konsisten dan tidak balik ke launch default.

## Hasil yang sudah terbukti di Rawon

### Gagal
- cookie + UA transplant saja tidak cukup untuk beberapa profile ChatGPT

### Berhasil
- patched FlareSolverr + `userDataDir` profile asli berhasil membersihkan Cloudflare pada beberapa profile ChatGPT Rawon
- untuk profile yang lebih bandel, mode session dua langkah juga berhasil:
  - `sessions.create`
  - `request.get`
  - `request.get` lagi sampai `Challenge not detected!`
  - `sessions.destroy`

## Status

Ini masih **patch eksperimen lokal**, belum upstream.
