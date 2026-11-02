"""Antarmuka CLI untuk sistem pakar RDR."""

import argparse
import csv
import json
import sys
from pathlib import Path

from rdr import RDRError, accept, add_rule, infer, iter_rules, load_kb, new_kb, save_kb, suggestions, tree_lines

ZOO_FILE = Path(__file__).parent / "zoo" / "zoo.data"
ZOO_ATTRIBUTES = ["hair", "feathers", "eggs", "milk", "airborne", "aquatic", "predator", "toothed",
                  "backbone", "breathes", "venomous", "fins", "legs", "tail", "domestic", "catsize"]
ZOO_CLASSES = {1: "Mamalia", 2: "Burung", 3: "Reptil", 4: "Ikan", 5: "Amfibi", 6: "Serangga", 7: "Invertebrata lain"}


def zoo_domain():
    return {"nama": "Klasifikasi hewan Zoo", "kesimpulan_default": "Konsultasi lebih lanjut",
            "atribut": {name: ({"tipe": "numerik"} if name == "legs" else
                               {"tipe": "kategorikal", "nilai": ["0", "1"]}) for name in ZOO_ATTRIBUTES}}


def zoo_rows():
    with ZOO_FILE.open(encoding="utf-8", newline="") as file:
        for index, row in enumerate(csv.reader(file), start=1):
            if len(row) != 18:
                raise RDRError(f"Baris zoo {index} tidak memiliki 18 kolom.")
            values = row[1:17]
            case = {name: (int(value) if name == "legs" else value) for name, value in zip(ZOO_ATTRIBUTES, values)}
            yield index, row[0], case, ZOO_CLASSES[int(row[17])]


def show_result(result):
    if result["selesai"]:
        print(f"Kesimpulan: {result['kesimpulan']}")
        if result.get("atribut_tidak_diketahui"):
            print("Perhatian: kondisi dengan atribut kosong tidak terpenuhi: " + ", ".join(result["atribut_tidak_diketahui"]))
    else:
        print(f"Inferensi belum selesai. Lengkapi: {', '.join(result['atribut_diperlukan'])}")
        print(f"Kesimpulan sementara (belum final): {result['kesimpulan_sementara']}")
    print(f"Rule terakhir: #{result['last_firing_id']}")
    print("Jalur: " + " -> ".join(f"#{step['id']} ({'unknown' if step['terpenuhi'] is None else 'true' if step['terpenuhi'] else 'false'})" for step in result["jalur"]))


def read_case(domain):
    case = {}
    for name, spec in domain["atribut"].items():
        while True:
            suffix = "angka" if spec["tipe"] == "numerik" else "/".join(spec["nilai"])
            raw = input(f"{name} ({suffix}; kosong jika tidak diketahui): ").strip()
            if not raw:
                case[name] = None
                break
            if spec["tipe"] == "numerik":
                try:
                    case[name] = float(raw)
                    break
                except ValueError:
                    print("Masukkan angka yang valid.")
            elif raw in spec["nilai"]:
                case[name] = raw
                break
            else:
                print("Nilai tidak ada di skema.")
    return case


def consult(kb, path, case):
    print("Kasus:", json.dumps(case, ensure_ascii=False))
    result = infer(kb, case)
    show_result(result)
    if not result["selesai"]:
        print("Konsultasi belum selesai; lengkapi atribut yang diperlukan dan coba lagi.")
        return
    while True:
        answer = input("Pakar setuju? [y/n/batal]: ").strip().lower()
        if answer in ("y", "n", "batal"):
            break
    if answer == "batal":
        print("Konsultasi dibatalkan; KB tidak diubah.")
        return
    if answer == "y":
        accept(kb, case)
        save_kb(kb, path)
        print("Persetujuan tersimpan dalam riwayat; pohon tidak berubah.")
        return
    while True:
        conclusion = input("Kesimpulan yang benar (atau batal): ").strip()
        if conclusion.lower() == "batal":
            return
        if conclusion and conclusion != result["kesimpulan"]:
            break
        print("Kesimpulan harus diisi dan berbeda dari hasil saat ini.")
    last = next(rule for rule in iter_rules(kb["root"]) if rule["id"] == result["last_firing_id"])
    options = suggestions(kb["domain"], case, last["kasus_kunci"])
    if last["kasus_kunci"] is None:
        print("Rule default belum memiliki kasus kunci; semua atribut dapat menjadi kandidat.")
    elif any(item["kasus_kunci"] is None for item in options):
        print("Nilai kunci kosong membedakan secara operasional; ini bukan bukti nilai lama.")
    if not options:
        print("Tidak ada perbedaan atribut dengan kasus kunci; rule tidak dapat ditambahkan.")
        return
    print("Kandidat perbedaan atribut:")
    for index, item in enumerate(options, start=1):
        print(f"  {index}. baru={item['kasus_baru']!r}, kunci={item['kasus_kunci']!r}: {json.dumps(item['klausa'])}")
    print('Pilih nomor dipisah koma (AND), atau masukkan array JSON klausa, mis. [{"atribut":"legs","operator":">=","nilai":4}].')
    print("Ketik batal untuk membatalkan.")
    while True:
        raw = input("Kondisi: ").strip()
        if raw.lower() == "batal":
            return
        try:
            if raw.startswith("["):
                condition = json.loads(raw)
            else:
                numbers = [int(value.strip()) for value in raw.split(",")]
                if not numbers or any(number < 1 or number > len(options) for number in numbers):
                    raise RDRError("Nomor kandidat di luar rentang.")
                condition = [options[number - 1]["klausa"] for number in numbers]
            updated = add_rule(kb, case, conclusion, condition)
            save_kb(kb, path)
            print("Rule ditambahkan dan tersimpan.")
            show_result(updated)
            return
        except (ValueError, RDRError) as error:
            print(f"Tidak dapat menambahkan rule: {error}")


def demo(path):
    if Path(path).exists():
        raise RDRError(f"File {path} sudah ada; pilih nama lain agar tidak tertimpa.")
    kb = new_kb(zoo_domain())
    selected = {"aardvark", "chicken", "bass", "frog", "honeybee"}
    for index, name, case, label in zoo_rows():
        if name not in selected:
            continue
        selected.remove(name)
        before = infer(kb, case)
        print(f"\n#{index} {name}: label dataset = {label}; hasil awal = {before['kesimpulan']}")
        if before["kesimpulan"] != label:
            last = next(rule for rule in iter_rules(kb["root"]) if rule["id"] == before["last_firing_id"])
            clauses = [item["klausa"] for item in suggestions(kb["domain"], case, last["kasus_kunci"])]
            add_rule(kb, case, label, clauses)
            print("Koreksi simulasi pakar: seluruh kandidat digunakan sebagai AND.")
        else:
            accept(kb, case)
            print("Simulasi pakar menyetujui hasil.")
        show_result(infer(kb, case))
    save_kb(kb, path)
    print(f"\nKB demo disimpan ke {path}. Ini contoh pembelajaran, bukan evaluasi akurasi.")


def main():
    parser = argparse.ArgumentParser(description="Sistem pakar Ripple Down Rules")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Buat KB baru")
    init.add_argument("kb")
    init.add_argument("--domain", help="File konfigurasi domain JSON; default: zoo")
    example = sub.add_parser("demo", help="Buat KB demo dari beberapa baris dataset zoo")
    example.add_argument("kb")
    consultation = sub.add_parser("konsultasi", help="Masukkan kasus dan validasi oleh pakar")
    consultation.add_argument("kb")
    for name in ("pohon", "riwayat"):
        command = sub.add_parser(name)
        command.add_argument("kb")
    args = parser.parse_args()
    if args.command == "init":
        if Path(args.kb).exists():
            raise RDRError(f"File {args.kb} sudah ada; pilih nama lain agar tidak tertimpa.")
        if args.domain:
            with open(args.domain, encoding="utf-8") as file:
                domain = json.load(file)
        else:
            domain = zoo_domain()
        save_kb(new_kb(domain), args.kb)
        print(f"KB baru disimpan ke {args.kb}.")
    elif args.command == "demo":
        demo(args.kb)
    else:
        kb = load_kb(args.kb)
        if args.command == "pohon":
            print("\n".join(tree_lines(kb["root"])))
        elif args.command == "riwayat":
            print(json.dumps(kb["riwayat"], ensure_ascii=False, indent=2))
        else:
            consult(kb, args.kb, read_case(kb["domain"]))


if __name__ == "__main__":
    try:
        main()
    except (RDRError, OSError, json.JSONDecodeError, EOFError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
