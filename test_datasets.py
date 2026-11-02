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
    def test_revise_conclusion_dialog(self):
        import tkinter as tk
        from gui import RDRApp, ReviseConclusionDialog
        from rdr import accept, add_rule

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
            case = {"warna": "merah"}
            add_rule(app.kb, case, "lama", [{"atribut": "warna", "operator": "=", "nilai": "merah"}])
            app.select_rule(1)
            app.revise_selected_conclusion()
            dialog = next(window for window in root.winfo_children() if isinstance(window, ReviseConclusionDialog))
            dialog.conclusion.set("baru")
            with patch("gui.messagebox.showinfo"):
                dialog.apply()
            self.assertEqual(infer(app.kb, case)["kesimpulan"], "baru")
            self.assertIn("baru", app.node_detail.get("1.0", "end"))
            accept(app.kb, case)
            dialog = ReviseConclusionDialog(app, app.kb["root"]["true_child"])
            dialog.conclusion.set("bertentangan")
            with patch("gui.messagebox.showerror") as error:
                dialog.apply()
                error.assert_called_once()
            self.assertEqual(infer(app.kb, case)["kesimpulan"], "baru")
            dialog.destroy()
        finally:
            root.destroy()

    def test_edit_candidate_and_revise_saved_rule(self):
        import tkinter as tk
        from gui import CorrectionDialog, RDRApp, ReviseConditionDialog
        from rdr import add_rule

        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk tidak tersedia: {error}")
        root.withdraw()
        try:
            app = RDRApp(root)
            domain = {"nama": "uji", "kesimpulan_default": "default", "atribut": {
                "cuaca": {"tipe": "kategorikal", "nilai": ["panas", "dingin"]}, "suhu": {"tipe": "numerik"}}}
            app.set_kb(new_kb(domain), None, dirty=False)
            add_rule(app.kb, {"cuaca": "panas", "suhu": 30}, "es", [{"atribut": "cuaca", "operator": "=", "nilai": "panas"}])
            case = {"cuaca": "panas", "suhu": 36}
            app.inputs["cuaca"].set("panas")
            app.inputs["suhu"].set("36")
            dialog = CorrectionDialog(app, case, infer(app.kb, case))
            dialog.conclusion.set("super dingin")
            dialog.listbox.selection_set(0)
            dialog.edit_candidates()
            self.assertEqual(dialog.editor.rows[0]["value"].get(), "33.0")
            dialog.editor.rows[0]["value"].set("34")
            with patch("gui.messagebox.showinfo"):
                dialog.apply()
            rule = app.kb["root"]["true_child"]["true_child"]
            self.assertEqual(rule["kondisi"][0]["nilai"], 34)
            app.select_rule(2)
            dialog = ReviseConditionDialog(app, rule)
            dialog.editor.rows[0]["value"].set("35")
            with patch("gui.messagebox.showinfo"):
                dialog.apply()
            self.assertEqual(app.kb["root"]["true_child"]["true_child"]["kondisi"][0]["nilai"], 35)
            self.assertIn('35.0', app.node_detail.get("1.0", "end"))
            dialog = ReviseConditionDialog(app, app.kb["root"]["true_child"]["true_child"])
            dialog.editor.rows[0]["value"].set("36")
            with patch("gui.messagebox.showerror") as error:
                dialog.apply()
                error.assert_called_once()
            self.assertEqual(app.kb["root"]["true_child"]["true_child"]["kondisi"][0]["nilai"], 35)
            dialog.destroy()
        finally:
            root.destroy()

    def test_condition_editor_conjunction_and_categorical_list(self):
        import tkinter as tk
        from gui import ConditionEditor

        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk tidak tersedia: {error}")
        root.withdraw()
        try:
            domain = {"nama": "uji", "kesimpulan_default": "default", "atribut": {
                "warna": {"tipe": "kategorikal", "nilai": ["merah", "biru,muda"]}, "suhu": {"tipe": "numerik"}}}
            editor = ConditionEditor(root, domain)
            condition = [{"atribut": "warna", "operator": "in", "nilai": ["merah", "biru,muda"]},
                         {"atribut": "suhu", "operator": ">", "nilai": 34}]
            editor.set_condition(condition)
            self.assertEqual(editor.get_condition(), condition)
            editor.rows[1]["value"].set("bukan angka")
            with self.assertRaises(RDRError):
                editor.get_condition()
        finally:
            root.destroy()

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
            self.assertNotIn("fitur", app.kb["root"]["true_child"]["kasus_kunci"])
            app.inputs["fitur"].set("ya")
            case, result = app.current_result()
            dialog = CorrectionDialog(app, case, result)
            dialog.conclusion.set("khusus")
            dialog.listbox.selection_set(0)
            with patch("gui.messagebox.showinfo"):
                dialog.apply()
            self.assertEqual(infer(app.kb, {"warna": "merah"})["kesimpulan"], "contoh")
            self.assertEqual(infer(app.kb, case)["kesimpulan"], "khusus")
            cornerstone = CornerstoneDialog(app)
            cornerstone.value.set("tidak")
            with patch("gui.messagebox.showinfo"):
                cornerstone.apply()
            self.assertEqual(app.kb["root"]["true_child"]["kasus_kunci"]["fitur"], "tidak")
            app.inputs["warna"].set("")
            app.run_inference()
            self.assertIn("Perhatian: kondisi dengan atribut kosong", app.result.get("1.0", "end"))
            with patch("gui.messagebox.showinfo"):
                app.approve()
            self.assertEqual(app.kb["riwayat"][-1]["aksi"], "disetujui")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
