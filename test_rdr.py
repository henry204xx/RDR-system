import copy
import json
import tempfile
import unittest
from pathlib import Path

from main import zoo_domain, zoo_rows
from rdr import (RDRError, accept, add_attribute, add_rule, infer, iter_rules, load_kb, matches, new_kb,
                 revise_condition, revise_conclusion, save_kb, set_cornerstone_attribute, suggestions)


class RDRTests(unittest.TestCase):
    def setUp(self):
        self.domain = {"nama": "uji", "kesimpulan_default": "default", "atribut": {
            "warna": {"tipe": "kategorikal", "nilai": ["merah", "biru", "hijau"]},
            "ukuran": {"tipe": "numerik"}}}
        self.kb = new_kb(self.domain)
        self.red = {"warna": "merah", "ukuran": 10}
        self.blue = {"warna": "biru", "ukuran": 4}

    def clause(self, name, operation, value):
        return {"atribut": name, "operator": operation, "nilai": value}

    def test_inference_exception_and_alternative(self):
        add_rule(self.kb, self.red, "merah", [self.clause("warna", "=", "merah")])
        add_rule(self.kb, self.blue, "biru", [self.clause("warna", "=", "biru")])
        small_red = {"warna": "merah", "ukuran": 2}
        add_rule(self.kb, small_red, "merah kecil", [self.clause("ukuran", "<", 6)])
        self.assertEqual(infer(self.kb, self.red)["kesimpulan"], "merah")
        self.assertEqual(infer(self.kb, self.blue)["kesimpulan"], "biru")
        result = infer(self.kb, small_red)
        self.assertEqual(result["kesimpulan"], "merah kecil")
        self.assertEqual(result["last_firing_id"], 3)
        self.assertEqual([step["id"] for step in result["jalur"]], [0, 1, 3])
        self.assertEqual([step["terpenuhi"] for step in infer(self.kb, self.blue)["jalur"]], [True, False, True])

    def test_rejections_do_not_mutate_kb(self):
        add_rule(self.kb, self.red, "merah", [self.clause("warna", "=", "merah")])
        snapshot = copy.deepcopy(self.kb)
        small_red = {"warna": "merah", "ukuran": 2}
        with self.assertRaises(RDRError):
            add_rule(self.kb, small_red, "salah", [self.clause("warna", "=", "merah")])
        self.assertEqual(self.kb, snapshot)
        with self.assertRaises(RDRError):
            add_rule(self.kb, small_red, "salah", [self.clause("ukuran", ">", 100)])
        self.assertEqual(self.kb, snapshot)

    def test_condition_operators_and_conjunction(self):
        for operation, value in [("<", 11), ("<=", 10), (">", 9), (">=", 10), ("=", 10), ("!=", 9)]:
            self.assertTrue(matches([self.clause("ukuran", operation, value)], self.red, self.domain))
        for operation, value in [("=", "merah"), ("!=", "biru"), ("in", ["merah", "biru"])]:
            self.assertTrue(matches([self.clause("warna", operation, value)], self.red, self.domain))
        self.assertFalse(matches([self.clause("warna", "=", "merah"), self.clause("ukuran", "<", 3)], self.red, self.domain))

    def test_missing_values_do_not_match_and_are_reported(self):
        clauses = [self.clause("warna", "=", "merah"), self.clause("ukuran", ">", 5)]
        self.assertIs(matches(clauses, {"warna": "merah"}, self.domain), False)
        self.assertIs(matches(clauses, {"warna": "biru"}, self.domain), False)
        self.assertIs(matches([self.clause("warna", "!=", "biru")], {}, self.domain), False)
        self.assertIs(matches([self.clause("ukuran", "!=", 5)], {"ukuran": None}, self.domain), False)
        add_rule(self.kb, self.red, "merah besar", clauses)
        result = infer(self.kb, {"warna": "merah"})
        self.assertTrue(result["selesai"])
        self.assertEqual(result["kesimpulan"], "default")
        self.assertEqual(result["atribut_tidak_diketahui"], ["ukuran"])
        self.assertEqual(infer(self.kb, {"warna": "biru"})["kesimpulan"], "default")
        accept(self.kb, {"warna": "merah"})

    def test_add_attribute_and_complete_cornerstone(self):
        add_rule(self.kb, self.red, "merah", [self.clause("warna", "=", "merah")])
        original_history = copy.deepcopy(self.kb["riwayat"])
        add_attribute(self.kb, "fitur", {"tipe": "kategorikal", "nilai": ["ya", "tidak"]})
        self.assertEqual(self.kb["root"]["true_child"]["kasus_kunci"], self.red)
        self.assertEqual(self.kb["riwayat"][:len(original_history)], original_history)
        new_case = {"warna": "merah", "fitur": "ya"}
        condition = [self.clause("fitur", "=", "ya")]
        self.assertIn(condition[0], [item["klausa"] for item in suggestions(self.kb["domain"], new_case, self.red)])
        add_rule(self.kb, new_case, "baru", condition)
        self.assertEqual(self.kb["root"]["true_child"]["kasus_kunci"], self.red)
        self.assertEqual(infer(self.kb, self.red)["kesimpulan"], "merah")
        self.assertEqual(infer(self.kb, new_case)["kesimpulan"], "baru")
        with self.assertRaises(RDRError):
            set_cornerstone_attribute(self.kb, 1, "fitur", "ya")
        set_cornerstone_attribute(self.kb, 1, "fitur", "tidak")
        with self.assertRaises(RDRError):
            set_cornerstone_attribute(self.kb, 1, "fitur", "ya")
        with tempfile.NamedTemporaryFile(dir=Path.cwd(), delete=False) as file:
            path = Path(file.name)
        try:
            save_kb(self.kb, path)
            self.assertEqual(load_kb(path), self.kb)
        finally:
            path.unlink(missing_ok=True)

    def test_new_numeric_attribute_and_existing_unknown_values(self):
        old_case = {"warna": "merah", "ukuran": None}
        add_rule(self.kb, old_case, "merah", [self.clause("warna", "=", "merah")])
        add_attribute(self.kb, "berat", {"tipe": "numerik"})
        case = {"warna": "merah", "berat": 12}
        suggestion = next(item["klausa"] for item in suggestions(self.kb["domain"], case, old_case)
                          if item["atribut"] == "berat")
        self.assertEqual(suggestion, self.clause("berat", "=", 12))
        add_rule(self.kb, case, "berat", [suggestion])
        self.assertEqual(infer(self.kb, old_case)["kesimpulan"], "merah")
        self.assertEqual(infer(self.kb, case)["kesimpulan"], "berat")
        self.assertEqual(self.kb["root"]["true_child"]["kasus_kunci"], old_case)

    def test_root_only_domain(self):
        kb = new_kb({"nama": "kosong", "kesimpulan_default": "default", "atribut": {}})
        self.assertEqual(infer(kb, {})["kesimpulan"], "default")
        add_attribute(kb, "fitur", {"tipe": "numerik"})
        add_rule(kb, {"fitur": 1}, "baru", [self.clause("fitur", "=", 1)])
        self.assertEqual(infer(kb, {})["kesimpulan"], "default")

    def test_revise_condition_preserves_cornerstones_and_history(self):
        add_rule(self.kb, self.red, "merah", [self.clause("warna", "=", "merah")])
        hot = {"warna": "merah", "ukuran": 20}
        small = {"warna": "merah", "ukuran": 6}
        add_rule(self.kb, hot, "besar", [self.clause("ukuran", ">", 15)])
        add_rule(self.kb, small, "kecil", [self.clause("ukuran", "<", 8)])
        revise_condition(self.kb, 2, [self.clause("ukuran", ">", 17)])
        rule = next(rule for rule in iter_rules(self.kb["root"]) if rule["id"] == 2)
        self.assertEqual(rule["kondisi"], [self.clause("ukuran", ">", 17)])
        self.assertEqual(infer(self.kb, hot)["kesimpulan"], "besar")
        self.assertEqual(infer(self.kb, self.red)["kesimpulan"], "merah")
        self.assertEqual(infer(self.kb, small)["kesimpulan"], "kecil")
        self.assertEqual(self.kb["riwayat"][-1]["aksi"], "kondisi_direvisi")
        self.assertEqual(self.kb["riwayat"][-1]["kondisi_sebelum"], [self.clause("ukuran", ">", 15)])
        snapshot = copy.deepcopy(self.kb)
        for rule_id, condition in [(0, [self.clause("ukuran", ">", 5)]),
                                   (99, [self.clause("ukuran", ">", 5)]),
                                   (2, [self.clause("ukuran", ">", 21)]),
                                   (2, [self.clause("ukuran", ">", 5)]),
                                   (2, [self.clause("ukuran", "!=", 10)])]:
            with self.subTest(rule_id=rule_id, condition=condition), self.assertRaises(RDRError):
                revise_condition(self.kb, rule_id, condition)
            self.assertEqual(self.kb, snapshot)
        with tempfile.NamedTemporaryFile(dir=Path.cwd(), delete=False) as file:
            path = Path(file.name)
        try:
            save_kb(self.kb, path)
            self.assertEqual(load_kb(path), self.kb)
        finally:
            path.unlink(missing_ok=True)
    def test_revise_conclusion_and_reject_approved_conflict(self):
        add_rule(self.kb, self.red, "merah", [self.clause("warna", "=", "merah")])
        add_rule(self.kb, self.blue, "biru", [self.clause("warna", "=", "biru")])
        old_history = copy.deepcopy(self.kb["riwayat"])
        revise_conclusion(self.kb, 1, "merah baru")
        self.assertEqual(infer(self.kb, self.red)["kesimpulan"], "merah baru")
        self.assertEqual(infer(self.kb, self.blue)["kesimpulan"], "biru")
        self.assertEqual(self.kb["riwayat"][:-1], old_history)
        self.assertEqual(self.kb["riwayat"][-1]["kesimpulan_sebelum"], "merah")
        self.assertEqual(self.kb["riwayat"][-1]["kesimpulan_sesudah"], "merah baru")
        self.assertEqual(self.kb["riwayat"][-1]["aksi"], "kesimpulan_direvisi")
        accept(self.kb, {"warna": "merah", "ukuran": 12})
        snapshot = copy.deepcopy(self.kb)
        for rule_id, conclusion in [(1, "lain"), (1, "  "), (1, "merah baru"), (999, "lain")]:
            with self.subTest(rule_id=rule_id, conclusion=conclusion), self.assertRaises(RDRError):
                revise_conclusion(self.kb, rule_id, conclusion)
            self.assertEqual(self.kb, snapshot)
        with tempfile.NamedTemporaryFile(dir=Path.cwd(), delete=False) as file:
            path = Path(file.name)
        try:
            save_kb(self.kb, path)
            self.assertEqual(load_kb(path), self.kb)
        finally:
            path.unlink(missing_ok=True)

    def test_revise_default_and_preserve_approved_cases(self):
        revise_conclusion(self.kb, 0, "default baru")
        self.assertEqual(self.kb["domain"]["kesimpulan_default"], "default baru")
        self.assertEqual(infer(self.kb, {})["kesimpulan"], "default baru")
        add_rule(self.kb, self.red, "merah", [self.clause("warna", "=", "merah")])
        accept(self.kb, self.blue)
        snapshot = copy.deepcopy(self.kb)
        with self.assertRaises(RDRError):
            revise_conclusion(self.kb, 0, "lain")
        self.assertEqual(self.kb, snapshot)

    def test_revise_conclusion_rejects_other_cornerstone_conflict(self):
        add_rule(self.kb, self.red, "merah", [self.clause("warna", "=", "merah")])
        add_rule(self.kb, self.blue, "biru", [self.clause("warna", "=", "biru")])
        self.kb["root"]["true_child"]["false_child"]["kasus_kunci"] = copy.deepcopy(self.red)
        snapshot = copy.deepcopy(self.kb)
        with self.assertRaisesRegex(RDRError, "kasus kunci rule lain"):
            revise_conclusion(self.kb, 1, "lain")
        self.assertEqual(self.kb, snapshot)

    def test_suggestions_distinguish_cornerstone(self):
        for item in suggestions(self.domain, self.blue, self.red):
            condition = [item["klausa"]]
            self.assertTrue(matches(condition, self.blue, self.domain))
            self.assertFalse(matches(condition, self.red, self.domain))

    def test_history_and_persistence(self):
        accept(self.kb, self.red)
        add_rule(self.kb, self.blue, "biru", [self.clause("warna", "=", "biru")])
        with tempfile.NamedTemporaryFile(dir=Path.cwd(), delete=False) as file:
            path = Path(file.name)
        try:
            save_kb(self.kb, path)
            self.assertEqual(load_kb(path), self.kb)
            self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))["riwayat"]), 2)
        finally:
            path.unlink(missing_ok=True)

    def test_zoo_dataset_and_incremental_examples(self):
        rows = list(zoo_rows())
        self.assertEqual(len(rows), 101)
        kb = new_kb(zoo_domain())
        for _, name, case, label in rows:
            if name not in {"aardvark", "chicken", "bass", "frog", "honeybee"}:
                continue
            previous = infer(kb, case)
            last = next(rule for rule in iter_rules(kb["root"]) if rule["id"] == previous["last_firing_id"])
            add_rule(kb, case, label, [item["klausa"] for item in suggestions(kb["domain"], case, last["kasus_kunci"])])
            self.assertEqual(infer(kb, case)["kesimpulan"], label)
            for rule in iter_rules(kb["root"]):
                if rule["kasus_kunci"] is not None:
                    self.assertEqual(infer(kb, rule["kasus_kunci"])["kesimpulan"], rule["kesimpulan"])
            if name == "frog":
                break


if __name__ == "__main__":
    unittest.main()
