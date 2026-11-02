"""Mesin Ripple Down Rules dan utilitas persistensi."""

import copy
import json
import math
import operator
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

NUMERIC_OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt,
               ">=": operator.ge, "=": operator.eq, "!=": operator.ne}
CATEGORICAL_OPS = {"=": operator.eq, "!=": operator.ne, "in": lambda value, choices: value in choices}


class RDRError(ValueError):
    pass


def validate_domain(domain):
    if not isinstance(domain, dict) or not isinstance(domain.get("nama"), str) or not domain["nama"].strip():
        raise RDRError("Nama domain harus berupa teks yang tidak kosong.")
    if not isinstance(domain.get("kesimpulan_default"), str) or not domain["kesimpulan_default"].strip():
        raise RDRError("Kesimpulan default harus berupa teks yang tidak kosong.")
    attributes = domain.get("atribut")
    if not isinstance(attributes, dict):
        raise RDRError("Atribut domain harus berupa objek.")
    for name, spec in attributes.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(spec, dict):
            raise RDRError("Nama dan definisi atribut tidak valid.")
        if spec.get("tipe") not in ("numerik", "kategorikal"):
            raise RDRError(f"Tipe atribut {name} harus numerik atau kategorikal.")
        if spec["tipe"] == "kategorikal":
            values = spec.get("nilai")
            if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values) or len(set(values)) != len(values):
                raise RDRError(f"Nilai kategorikal {name} harus berupa daftar teks unik yang tidak kosong.")


def validate_case(domain, case):
    if not isinstance(case, dict) or set(case) - set(domain["atribut"]):
        raise RDRError("Kasus harus berupa objek yang hanya berisi atribut domain.")
    for name, spec in domain["atribut"].items():
        value = case.get(name)
        if value is None:
            continue
        if spec["tipe"] == "numerik":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise RDRError(f"{name} harus berupa angka berhingga.")
        elif not isinstance(value, str) or value not in spec["nilai"]:
            raise RDRError(f"{name} harus salah satu dari {spec['nilai']}.")


def validate_condition(domain, condition):
    if not isinstance(condition, list) or not condition:
        raise RDRError("Kondisi harus berisi minimal satu klausa.")
    for clause in condition:
        if not isinstance(clause, dict) or set(clause) != {"atribut", "operator", "nilai"}:
            raise RDRError("Klausa harus berisi atribut, operator, dan nilai.")
        name, operation, value = clause["atribut"], clause["operator"], clause["nilai"]
        if not isinstance(name, str) or name not in domain["atribut"]:
            raise RDRError(f"Atribut tidak dikenal: {name}.")
        spec = domain["atribut"][name]
        allowed = NUMERIC_OPS if spec["tipe"] == "numerik" else CATEGORICAL_OPS
        if not isinstance(operation, str) or operation not in allowed:
            raise RDRError(f"Operator tidak valid untuk {name}.")
        values = value if operation == "in" else [value]
        if not isinstance(values, list) or not values:
            raise RDRError("Operator in membutuhkan daftar nilai yang tidak kosong.")
        for item in values:
            if spec["tipe"] == "numerik":
                if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
                    raise RDRError(f"Nilai kondisi {name} harus berupa angka berhingga.")
            elif not isinstance(item, str) or item not in spec["nilai"]:
                raise RDRError(f"Nilai kondisi {name} tidak terdaftar dalam skema.")


def matches(condition, case, domain):
    if condition is None:
        return True
    for clause in condition:
        value = case.get(clause["atribut"])
        if value is None:
            return False
        operations = NUMERIC_OPS if domain["atribut"][clause["atribut"]]["tipe"] == "numerik" else CATEGORICAL_OPS
        if not operations[clause["operator"]](value, clause["nilai"]):
            return False
    return True


def new_rule(identifier, condition, conclusion, cornerstone):
    return {"id": identifier, "kondisi": copy.deepcopy(condition), "kesimpulan": conclusion,
            "kasus_kunci": copy.deepcopy(cornerstone), "true_child": None, "false_child": None}


def new_kb(domain):
    validate_domain(domain)
    return {"versi": 1, "domain": copy.deepcopy(domain),
            "root": new_rule(0, None, domain["kesimpulan_default"], None),
            "next_id": 1, "riwayat": []}


def infer(kb, case):
    validate_case(kb["domain"], case)
    node = kb["root"]
    conclusion = node["kesimpulan"]
    last_rule = node
    path = []
    missing = set()
    while node is not None:
        fired = matches(node["kondisi"], case, kb["domain"])
        path.append({"id": node["id"], "terpenuhi": fired, "kesimpulan": node["kesimpulan"]})
        if node["kondisi"] is not None:
            known = [clause for clause in node["kondisi"] if case.get(clause["atribut"]) is not None]
            if matches(known, case, kb["domain"]):
                missing.update(clause["atribut"] for clause in node["kondisi"] if case.get(clause["atribut"]) is None)
        if fired:
            conclusion, last_rule = node["kesimpulan"], node
        node = node["true_child" if fired else "false_child"]
    return {"kesimpulan": conclusion, "selesai": True, "atribut_diperlukan": [], "atribut_tidak_diketahui": sorted(missing),
            "last_firing_id": last_rule["id"], "jalur": path}


def iter_rules(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        if node["false_child"] is not None:
            stack.append(node["false_child"])
        if node["true_child"] is not None:
            stack.append(node["true_child"])


def suggestions(domain, case, cornerstone):
    validate_case(domain, case)
    if cornerstone is not None:
        validate_case(domain, cornerstone)
    result = []
    for name, spec in domain["atribut"].items():
        value = case.get(name)
        old = None if cornerstone is None else cornerstone.get(name)
        if value is None or (cornerstone is not None and value == old):
            continue
        if spec["tipe"] == "numerik" and old is not None:
            threshold = old / 2 + value / 2
            if not math.isfinite(threshold) or threshold == old or threshold == value:
                threshold = old
            operation = ">" if value > old else "<"
            clause = {"atribut": name, "operator": operation, "nilai": threshold}
        else:
            clause = {"atribut": name, "operator": "=", "nilai": value}
        result.append({"atribut": name, "kasus_baru": value, "kasus_kunci": old, "klausa": clause})
    return result


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def accept(kb, case):
    result = infer(kb, case)
    if not result["selesai"]:
        raise RDRError(f"Inferensi belum selesai; isi atribut: {', '.join(result['atribut_diperlukan'])}.")
    kb["riwayat"].append({"waktu": timestamp(), "aksi": "disetujui", "kasus": copy.deepcopy(case),
                          "hasil": result})
    return result


def add_rule(kb, case, conclusion, condition):
    before = infer(kb, case)
    if not before["selesai"]:
        raise RDRError(f"Inferensi belum selesai; isi atribut: {', '.join(before['atribut_diperlukan'])}.")
    if not isinstance(conclusion, str) or not conclusion.strip():
        raise RDRError("Kesimpulan baru tidak boleh kosong.")
    if conclusion == before["kesimpulan"]:
        raise RDRError("Kesimpulan baru sama dengan hasil saat ini; setujui kasus sebagai gantinya.")
    validate_condition(kb["domain"], condition)
    if matches(condition, case, kb["domain"]) is not True:
        raise RDRError("Kondisi baru harus pasti terpenuhi oleh kasus baru; lengkapi nilai yang diperlukan.")
    last = next(rule for rule in iter_rules(kb["root"]) if rule["id"] == before["last_firing_id"])
    if last["kasus_kunci"] is not None and matches(condition, last["kasus_kunci"], kb["domain"]) is not False:
        raise RDRError("Kondisi tidak boleh terpenuhi oleh kasus kunci rule terakhir.")

    candidate = copy.deepcopy(kb)
    target = next(rule for rule in iter_rules(candidate["root"]) if rule["id"] == before["last_firing_id"])
    slot = target
    edge = "true_child"
    if slot[edge] is not None:
        slot = slot[edge]
        edge = "false_child"
        while slot[edge] is not None:
            slot = slot[edge]
    rule = new_rule(candidate["next_id"], condition, conclusion, case)
    slot[edge] = rule
    candidate["next_id"] += 1
    after = infer(candidate, case)
    if not after["selesai"] or after["last_firing_id"] != rule["id"] or after["kesimpulan"] != conclusion:
        raise RDRError("Rule baru tidak dapat dicapai: rule perkecualian sebelumnya cocok dengan kasus ini.")
    conflicts = []
    for old_rule in iter_rules(kb["root"]):
        old_case = old_rule["kasus_kunci"]
        if old_case is not None:
            old_result, new_result = infer(kb, old_case), infer(candidate, old_case)
            if not old_result["selesai"] or not new_result["selesai"] or old_result["kesimpulan"] != new_result["kesimpulan"]:
                conflicts.append(old_rule["id"])
    if conflicts:
        raise RDRError(f"Konflik atau nilai belum diketahui pada kasus kunci rule {conflicts}; rule tidak disimpan.")
    candidate["riwayat"].append({"waktu": timestamp(), "aksi": "rule_ditambahkan", "kasus": copy.deepcopy(case),
                                "hasil_sebelum": before, "hasil_sesudah": after, "rule": copy.deepcopy(rule)})
    kb.clear()
    kb.update(candidate)
    return after


def revise_condition(kb, rule_id, condition):
    validate_condition(kb["domain"], condition)
    stack = [(kb["root"], None)]
    target = parent = None
    while stack:
        node, context = stack.pop()
        if node["id"] == rule_id:
            target, parent = node, context
            break
        if node["false_child"] is not None:
            stack.append((node["false_child"], context))
        if node["true_child"] is not None:
            stack.append((node["true_child"], node))
    if target is None:
        raise RDRError("Rule tidak ditemukan.")
    if parent is None or target["kasus_kunci"] is None:
        raise RDRError("Kondisi rule default tidak dapat direvisi.")
    if not matches(condition, target["kasus_kunci"], kb["domain"]):
        raise RDRError("Kondisi baru harus terpenuhi oleh kasus kunci rule ini.")
    if parent["kasus_kunci"] is not None and matches(condition, parent["kasus_kunci"], kb["domain"]):
        raise RDRError("Kondisi baru tidak boleh terpenuhi oleh kasus kunci rule yang dikoreksi.")

    candidate = copy.deepcopy(kb)
    revised = next(rule for rule in iter_rules(candidate["root"]) if rule["id"] == rule_id)
    previous_condition = copy.deepcopy(revised["kondisi"])
    revised["kondisi"] = copy.deepcopy(condition)
    conflicts = []
    for rule in iter_rules(kb["root"]):
        if rule["kasus_kunci"] is None:
            continue
        before = infer(kb, rule["kasus_kunci"])
        after = infer(candidate, rule["kasus_kunci"])
        if (before["selesai"], before["kesimpulan"], before["last_firing_id"]) != (
                after["selesai"], after["kesimpulan"], after["last_firing_id"]):
            conflicts.append(rule["id"])
    if conflicts:
        raise RDRError(f"Revisi mengubah hasil atau rule terakhir kasus kunci {conflicts}; revisi ditolak.")
    candidate["riwayat"].append({"waktu": timestamp(), "aksi": "kondisi_direvisi", "rule_id": rule_id,
                                 "kondisi_sebelum": previous_condition, "kondisi_sesudah": copy.deepcopy(condition)})
    kb.clear()
    kb.update(candidate)


def revise_conclusion(kb, rule_id, conclusion):
    target = next((rule for rule in iter_rules(kb["root"]) if rule["id"] == rule_id), None)
    if target is None:
        raise RDRError("Rule tidak ditemukan.")
    if not isinstance(conclusion, str) or not conclusion.strip():
        raise RDRError("Kesimpulan baru tidak boleh kosong.")
    conclusion = conclusion.strip()
    if conclusion == target["kesimpulan"]:
        raise RDRError("Kesimpulan baru sama dengan kesimpulan saat ini.")

    candidate = copy.deepcopy(kb)
    revised = next(rule for rule in iter_rules(candidate["root"]) if rule["id"] == rule_id)
    previous_conclusion = revised["kesimpulan"]
    revised["kesimpulan"] = conclusion
    if rule_id == candidate["root"]["id"]:
        candidate["domain"]["kesimpulan_default"] = conclusion
    if target["kasus_kunci"] is not None:
        result = infer(candidate, target["kasus_kunci"])
        if not result["selesai"] or result["last_firing_id"] != rule_id or result["kesimpulan"] != conclusion:
            raise RDRError("Kasus kunci rule ini tidak menghasilkan kesimpulan baru; revisi ditolak.")

    conflicts = []
    for rule in iter_rules(kb["root"]):
        if rule["id"] == rule_id or rule["kasus_kunci"] is None:
            continue
        before = infer(kb, rule["kasus_kunci"])
        after = infer(candidate, rule["kasus_kunci"])
        if (before["selesai"], before["kesimpulan"]) != (after["selesai"], after["kesimpulan"]):
            conflicts.append(rule["id"])
    if conflicts:
        raise RDRError(f"Revisi mengubah hasil kasus kunci rule lain {conflicts}; revisi ditolak.")
    accepted_conflicts = []
    for index, entry in enumerate(kb["riwayat"], start=1):
        if entry.get("aksi") != "disetujui":
            continue
        before = infer(kb, entry["kasus"])
        after = infer(candidate, entry["kasus"])
        if (before["selesai"], before["kesimpulan"]) != (after["selesai"], after["kesimpulan"]):
            accepted_conflicts.append(index)
    if accepted_conflicts:
        raise RDRError(f"Revisi mengubah hasil kasus yang disetujui pada riwayat {accepted_conflicts}; revisi ditolak.")

    candidate["riwayat"].append({"waktu": timestamp(), "aksi": "kesimpulan_direvisi", "rule_id": rule_id,
                                 "kesimpulan_sebelum": previous_conclusion, "kesimpulan_sesudah": conclusion})
    kb.clear()
    kb.update(candidate)


def add_attribute(kb, name, spec, cornerstone_values=None):
    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise RDRError("Nama atribut harus berupa teks tidak kosong tanpa spasi di tepinya.")
    if name in kb["domain"]["atribut"]:
        raise RDRError("Atribut sudah ada dalam domain.")
    values = {} if cornerstone_values is None else cornerstone_values
    if not isinstance(values, dict):
        raise RDRError("Nilai kasus kunci harus berupa pasangan ID rule dan nilai.")
    old_rules = {rule["id"]: rule for rule in iter_rules(kb["root"]) if rule["kasus_kunci"] is not None}
    if set(values) - set(old_rules):
        raise RDRError("ID kasus kunci tidak dikenal.")
    candidate = copy.deepcopy(kb)
    candidate["domain"]["atribut"][name] = copy.deepcopy(spec)
    validate_domain(candidate["domain"])
    for rule in iter_rules(candidate["root"]):
        if rule["kasus_kunci"] is None:
            continue
        if values.get(rule["id"]) is not None:
            rule["kasus_kunci"][name] = copy.deepcopy(values[rule["id"]])
        validate_case(candidate["domain"], rule["kasus_kunci"])
        old_result = infer(kb, old_rules[rule["id"]]["kasus_kunci"])
        new_result = infer(candidate, rule["kasus_kunci"])
        if (old_result["selesai"], old_result["kesimpulan"]) != (new_result["selesai"], new_result["kesimpulan"]):
            raise RDRError(f"Penambahan atribut mengubah hasil kasus kunci rule {rule['id']}.")
    candidate["riwayat"].append({"waktu": timestamp(), "aksi": "atribut_ditambahkan", "atribut": name,
                                "definisi": copy.deepcopy(spec), "nilai_kasus_kunci": [
                                    {"rule_id": rule_id, "nilai": copy.deepcopy(value)} for rule_id, value in values.items()]})
    kb.clear()
    kb.update(candidate)


def set_cornerstone_attribute(kb, rule_id, name, value):
    old_rule = next((rule for rule in iter_rules(kb["root"]) if rule["id"] == rule_id), None)
    if old_rule is None or old_rule["kasus_kunci"] is None:
        raise RDRError("Kasus kunci tidak ditemukan.")
    if name not in kb["domain"]["atribut"]:
        raise RDRError("Atribut tidak ditemukan.")
    if old_rule["kasus_kunci"].get(name) is not None:
        raise RDRError("Nilai kasus kunci sudah diketahui dan tidak dapat ditimpa.")
    if value is None:
        raise RDRError("Masukkan nilai yang diketahui, bukan nilai kosong.")
    candidate = copy.deepcopy(kb)
    rule = next(rule for rule in iter_rules(candidate["root"]) if rule["id"] == rule_id)
    rule["kasus_kunci"][name] = value
    validate_case(candidate["domain"], rule["kasus_kunci"])
    before = infer(kb, old_rule["kasus_kunci"])
    after = infer(candidate, rule["kasus_kunci"])
    if before["selesai"] and (not after["selesai"] or before["kesimpulan"] != after["kesimpulan"]):
        raise RDRError("Nilai tersebut mengubah hasil kasus kunci; perubahan ditolak.")
    if not before["selesai"] and after["selesai"] and after["kesimpulan"] != rule["kesimpulan"]:
        raise RDRError("Nilai tersebut bertentangan dengan kesimpulan kasus kunci; perubahan ditolak.")
    candidate["riwayat"].append({"waktu": timestamp(), "aksi": "kasus_kunci_dilengkapi", "rule_id": rule_id,
                                "atribut": name, "nilai": copy.deepcopy(value)})
    kb.clear()
    kb.update(candidate)


def load_kb(path):
    with open(path, encoding="utf-8") as file:
        kb = json.load(file)
    if kb.get("versi") != 1:
        raise RDRError("Versi KB tidak didukung.")
    validate_domain(kb["domain"])
    return kb


def save_kb(kb, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = file.name
            json.dump(kb, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def tree_lines(node, prefix="", edge="root"):
    condition = "TRUE" if node["kondisi"] is None else " AND ".join(
        f"{item['atribut']} {item['operator']} {json.dumps(item['nilai'], ensure_ascii=False)}" for item in node["kondisi"])
    yield f"{prefix}{edge}: #{node['id']} [{condition}] -> {node['kesimpulan']}"
    for label, child in (("true", node["true_child"]), ("false", node["false_child"])):
        if child is not None:
            yield from tree_lines(child, prefix + "  ", label)
