# Sistem pakar Ripple Down Rules

Sistem desktop Python untuk membuat domain, memasukkan kasus, dan memperbaiki pengetahuan secara manual. Tidak ada impor CSV/dataset dalam GUI. Dataset Zoo dan Automobile yang disertakan hanya merupakan contoh dan bahan pengujian; tidak digunakan otomatis untuk melatih KB.

## Menjalankan

Di Windows, jalankan dari folder proyek:

```powershell
py gui.py
```

Diperlukan Python dengan Tkinter; tidak ada paket eksternal. Di sistem lain gunakan `python3 gui.py` dan pasang Tkinter jika belum tersedia. Jalankan pengujian dengan `py -m unittest -v`.

## Alur manual

1. Klik **Buat KB baru**, isi nama domain, kesimpulan default, dan atribut pertama. Contoh Zoo: nama `eggs`, tipe `kategorikal`, nilai `0, 1`; `0` dan `1` merupakan teks kategori. Untuk domain mobil, contoh atribut: `fuel` dengan nilai `gas, diesel` atau `horsepower` bertipe `numerik`.
2. Klik **Tambah atribut** untuk atribut lain. Isikan daftar kategori dengan pemisah koma; angka menggunakan titik desimal, misalnya `3.14`. Pilih atribut yang bermakna bagi keputusan; jangan masukkan jawaban sebagai atribut. Nama dan arti nilai ditentukan pakar, bukan oleh dataset.
3. Isi atribut kasus yang diketahui pada tab **Konsultasi**, lalu klik **Inferensi**. Kosong berarti **tidak diketahui**, bukan `0`, `tidak`, atau `false`. Atribut yang tidak relevan pada jalur yang diuji boleh dikosongkan. Jika atribut yang dibutuhkan tidak diketahui, hasil ditandai belum selesai; lengkapi atribut yang diminta sebelum menyetujui atau mengoreksi.
4. Pilih **Pakar setuju**, atau **Pakar koreksi** dan masukkan kesimpulan yang benar. Pilih kandidat pembeda; beberapa pilihan berarti AND. Contoh: dengan kasus baru `eggs = 0`, pakar boleh memilih `eggs = 0` dan menyimpulkan `Burung` jika hal itu benar untuk kasus tersebut. Sistem tidak mengasumsikan bahwa semua burung memiliki nilai itu.
5. Tab **Visualisasi pohon** menampilkan cabang false di kiri dan true di kanan; biru adalah jalur terakhir. Klik node untuk melihat detail dan kasus kunci. Tab **Riwayat** menampilkan perubahan dan persetujuan.
6. Klik **Simpan KB** dan gunakan **Buka KB** untuk melanjutkan. JSON di sini adalah penyimpanan KB, bukan mekanisme impor dataset. Simpan file dengan aman karena memuat kasus dan riwayat.

## Menambah atribut setelah rule ada

Pakar boleh menambahkan atribut kapan saja. Jika nilai atribut baru untuk kasus kunci lama diketahui, isi pada dialog **Tambah atribut**. Jika tidak diketahui, biarkan kosong; jangan menebaknya. Nilainya dapat dilengkapi kemudian lewat **Lengkapi kasus kunci**. Nilai yang sudah diketahui tidak dapat ditimpa melalui dialog ini.

Rule koreksi harus cocok dengan kasus baru dan **pasti tidak cocok** dengan kasus kunci rule terakhir. Jika kasus baru membutuhkan `fitur_B = ya` tetapi nilai `fitur_B` pada kasus kunci lama tidak diketahui, sistem menolak rule hingga pakar dapat memastikan nilai lama atau memilih kondisi lain yang benar-benar membedakan. Semua kasus kunci lama harus tetap menghasilkan hasil yang sama dan dapat ditentukan; bila tidak, rule ditolak. Persetujuan tanpa koreksi dicatat sebagai riwayat, bukan otomatis sebagai kasus kunci.

## Struktur dan algoritma

KB menyimpan domain, pohon rule, nomor rule berikutnya, dan riwayat. Setiap node memuat kondisi AND, kesimpulan, kasus kunci, `true_child`, dan `false_child`. Root selalu benar dan tidak mempunyai kasus kunci karena belum ada kasus nyata. Rule pertama di bawah root tidak perlu dibandingkan dengan kasus kunci root.

```text
INFERENSI(kasus):
  hasil = default; terakhir = root; node = root
  selama node ada:
    evaluasi kondisi dan catat jalur
    jika tidak diketahui: berhenti; minta atribut yang diperlukan
    jika benar: hasil = kesimpulan node; terakhir = node; node = true_child
    jika salah: node = false_child
  kembalikan hasil, terakhir, jalur

KOREKSI(kasus, kesimpulan, kondisi):
  inferensi harus selesai; kondisi harus pasti cocok untuk kasus
  jika rule terakhir memiliki kasus kunci, kondisi harus pasti tidak cocok untuknya
  salin KB; pasang rule pada true_child rule terakhir,
    atau pada ujung false_child dari anak tersebut
  tolak jika rule tidak tercapai atau hasil kasus kunci lama berubah/tidak dapat ditentukan
  terapkan salinan dan catat riwayat
```

Untuk AND, satu klausa yang pasti salah membuat kondisi salah sekalipun klausa lain tidak diketahui; jika tidak ada klausa salah dan ada klausa tidak diketahui, kondisi tidak diketahui. Root default bukan diagnosis atau rekomendasi final jika inferensi terhenti karena nilai yang diperlukan hilang.

Operator numerik: `<`, `<=`, `>`, `>=`, `=`, `!=`. Operator kategorikal: `=`, `!=`, `in`. Kandidat di dialog koreksi dibuat dari perbedaan nilai yang diketahui. Klausa lebih khusus dapat dimasukkan sebagai JSON di dialog, misalnya `[ {"atribut":"horsepower", "operator":">=", "nilai":100} ]`.

## CLI dan pengujian dataset

GUI adalah cara utama dan menggunakan input manual. CLI juga tersedia: `py main.py init kb.json`, `py main.py konsultasi kb.json`, `py main.py pohon kb.json`, dan `py main.py riwayat kb.json`. CLI `init` secara default memakai skema Zoo; pilihan `--domain domain-contoh.json` tersedia untuk kompatibilitas. `py main.py demo kb-demo-baru.json` memakai beberapa baris Zoo hanya untuk mensimulasikan koreksi dan menguji mesin, bukan konsultasi manual atau evaluasi akurasi. `init` dan `demo` menolak menimpa file yang sudah ada.
