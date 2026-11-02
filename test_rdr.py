import copy
import json
import tempfile
import unittest
from pathlib import Path

from main import zoo_domain, zoo_rows
from rdr import (RDRError, accept, add_attribute, add_rule, infer, iter_rules, load_kb, matches, new_kb,
                 save_kb, set_cornerstone_attribute, suggestions)


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

    def test_unknown_inference_and_false_conjunction(self):
        clauses = [self.clause("warna", "=", "merah"), self.clause("ukuran", ">", 5)]
        self.assertIsNone(matches(clauses, {"warna": "merah"}, self.domain))
        self.assertIs(matches(clauses, {"warna": "biru"}, self.domain), False)
        add_rule(self.kb, self.red, "merah besar", clauses)
        result = infer(self.kb, {"warna": "merah"})
        self.assertFalse(result["selesai"])
        self.assertIsNone(result["kesimpulan"])
        self.assertEqual(result["atribut_diperlukan"], ["ukuran"])
        self.assertEqual(infer(self.kb, {"warna": "biru"})["kesimpulan"], "default")
        snapshot = copy.deepcopy(self.kb)
        with self.assertRaises(RDRError):
            accept(self.kb, {"warna": "merah"})
        with self.assertRaises(RDRError):
            add_rule(self.kb, {"warna": "merah"}, "lain", [self.clause("warna", "=", "merah")])
        self.assertEqual(snapshot, self.kb)

    def test_add_attribute_and_complete_cornerstone(self):
        add_rule(self.kb, self.red, "merah", [self.clause("warna", "=", "merah")])
        original_history = copy.deepcopy(self.kb["riwayat"])
        add_attribute(self.kb, "fitur", {"tipe": "kategorikal", "nilai": ["ya", "tidak"]})
        self.assertIsNone(self.kb["root"]["true_child"]["kasus_kunci"]["fitur"])
        self.assertEqual(self.kb["riwayat"][:len(original_history)], original_history)
        new_case = {"warna": "merah", "fitur": "ya"}
        condition = [self.clause("fitur", "=", "ya")]
        with self.assertRaises(RDRError):
            add_rule(self.kb, new_case, "baru", condition)
        set_cornerstone_attribute(self.kb, 1, "fitur", "tidak")
        add_rule(self.kb, new_case, "baru", condition)
        self.assertEqual(infer(self.kb, self.red | {"fitur": "tidak"})["kesimpulan"], "merah")
        self.assertEqual(infer(self.kb, new_case)["kesimpulan"], "baru")
        with self.assertRaises(RDRError):
            set_cornerstone_attribute(self.kb, 1, "fitur", "ya")
        with tempfile.NamedTemporaryFile(dir=Path.cwd(), delete=False) as file:
            path = Path(file.name)
        try:
            save_kb(self.kb, path)
            self.assertEqual(load_kb(path), self.kb)
        finally:
            path.unlink(missing_ok=True)

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
