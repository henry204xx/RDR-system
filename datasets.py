"""Membaca dataset CSV dan mengubah kolom terpilih menjadi kasus RDR."""

import csv
import math
from pathlib import Path

from main import ZOO_ATTRIBUTES
from rdr import RDRError, validate_domain, validate_case

AUTOMOBILE_COLUMNS = ["symboling", "normalized-losses", "make", "fuel-type", "aspiration",
                      "num-of-doors", "body-style", "drive-wheels", "engine-location", "wheel-base",
                      "length", "width", "height", "curb-weight", "engine-type", "num-of-cylinders",
                      "engine-size", "fuel-system", "bore", "stroke", "compression-ratio", "horsepower",
                      "peak-rpm", "city-mpg", "highway-mpg", "price"]
AUTOMOBILE_CATEGORICAL = {"make", "fuel-type", "aspiration", "num-of-doors", "body-style", "drive-wheels",
                          "engine-location", "engine-type", "num-of-cylinders", "fuel-system"}
MISSING = {"", "?"}


def read_table(path, preset="csv"):
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file, strict=True))
    if not rows:
        raise RDRError("File dataset kosong.")
    if preset == "zoo":
        names = ["animal_name", *ZOO_ATTRIBUTES, "type"]
    elif preset == "automobile":
        names = AUTOMOBILE_COLUMNS[:]
    elif preset == "csv":
        names = [name.strip() for name in rows.pop(0)]
    elif preset == "tanpa header":
        names = [f"kolom_{index + 1}" for index in range(len(rows[0]))]
    else:
        raise RDRError("Format dataset tidak dikenal.")
    if not rows:
        raise RDRError("Dataset tidak memiliki baris data.")
    if not names or any(not name for name in names) or len(set(names)) != len(names):
        raise RDRError("Nama kolom harus unik dan tidak kosong.")
    for index, row in enumerate(rows, start=2 if preset == "csv" else 1):
        if len(row) != len(names):
            raise RDRError(f"Baris data {index} memiliki {len(row)} kolom, diharapkan {len(names)}.")
    return names, [[value.strip() for value in row] for row in rows]


def guess_roles(names, rows, preset, domain=None):
    roles = []
    for index, name in enumerate(names):
        if domain is not None:
            role = domain["atribut"].get(name, {}).get("tipe", "abaikan")
        elif preset == "zoo":
            role = "abaikan" if name == "animal_name" else "label" if name == "type" else "numerik" if name == "legs" else "kategorikal"
        elif preset == "automobile":
            role = "label" if name == "symboling" else "kategorikal" if name in AUTOMOBILE_CATEGORICAL else "numerik"
        else:
            values = [row[index] for row in rows if row[index] not in MISSING]
            try:
                numeric = bool(values) and all(math.isfinite(float(value)) for value in values)
            except ValueError:
                numeric = False
            role = "numerik" if numeric else "kategorikal"
        roles.append(role)
    return roles


def prepare_dataset(names, rows, roles, domain_name, default, existing_domain=None):
    if len(names) != len(roles) or len(set(names)) != len(names) or any(not name.strip() for name in names):
        raise RDRError("Nama kolom harus unik, tidak kosong, dan sesuai dengan pilihan peran.")
    if any(role not in {"numerik", "kategorikal", "label", "abaikan"} for role in roles):
        raise RDRError("Peran kolom tidak dikenal.")
    if roles.count("label") > 1:
        raise RDRError("Pilih paling banyak satu kolom label.")
    feature_columns = [(index, name, role) for index, (name, role) in enumerate(zip(names, roles))
                       if role in {"numerik", "kategorikal"}]
    if not feature_columns:
        raise RDRError("Pilih setidaknya satu atribut.")
    if existing_domain is not None:
        selected = {name: role for _, name, role in feature_columns}
        expected = {name: spec["tipe"] for name, spec in existing_domain["atribut"].items()}
        if selected != expected:
            raise RDRError("Kolom atribut dan tipenya harus sama persis dengan domain KB yang sedang dibuka.")
    label_index = roles.index("label") if "label" in roles else None
    cases = []
    skipped = []
    for row_number, row in enumerate(rows, start=1):
        case = {}
        try:
            for index, name, role in feature_columns:
                value = row[index]
                if value in MISSING:
                    case[name] = None
                    continue
                if role == "numerik":
                    value = float(value)
                    if not math.isfinite(value):
                        raise ValueError(f"{name} bukan angka berhingga")
                case[name] = value
            if existing_domain is not None:
                validate_case(existing_domain, case)
        except (ValueError, RDRError) as error:
            skipped.append(f"Baris data {row_number}: {error}")
            continue
        label = row[label_index] if label_index is not None and row[label_index] not in MISSING else None
        cases.append({"nomor": row_number, "kasus": case, "label": label})
    if not cases:
        raise RDRError("Tidak ada baris valid setelah memeriksa atribut yang dipilih.")
    if existing_domain is None:
        attributes = {}
        for _, name, role in feature_columns:
            attributes[name] = ({"tipe": "numerik"} if role == "numerik" else
                                {"tipe": "kategorikal", "nilai": sorted({case["kasus"][name] for case in cases
                                                                         if case["kasus"][name] is not None})})
        domain = {"nama": domain_name, "kesimpulan_default": default, "atribut": attributes}
        validate_domain(domain)
    else:
        domain = existing_domain
    return domain, cases, skipped
