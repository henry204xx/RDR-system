# Sistem pakar Ripple Down Rules

Sistem desktop Python untuk membuat domain, memasukkan kasus, dan memperbaiki pengetahuan secara manual. Tidak ada impor CSV/dataset dalam GUI. Dataset Zoo dan Automobile yang disertakan hanya merupakan contoh dan bahan pengujian; tidak digunakan otomatis untuk melatih KB.

## Menjalankan

Di Windows, jalankan dari folder proyek:

```powershell
py gui.py
```

Diperlukan Python dengan Tkinter; tidak ada paket eksternal. Di sistem lain gunakan `python3 gui.py` dan pasang Tkinter jika belum tersedia. Jalankan pengujian dengan `py -m unittest -v`.

## Alur manual

1. Klik **Buat KB baru**, isi nama domain dan kesimpulan default. Atribut pertama boleh dikosongkan. Contoh Zoo: nama `eggs`, tipe `kategorikal`, nilai `0, 1`; `0` dan `1` merupakan teks kategori. Untuk domain mobil, contoh atribut: `fuel` dengan nilai `gas, diesel` atau `horsepower` bertipe `numerik`.
2. Klik **Tambah atribut** untuk atribut lain. Isikan daftar kategori dengan pemisah koma; angka menggunakan titik desimal, misalnya `3.14`. Pilih atribut yang bermakna bagi keputusan; jangan masukkan jawaban sebagai atribut. Nama dan arti nilai ditentukan pakar, bukan oleh dataset.
3. Isi atribut kasus yang diketahui pada tab **Konsultasi**, lalu klik **Inferensi**. Kosong berarti **tidak diketahui**, bukan `0`, `tidak`, atau `false`. Kondisi yang membutuhkan nilai kosong dianggap tidak terpenuhi dan mengikuti cabang false. Sistem memperingatkan bila nilai kosong menentukan cabang; lengkapi bila tersedia sebelum pakar menilai hasilnya.
4. Pilih **Pakar setuju**, atau **Pakar koreksi** dan masukkan kesimpulan yang benar. Pilih kandidat pembeda; beberapa pilihan berarti AND. Untuk mengubah kandidat atau membuat kondisi manual tanpa JSON, ikuti bagian **Mengubah kondisi**. Contoh: dengan kasus baru `eggs = 0`, pakar boleh memilih `eggs = 0` dan menyimpulkan `Burung` jika hal itu benar untuk kasus tersebut. Sistem tidak mengasumsikan bahwa semua burung memiliki nilai itu.
5. Tab **Visualisasi pohon** menampilkan cabang false di kiri dan true di kanan; biru adalah jalur terakhir. Klik node untuk melihat detail dan kasus kunci atau merevisi kondisinya. Tab **Riwayat** menampilkan perubahan dan persetujuan.
6. Klik **Simpan KB** dan gunakan **Buka KB** untuk melanjutkan. JSON di sini adalah penyimpanan KB, bukan mekanisme impor dataset. Simpan file dengan aman karena memuat kasus dan riwayat.

## Menambah atribut setelah rule ada

Pakar boleh menambahkan atribut kapan saja, termasuk untuk membedakan kasus baru. Nilai kasus kunci lama tidak perlu diisi dan tidak diubah. Jika nilainya benar-benar diketahui, boleh diisi pada dialog **Tambah atribut** atau kemudian lewat **Lengkapi kasus kunci**. Nilai yang sudah diketahui tidak dapat ditimpa melalui dialog ini.

Rule koreksi harus cocok dengan kasus baru dan tidak terpenuhi oleh kasus kunci rule terakhir menurut kebijakan di atas. Contohnya, `fitur_B = ya` dapat membedakan kasus baru dari kasus kunci tanpa `fitur_B`, tanpa mengubah kasus lama. Semua kasus kunci lama diuji ulang; jika hasilnya berubah, rule ditolak. Persetujuan tanpa koreksi dicatat sebagai riwayat, bukan otomatis sebagai kasus kunci.

**Batasan penting:** tidak terpenuhinya kondisi karena nilai kosong adalah kebijakan operasional, bukan bukti bahwa nilai sebenarnya berbeda. Mengisi `fitur_B` pada kasus lama atau konsumen lain di kemudian hari bisa mengubah hasil inferensi. Sistem tidak dapat menjamin bahwa rule baru benar secara klinis atau faktual untuk nilai yang belum diketahui; pakar harus mempertimbangkan peringatan tersebut. Fitur pelengkapan kasus kunci menolak nilai yang mengubah kesimpulan terdahulu.

## Mengubah kondisi

**Saat membuat rule:** pada dialog **Pakar koreksi**, pilih kandidat lalu klik **Ubah kandidat terpilih**. Kandidat disalin ke editor sehingga atribut, operator, dan nilainya dapat diubah. Misalnya, ubah nilai `33` menjadi `34` untuk membuat `suhu > 34`. Atau klik **Tambah kondisi** dan pilih atribut, operator, serta nilai sendiri. Tambahkan beberapa baris untuk menggabungkannya dengan AND; gunakan **Hapus** untuk menghapus baris. Jika editor berisi kondisi, isinya menggantikan pilihan di daftar kandidat. Tanpa baris manual, pilihan kandidat digunakan langsung.

Untuk operator kategorikal `in`, masukkan nilai dipisahkan koma, misalnya `merah, biru`. Apit nilai yang mengandung koma dengan tanda kutip, misalnya `merah,"biru,muda"`. Sistem memeriksa tipe, nilai yang diizinkan, kecocokan kasus baru, kasus kunci, dan konflik sebelum menyimpan rule.

**Setelah rule dibuat:** buka **Visualisasi pohon**, klik node rule selain root, lalu klik **Revisi kondisi rule**. Ubah kondisi dan klik **Simpan revisi**, kemudian **Simpan KB**. Kesimpulan rule tidak berubah. Revisi ditolak jika tidak cocok dengan kasus kunci rule tersebut, cocok dengan kasus kunci rule yang dikoreksinya, atau mengubah kesimpulan maupun rule terakhir pada kasus kunci mana pun. Revisi dicatat pada tab **Riwayat**.

Validasi ini tidak menjamin hasil seluruh kasus yang mungkin atau kasus yang hanya disetujui tanpa menjadi kasus kunci: misalnya, mengubah `suhu > 33` menjadi `suhu > 34` dapat mengubah hasil untuk suhu `33.5` atau `34`. Pakar perlu memeriksa dampaknya. Untuk mencatat pengetahuan baru dari kasus koreksi, alur RDR biasa tetaplah menambahkan rule perkecualian, bukan mengubah rule lama.

## Mengubah kesimpulan rule

Buka **Visualisasi pohon**, klik node yang ingin diubah, lalu klik **Revisi kesimpulan rule**. Isi kesimpulan baru, klik **Simpan revisi**, lalu **Simpan KB**. Kondisi dan struktur pohon tidak berubah. Root juga dapat dipilih; kesimpulan default domain akan diperbarui bersama kesimpulan root.

Revisi secara sengaja mengubah kesimpulan kasus kunci milik rule yang dipilih, tanpa mengubah atribut kasusnya. Sistem menolak revisi jika kesimpulan baru kosong atau sama, jika kasus kunci itu tidak menghasilkan kesimpulan baru dari rule tersebut, atau jika revisi mengubah hasil inferensi saat ini untuk kasus kunci rule lain atau kasus yang pernah disetujui pakar. Misalnya, jika kasus kunci rule tersebut juga pernah disetujui, persetujuan itu dapat membuat revisi ditolak. Penolakan tidak mengubah KB.

Riwayat menyimpan kesimpulan sebelum dan sesudah revisi; entri lama tidak ditulis ulang. Pemeriksaan persetujuan membandingkan hasil KB saat ini dengan hasil setelah revisi, bukan memperbaiki kemungkinan perbedaan yang sudah ada di riwayat. Kasus yang tidak tersimpan masih bisa mendapatkan hasil berbeda; pakar tetap perlu menilai dampaknya. Untuk koreksi terhadap kasus baru, gunakan **Pakar koreksi** untuk membuat rule perkecualian.

## Contoh lengkap: 10 kasus

Contoh berikut memakai rekomendasi minuman **fiktif** untuk memperlihatkan proses RDR, bukan aturan nyata tentang cuaca atau kesehatan. Ikuti urutannya agar nomor rule dan hasilnya sama.

### Persiapan KB

1. Jalankan GUI dan klik **Buat KB baru**. Isi nama domain `Minuman ilustrasi`, kesimpulan default `Air putih`, nama atribut pertama `cuaca`, tipe `kategorikal`, dan nilai `panas, dingin`. Klik **Buat KB**.
2. Klik **Tambah atribut**, isi nama `suhu` dan pilih tipe `numerik`, lalu klik **Tambah**. Suhu pada contoh ini dinyatakan dalam derajat Celsius.
3. KB awal hanya berisi rule `#0`: kondisi selalu benar dan kesimpulan `Air putih`. Belum ada kasus kunci.

Untuk setiap baris di bawah, masukkan **semua nilai yang tercantum**, hapus nilai sisa dari kasus sebelumnya bila perlu, dan klik **Inferensi**. Kolom hasil awal adalah hasil *sebelum* tindakan pakar. Untuk koreksi, klik **Pakar koreksi**, isi kesimpulan yang tertera, pilih hanya kandidat kondisi yang tertera, lalu klik **Tambahkan rule**. Untuk persetujuan, klik **Pakar setuju**. Nomor kandidat di daftar dapat berubah; pilih berdasarkan nama atribut dan kondisinya.

| Kasus | Nilai kasus | Hasil awal (rule terakhir) | Pilihan pakar dan hasil |
|---|---|---|---|
| 1 | `cuaca = panas`, `suhu = 30` | `Air putih` (#0) | Koreksi menjadi `Es teh`; pilih `cuaca = panas`. Terbentuk #1. |
| 2 | `cuaca = dingin`, `suhu = 20` | `Air putih` (#0) | Koreksi menjadi `Teh hangat`; pilih `cuaca = dingin`. Terbentuk #2. |
| 3 | `cuaca = panas`, `suhu = 36` | `Es teh` (#1) | Koreksi menjadi `Es teh ekstra dingin`; pilih `suhu > 33`. Terbentuk #3. |
| 4 | `cuaca = panas`, `suhu = 28` | `Es teh` (#1) | Setuju: hasil tetap `Es teh`, tanpa rule baru. |
| 5 | `cuaca = panas`, `suhu = 24` | `Es teh` (#1) | Koreksi menjadi `Es teh ringan`; pilih `suhu < 27`. Terbentuk #4. |
| 6 | `cuaca = dingin`, `suhu = 8` | `Teh hangat` (#2) | Koreksi menjadi `Teh hangat pekat`; pilih `suhu < 14`. Terbentuk #5. |
| 7 | `cuaca = panas`, `suhu = 30`, `gula = ya` | `Es teh` (#1) | **Tambahkan atribut `gula` terlebih dahulu seperti petunjuk di bawah.** Koreksi menjadi `Es teh manis`; pilih `gula = ya`. Terbentuk #6. |
| 8 | `cuaca = panas`, `suhu = 30`, `gula = tidak` | `Es teh` (#1) | Setuju: hasil tetap `Es teh`, tanpa rule baru. |
| 9 | `cuaca = panas`, `suhu = 32`, `gula = ya` | `Es teh manis` (#6) | Koreksi menjadi `Es teh manis dingin`; pilih `suhu > 31`. Terbentuk #7. |
| 10 | `cuaca = panas`, `suhu = 40`, `gula = ya` | `Es teh ekstra dingin` (#3) | Setuju: hasil tetap `Es teh ekstra dingin`, tanpa rule baru. |

Sebelum kasus 7, klik **Tambah atribut**, isi nama `gula`, tipe `kategorikal`, dan nilai `ya, tidak`. Biarkan seluruh kolom untuk kasus kunci lama kosong, lalu klik **Tambah**. Isi `gula = ya` pada formulir konsultasi dan jalankan inferensi lagi. Kasus kunci #1 tetap `cuaca = panas, suhu = 30` tanpa nilai `gula`; kondisi `gula = ya` tidak terpenuhi oleh catatan lama itu menurut kebijakan nilai kosong. Jangan menyimpulkan bahwa gula pada kasus lama sebenarnya `tidak`.

Ambang numerik yang disarankan berasal dari titik tengah nilai kasus baru dan kasus kunci rule terakhir: kasus 3 membandingkan `36` dengan `30`, sehingga kandidatnya `suhu > 33`; kasus 5 membandingkan `24` dengan `30`, sehingga `suhu < 27`; kasus 6 membandingkan `8` dengan `20`, sehingga `suhu < 14`; dan kasus 9 membandingkan `32` dengan `30`, sehingga `suhu > 31`.

Setelah 10 kasus, pohonnya adalah sebagai berikut (`true` ke perkecualian, `false` ke alternatif):

```text
#0 TRUE -> Air putih
  true  -> #1 cuaca = panas -> Es teh
    false -> #2 cuaca = dingin -> Teh hangat
      true  -> #5 suhu < 14 -> Teh hangat pekat
    true  -> #3 suhu > 33 -> Es teh ekstra dingin
      false -> #4 suhu < 27 -> Es teh ringan
        false -> #6 gula = ya -> Es teh manis
          true  -> #7 suhu > 31 -> Es teh manis dingin
```

Contoh penelusuran kasus 9: #0 true → #1 true → #3 false → #4 false → #6 true → #7 true. Kesimpulan terakhir adalah `Es teh manis dingin`, menggantikan kesimpulan #6. Pada kasus 10, #3 sudah true sehingga #6 dan #7 tidak diperiksa. Jika `gula` dikosongkan pada kasus dengan `cuaca = panas, suhu = 30`, #6 tidak terpenuhi dan hasilnya `Es teh`, disertai peringatan bahwa `gula` tidak diketahui. Gunakan **Simpan KB** untuk menyimpan pohon dan riwayat; persetujuan pada kasus 4, 8, dan 10 tidak membuat kasus kunci baru.

## Struktur dan algoritma

KB menyimpan domain, pohon rule, nomor rule berikutnya, dan riwayat. Setiap node memuat kondisi AND, kesimpulan, kasus kunci, `true_child`, dan `false_child`. Root selalu benar dan tidak mempunyai kasus kunci karena belum ada kasus nyata. Rule pertama di bawah root tidak perlu dibandingkan dengan kasus kunci root.

```text
INFERENSI(kasus):
  hasil = default; terakhir = root; node = root
  selama node ada:
    evaluasi kondisi dan catat jalur
    jika atribut yang diperlukan kosong: kondisi tidak terpenuhi; catat peringatan
    jika benar: hasil = kesimpulan node; terakhir = node; node = true_child
    jika salah: node = false_child
  kembalikan hasil, terakhir, jalur

KOREKSI(kasus, kesimpulan, kondisi):
  kondisi harus cocok untuk kasus
  jika rule terakhir memiliki kasus kunci, kondisi tidak boleh cocok untuknya
  salin KB; pasang rule pada true_child rule terakhir,
    atau pada ujung false_child dari anak tersebut
  tolak jika rule tidak tercapai atau hasil kasus kunci lama berubah
  terapkan salinan dan catat riwayat
```

Untuk AND, setiap klausa harus terpenuhi; klausa dengan nilai kosong tidak terpenuhi, termasuk operator `!=`. Peringatan ditampilkan bila suatu nilai kosong menentukan cabang. Hasil tetap harus dinilai oleh pakar, terutama jika ada peringatan.

Operator numerik: `<`, `<=`, `>`, `>=`, `=`, `!=`. Operator kategorikal: `=`, `!=`, `in`. Kandidat dibuat dari perbedaan nilai atau nilai baru yang belum ada di kasus kunci. Pada GUI, kondisi manual diisi melalui editor atribut, operator, dan nilai; CLI tetap menyediakan input JSON sebagai alternatif.

## Referensi

- [Ripple-down rules: struktur SCRDR dan akuisisi pengetahuan](https://en.wikipedia.org/wiki/Ripple-down_rules). Penanganan nilai kosong di atas merupakan pilihan implementasi, bukan jaminan yang ditetapkan sumber tersebut.

## CLI dan pengujian dataset

GUI adalah cara utama dan menggunakan input manual. CLI juga tersedia: `py main.py init kb.json`, `py main.py konsultasi kb.json`, `py main.py pohon kb.json`, dan `py main.py riwayat kb.json`. CLI `init` secara default memakai skema Zoo; pilihan `--domain domain-contoh.json` tersedia untuk kompatibilitas. 
