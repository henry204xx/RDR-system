import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from datasets import AUTOMOBILE_COLUMNS, guess_roles, prepare_dataset, read_table
from main import zoo_domain
from rdr import RDRError, infer, new_kb


class DatasetTests(unittest.TestCase):
    def test_zoo_preset(self):
        names, rows = read_table(Path("zoo/zoo.data"), "zoo")
        roles = guess_roles(names, rows, "zoo")
        domain, cases, skipped = prepare_dataset(names, rows, roles, "Zoo", "default")
        self.assertEqual(len(cases), 101)
        self.assertFalse(skipped)
        self.assertEqual(cases[0]["label"], "1")
        self.assertNotIn("type", domain["atribut"])
        self.assertNotIn("animal_name", domain["atribut"])
        self.assertEqual(infer(new_kb(domain), cases[0]["kasus"])["kesimpulan"], "default")

    def test_automobile_missing_and_label_are_not_features(self):
        names, rows = read_table(Path("automobile/imports-85.data"), "automobile")
        self.assertEqual(names, AUTOMOBILE_COLUMNS)
        roles = guess_roles(names, rows, "automobile")
        domain, cases, skipped = prepare_dataset(names, rows, roles, "Automobile", "default")
        self.assertEqual(len(cases) + len(skipped), 205)
        self.assertFalse(skipped)
        self.assertTrue(any(None in item["kasus"].values() for item in cases))
        self.assertEqual(roles[0], "label")
        self.assertNotIn("symboling", domain["atribut"])
        self.assertEqual(domain["atribut"]["make"]["tipe"], "kategorikal")
        self.assertEqual(domain["atribut"]["price"]["tipe"], "numerik")

    def test_label_optional_missing_labels_and_existing_schema(self):
        names = ["warna", "ukuran", "jawaban"]
        rows = [["biru", "4", "A"], ["merah", "?", "B"], ["biru", "5", "?"]]
        domain, cases, skipped = prepare_dataset(names, rows, ["kategorikal", "numerik", "label"], "uji", "default")
        self.assertEqual(len(cases), 3)
        self.assertFalse(skipped)
        self.assertIsNone(cases[1]["kasus"]["ukuran"])
        self.assertIsNone(cases[2]["label"])
        _, attached, _ = prepare_dataset(names, rows, ["kategorikal", "numerik", "abaikan"], "", "", domain)
        self.assertEqual(len(attached), 3)
        with self.assertRaises(RDRError):
            prepare_dataset(names, rows, ["abaikan", "numerik", "label"], "", "", domain)

    def test_malformed_csv_and_duplicate_columns(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=Path.cwd(), delete=False, newline="") as file:
            path = Path(file.name)
            csv.writer(file).writerows([["a", "a"], ["1", "2"]])
        try:
            with self.assertRaises(RDRError):
                read_table(path)
        finally:
            path.unlink(missing_ok=True)

    def test_attach_zoo_existing_schema(self):
        names, rows = read_table(Path("zoo/zoo.data"), "zoo")
        roles = guess_roles(names, rows, "zoo", zoo_domain())
        roles[-1] = "label"
        _, cases, skipped = prepare_dataset(names, rows, roles, "", "", zoo_domain())
        self.assertEqual(len(cases), 101)
        self.assertFalse(skipped)


class GUITests(unittest.TestCase):
    def test_gui_manual_domain_and_attribute(self):
        import tkinter as tk
        from gui import AttributeDialog, DomainDialog, RDRApp

        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk tidak tersedia: {error}")
        root.withdraw()
        try:
            app = RDRApp(root)
            dialog = DomainDialog(app)
            dialog.name.set("Automobile")
            dialog.attribute.set("fuel")
            dialog.values.set("diesel, gas")
            dialog.apply()
            self.assertIsNotNone(app.kb)
            app.inputs["fuel"].set("gas")
            dialog = AttributeDialog(app)
            dialog.name.set("doors")
            dialog.kind.set("numerik")
            with patch("gui.messagebox.showinfo"):
                dialog.apply()
            self.assertEqual(app.inputs["fuel"].get(), "gas")
            self.assertIsNone(app.get_case()["doors"])
            self.assertEqual(app.current_result()[1]["kesimpulan"], "Konsultasi lebih lanjut")
        finally:
            root.destroy()

    def test_gui_inference_correction_and_visualization(self):
        import tkinter as tk
        from gui import AttributeDialog, CornerstoneDialog, CorrectionDialog, RDRApp

        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk tidak tersedia: {error}")
        root.withdraw()
        try:
            app = RDRApp(root)
            domain = {"nama": "uji", "kesimpulan_default": "default", "atribut": {
                "warna": {"tipe": "kategorikal", "nilai": ["merah", "biru"]}}}
            app.set_kb(new_kb(domain), None, dirty=False)
            app.inputs["warna"].set("merah")
            app.run_inference()
            self.assertEqual(app.highlighted, [0])
            dialog = CorrectionDialog(app, {"warna": "merah"}, infer(app.kb, {"warna": "merah"}))
            dialog.conclusion.set("contoh")
            dialog.listbox.selection_set(0)
            with patch("gui.messagebox.showinfo"):
                dialog.apply()
            self.assertEqual(infer(app.kb, {"warna": "merah"})["kesimpulan"], "contoh")
            self.assertEqual(app.highlighted, [0, 1])
            self.assertGreater(len(app.canvas.find_all()), 2)
            self.assertTrue(app.dirty)
            attribute = AttributeDialog(app)
            attribute.name.set("fitur")
            attribute.values.set("ya, tidak")
            with patch("gui.messagebox.showinfo"):
                attribute.apply()
            self.assertEqual(app.inputs["warna"].get(), "merah")
            cornerstone = CornerstoneDialog(app)
            cornerstone.value.set("tidak")
            with patch("gui.messagebox.showinfo"):
                cornerstone.apply()
            self.assertEqual(app.kb["root"]["true_child"]["kasus_kunci"]["fitur"], "tidak")
            app.inputs["warna"].set("")
            app.run_inference()
            self.assertIn("Inferensi belum selesai", app.result.get("1.0", "end"))
            with patch("gui.messagebox.showwarning") as warning:
                app.approve()
                app.correct()
                self.assertEqual(warning.call_count, 2)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
