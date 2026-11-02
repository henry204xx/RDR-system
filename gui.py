"""Antarmuka desktop untuk konsultasi dan akuisisi pengetahuan RDR."""

import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from rdr import (RDRError, accept, add_attribute, add_rule, infer, iter_rules, load_kb, new_kb, save_kb,
                 set_cornerstone_attribute, suggestions)


class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.content = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


def attribute_spec(kind, values):
    spec = {"tipe": kind}
    if kind == "kategorikal":
        text = values.strip()
        spec["nilai"] = json.loads(text) if text.startswith("[") else [item.strip() for item in text.split(",") if item.strip()]
    return spec


class DomainDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Buat KB baru")
        self.geometry("570x300")
        self.transient(app.root)
        self.grab_set()
        form = ttk.Frame(self, padding=15)
        form.pack(fill="both", expand=True)
        self.name = tk.StringVar(value="Domain baru")
        self.default = tk.StringVar(value="Konsultasi lebih lanjut")
        self.attribute = tk.StringVar()
        self.kind = tk.StringVar(value="kategorikal")
        self.values = tk.StringVar(value="tidak, ya")
        for row, (label, variable) in enumerate((("Nama domain", self.name), ("Kesimpulan default", self.default),
                                                  ("Nama atribut pertama", self.attribute))):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(form, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Label(form, text="Tipe atribut").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Combobox(form, textvariable=self.kind, state="readonly", values=["kategorikal", "numerik"]).grid(row=3, column=1, sticky="ew", padx=8)
        ttk.Label(form, text="Nilai kategorikal (pisahkan koma)").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.values).grid(row=4, column=1, sticky="ew", padx=8)
        form.columnconfigure(1, weight=1)
        ttk.Button(form, text="Buat KB", command=self.apply).grid(row=5, column=1, sticky="e", pady=10)

    def apply(self):
        try:
            domain = {"nama": self.name.get().strip(), "kesimpulan_default": self.default.get().strip(),
                      "atribut": {self.attribute.get().strip(): attribute_spec(self.kind.get(), self.values.get())}}
            kb = new_kb(domain)
        except (ValueError, RDRError) as error:
            messagebox.showerror("Domain tidak valid", str(error), parent=self)
            return
        if self.app.confirm_discard():
            self.app.set_kb(kb, None, dirty=True)
            self.destroy()


class CorrectionDialog(tk.Toplevel):
    def __init__(self, app, case, result):
        super().__init__(app.root)
        self.app, self.case = app, case
        self.title("Koreksi pakar")
        self.geometry("820x650")
        self.transient(app.root)
        self.grab_set()
        last = next(rule for rule in iter_rules(app.kb["root"]) if rule["id"] == result["last_firing_id"])
        self.options = suggestions(app.kb["domain"], case, last["kasus_kunci"])
        ttk.Label(self, text=f"Hasil saat ini: {result['kesimpulan']} | Rule terakhir: #{last['id']}", padding=10).pack(anchor="w")
        top = ttk.Frame(self, padding=(10, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Kesimpulan yang benar:").pack(side="left")
        self.conclusion = tk.StringVar()
        ttk.Entry(top, textvariable=self.conclusion).pack(side="left", fill="x", expand=True, padx=8)
        if last["kasus_kunci"] is None:
            text = "Root default belum mempunyai kasus kunci. Pilih atribut yang bermakna."
        elif not self.options:
            text = "Tidak ada perbedaan yang diketahui. Lengkapi kasus atau nilai kasus kunci, atau tambah atribut."
        else:
            text = "Pilih satu atau beberapa kandidat; semua pilihan digabung dengan AND."
        ttk.Label(self, text=text, padding=10, wraplength=760).pack(anchor="w")
        self.listbox = tk.Listbox(self, selectmode="multiple", exportselection=False, height=10)
        self.listbox.pack(fill="both", expand=True, padx=10)
        for item in self.options:
            self.listbox.insert("end", f"{item['atribut']}: baru={item['kasus_baru']!r}, kunci={item['kasus_kunci']!r} | {json.dumps(item['klausa'], ensure_ascii=False)}")
        ttk.Label(self, text="Atau isi kondisi JSON manual (menggantikan pilihan di atas):", padding=10).pack(anchor="w")
        self.manual = tk.Text(self, height=4, wrap="word")
        self.manual.pack(fill="x", padx=10)
        ttk.Label(self, text='Contoh: [{"atribut":"legs","operator":">=","nilai":4}]', padding=10).pack(anchor="w")
        buttons = ttk.Frame(self, padding=10)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Batal", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Tambahkan rule", command=self.apply).pack(side="right", padx=5)

    def apply(self):
        try:
            text = self.manual.get("1.0", "end").strip()
            condition = json.loads(text) if text else [self.options[index]["klausa"] for index in self.listbox.curselection()]
            result = add_rule(self.app.kb, self.case, self.conclusion.get().strip(), condition)
        except (RDRError, ValueError) as error:
            messagebox.showerror("Rule ditolak", str(error), parent=self)
            return
        self.app.dirty = True
        self.app.show_result(result)
        self.app.refresh_views()
        self.destroy()
        messagebox.showinfo("Rule ditambahkan", "Rule berhasil ditambahkan. Simpan KB untuk mempertahankan perubahan.", parent=self.app.root)


def parse_value(raw, spec):
    raw = raw.strip()
    if not raw:
        return None
    if spec["tipe"] == "numerik":
        try:
            return float(raw)
        except ValueError:
            raise RDRError("Nilai numerik harus berupa angka.") from None
    return raw


class AttributeDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Tambah atribut")
        self.geometry("860x620")
        self.transient(app.root)
        self.grab_set()
        header = ttk.Frame(self, padding=10)
        header.pack(fill="x")
        self.name = tk.StringVar()
        self.kind = tk.StringVar(value="kategorikal")
        self.values = tk.StringVar(value="tidak, ya")
        ttk.Label(header, text="Nama atribut:").grid(row=0, column=0, sticky="w")
        ttk.Entry(header, textvariable=self.name).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(header, text="Tipe:").grid(row=0, column=2, padx=5)
        ttk.Combobox(header, textvariable=self.kind, state="readonly", values=["kategorikal", "numerik"], width=15).grid(row=0, column=3)
        ttk.Label(header, text="Nilai kategorikal (pisahkan koma):").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(header, textvariable=self.values).grid(row=1, column=1, columnspan=3, sticky="ew", padx=5)
        header.columnconfigure(1, weight=1)
        ttk.Label(self, text="Masukkan nilai yang benar-benar diketahui untuk kasus kunci lama. Kosong = tidak diketahui, bukan 'tidak'.",
                  padding=10, wraplength=800).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10)
        self.cornerstones = {}
        for index, rule in enumerate(rule for rule in iter_rules(app.kb["root"]) if rule["kasus_kunci"] is not None):
            variable = tk.StringVar()
            self.cornerstones[rule["id"]] = variable
            sample = json.dumps(rule["kasus_kunci"], ensure_ascii=False)
            ttk.Label(self.scroll.content, text=f"Rule #{rule['id']} ({rule['kesimpulan']}): {sample[:100]}", wraplength=570).grid(row=index, column=0, sticky="w", padx=5, pady=4)
            ttk.Entry(self.scroll.content, textvariable=variable, width=20).grid(row=index, column=1, padx=5)
        self.scroll.content.columnconfigure(0, weight=1)
        footer = ttk.Frame(self, padding=10)
        footer.pack(fill="x")
        ttk.Button(footer, text="Batal", command=self.destroy).pack(side="right")
        ttk.Button(footer, text="Tambah", command=self.apply).pack(side="right", padx=5)

    def apply(self):
        try:
            spec = attribute_spec(self.kind.get(), self.values.get())
            values = {rule_id: parse_value(variable.get(), spec) for rule_id, variable in self.cornerstones.items()}
            add_attribute(self.app.kb, self.name.get().strip(), spec, values)
        except (ValueError, RDRError) as error:
            messagebox.showerror("Atribut tidak ditambahkan", str(error), parent=self)
            return
        self.app.dirty = True
        self.app.rebuild_form()
        self.app.refresh_views()
        self.destroy()
        messagebox.showinfo("Atribut ditambahkan", "Simpan KB. Nilai kosong tetap tidak diketahui dan dapat dilengkapi nanti.", parent=self.app.root)


class CornerstoneDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Lengkapi nilai kasus kunci")
        self.geometry("780x460")
        self.transient(app.root)
        self.grab_set()
        ttk.Label(self, text="Hanya isi nilai yang diketahui. Nilai yang sudah diketahui tidak dapat ditimpa.", padding=10).pack(anchor="w")
        self.options = [(rule, name) for rule in iter_rules(app.kb["root"]) if rule["kasus_kunci"] is not None
                        for name in app.kb["domain"]["atribut"] if rule["kasus_kunci"].get(name) is None]
        self.selection = ttk.Combobox(self, state="readonly", values=[f"Rule #{rule['id']} | {name}" for rule, name in self.options])
        self.selection.pack(fill="x", padx=10)
        self.selection.bind("<<ComboboxSelected>>", lambda event: self.show_case())
        self.details = tk.Text(self, height=10, wrap="word", state="disabled")
        self.details.pack(fill="both", expand=True, padx=10, pady=10)
        row = ttk.Frame(self, padding=10)
        row.pack(fill="x")
        ttk.Label(row, text="Nilai:").pack(side="left")
        self.value = tk.StringVar()
        ttk.Entry(row, textvariable=self.value).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row, text="Simpan nilai", command=self.apply).pack(side="right")
        if self.options:
            self.selection.current(0)
            self.show_case()
        else:
            app.set_text(self.details, "Tidak ada nilai kasus kunci yang belum diketahui.")

    def show_case(self):
        index = self.selection.current()
        if index >= 0:
            rule, name = self.options[index]
            spec = self.app.kb["domain"]["atribut"][name]
            self.app.set_text(self.details, f"Rule #{rule['id']} | {name}: {json.dumps(spec, ensure_ascii=False)}\n\n"
                              + json.dumps(rule["kasus_kunci"], ensure_ascii=False, indent=2))

    def apply(self):
        index = self.selection.current()
        if index < 0:
            return
        rule, name = self.options[index]
        try:
            value = parse_value(self.value.get(), self.app.kb["domain"]["atribut"][name])
            set_cornerstone_attribute(self.app.kb, rule["id"], name, value)
        except (RDRError, ValueError) as error:
            messagebox.showerror("Nilai tidak disimpan", str(error), parent=self)
            return
        self.app.dirty = True
        self.app.refresh_views()
        self.destroy()
        messagebox.showinfo("Kasus kunci dilengkapi", "Nilai dicatat. Simpan KB untuk mempertahankan perubahan.", parent=self.app.root)


class RDRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistem Pakar Ripple Down Rules")
        self.root.geometry("1100x780")
        self.root.minsize(760, 550)
        self.kb, self.path, self.dirty = None, None, False
        self.highlighted = []
        self.inputs = {}
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self):
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")
        for label, command in (("Buat KB baru", self.new_domain), ("Buka KB", self.open_kb),
                               ("Simpan KB", self.save), ("Simpan sebagai", self.save_as),
                               ("Tambah atribut", self.add_attribute), ("Lengkapi kasus kunci", self.complete_cornerstone)):
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=3)
        self.status = tk.StringVar(value="Buat KB baru atau buka KB yang tersimpan.")
        ttk.Label(self.root, textvariable=self.status, padding=(10, 2)).pack(fill="x")
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        consult = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(consult, text="Konsultasi")
        ttk.Label(consult, text="Isi atribut yang diketahui. Kosong berarti tidak diketahui.").pack(anchor="w", pady=(0, 8))
        split = ttk.Panedwindow(consult, orient="horizontal")
        split.pack(fill="both", expand=True, pady=8)
        form_panel = ttk.Frame(split, padding=4)
        result_panel = ttk.Frame(split, padding=4)
        split.add(form_panel, weight=1)
        split.add(result_panel, weight=1)
        ttk.Label(form_panel, text="Atribut kasus").pack(anchor="w")
        self.form = ScrollFrame(form_panel)
        self.form.pack(fill="both", expand=True)
        actions = ttk.Frame(result_panel)
        actions.pack(fill="x")
        ttk.Button(actions, text="Inferensi", command=self.run_inference).pack(side="left")
        ttk.Button(actions, text="Pakar setuju", command=self.approve).pack(side="left", padx=5)
        ttk.Button(actions, text="Pakar koreksi", command=self.correct).pack(side="left")
        ttk.Label(result_panel, text="Hasil, kasus, dan jalur").pack(anchor="w", pady=8)
        self.result = tk.Text(result_panel, wrap="word", state="disabled")
        self.result.pack(fill="both", expand=True)

        graph = ttk.Frame(self.tabs)
        self.tabs.add(graph, text="Visualisasi pohon")
        ttk.Label(graph, text="False di kiri, true di kanan. Biru = jalur inferensi terakhir; klik node untuk detail.", padding=8).pack(anchor="w")
        graph_split = ttk.Panedwindow(graph, orient="horizontal")
        graph_split.pack(fill="both", expand=True)
        canvas_frame = ttk.Frame(graph_split)
        detail_frame = ttk.Frame(graph_split, padding=8)
        graph_split.add(canvas_frame, weight=4)
        graph_split.add(detail_frame, weight=1)
        self.canvas = tk.Canvas(canvas_frame, background="white", highlightthickness=0)
        xscroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        yscroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        ttk.Label(detail_frame, text="Detail node").pack(anchor="w")
        self.node_detail = tk.Text(detail_frame, width=35, wrap="word", state="disabled")
        self.node_detail.pack(fill="both", expand=True)
        history_panel = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(history_panel, text="Riwayat")
        self.history = tk.Text(history_panel, wrap="word", state="disabled")
        history_scroll = ttk.Scrollbar(history_panel, command=self.history.yview)
        self.history.configure(yscrollcommand=history_scroll.set)
        self.history.pack(side="left", fill="both", expand=True)
        history_scroll.pack(side="right", fill="y")

    def confirm_discard(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("Perubahan belum disimpan", "Simpan perubahan KB sebelum melanjutkan?", parent=self.root)
        if answer is None:
            return False
        return self.save() if answer else True

    def new_domain(self):
        DomainDialog(self)

    def add_attribute(self):
        if self.require_kb():
            AttributeDialog(self)

    def complete_cornerstone(self):
        if self.require_kb():
            CornerstoneDialog(self)

    def open_kb(self):
        path = filedialog.askopenfilename(parent=self.root, title="Buka KB", filetypes=[("JSON", "*.json"), ("Semua file", "*.*")])
        if not path:
            return
        try:
            kb = load_kb(path)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
            messagebox.showerror("KB tidak valid", str(error), parent=self.root)
            return
        if self.confirm_discard():
            self.set_kb(kb, path, dirty=False)

    def set_kb(self, kb, path, dirty):
        self.kb, self.path, self.dirty = kb, path, dirty
        self.highlighted = []
        self.build_form()
        self.set_text(self.result, "Masukkan atribut yang diketahui, lalu tekan Inferensi.")
        self.set_text(self.node_detail, "Klik node untuk melihat detail.")
        self.refresh_views()

    def build_form(self, previous=None):
        for child in self.form.content.winfo_children():
            child.destroy()
        self.inputs = {}
        for index, (name, spec) in enumerate(self.kb["domain"]["atribut"].items()):
            ttk.Label(self.form.content, text=f"{name} ({spec['tipe']})").grid(row=index, column=0, sticky="w", padx=5, pady=3)
            variable = tk.StringVar(value=(previous or {}).get(name, ""))
            self.inputs[name] = variable
            if spec["tipe"] == "kategorikal":
                widget = ttk.Combobox(self.form.content, textvariable=variable, values=[""] + spec["nilai"], state="readonly")
            else:
                widget = ttk.Entry(self.form.content, textvariable=variable)
            widget.grid(row=index, column=1, sticky="ew", padx=5, pady=3)
            variable.trace_add("write", self.input_changed)
        self.form.content.columnconfigure(1, weight=1)

    def input_changed(self, *_):
        self.highlighted = []
        self.set_text(self.result, "Kasus berubah. Tekan Inferensi untuk melihat hasil terbaru.")
        self.render_tree()

    def rebuild_form(self):
        previous = {name: variable.get() for name, variable in self.inputs.items()}
        self.build_form(previous)
        self.highlighted = []
        self.set_text(self.result, "Skema berubah. Tekan Inferensi untuk memeriksa kasus kembali.")

    def get_case(self):
        case = {}
        for name, spec in self.kb["domain"]["atribut"].items():
            try:
                case[name] = parse_value(self.inputs[name].get(), spec)
            except RDRError:
                raise RDRError(f"{name} harus berupa angka.") from None
        return case

    def require_kb(self):
        if self.kb is None:
            messagebox.showwarning("KB belum dibuka", "Buat atau buka KB terlebih dahulu.", parent=self.root)
            return False
        return True

    def current_result(self):
        if not self.require_kb():
            return None
        try:
            case = self.get_case()
            result = infer(self.kb, case)
        except RDRError as error:
            messagebox.showerror("Kasus tidak valid", str(error), parent=self.root)
            return None
        self.show_result(result, case)
        return case, result

    def run_inference(self):
        self.current_result()

    def show_result(self, result, case=None):
        if case is None:
            case = self.get_case()
        path = " -> ".join(f"#{step['id']} ({'unknown' if step['terpenuhi'] is None else 'true' if step['terpenuhi'] else 'false'})" for step in result["jalur"])
        if result["selesai"]:
            outcome = f"Kesimpulan: {result['kesimpulan']}"
        else:
            outcome = (f"Inferensi belum selesai. Lengkapi: {', '.join(result['atribut_diperlukan'])}\n"
                       f"Kesimpulan sementara (belum final): {result['kesimpulan_sementara']}")
        text = f"{outcome}\nRule terakhir: #{result['last_firing_id']}\nJalur: {path}\n\nKasus:\n{json.dumps(case, ensure_ascii=False, indent=2)}"
        self.set_text(self.result, text)
        self.highlighted = [step["id"] for step in result["jalur"]]
        self.render_tree()

    def approve(self):
        current = self.current_result()
        if current and not current[1]["selesai"]:
            messagebox.showwarning("Inferensi belum selesai", "Lengkapi atribut yang diperlukan sebelum persetujuan.", parent=self.root)
        elif current:
            accept(self.kb, current[0])
            self.dirty = True
            self.refresh_views()
            messagebox.showinfo("Disetujui", "Persetujuan dicatat. Simpan KB untuk mempertahankan riwayat.", parent=self.root)

    def correct(self):
        current = self.current_result()
        if current and not current[1]["selesai"]:
            messagebox.showwarning("Inferensi belum selesai", "Lengkapi atribut yang diperlukan sebelum koreksi.", parent=self.root)
        elif current:
            CorrectionDialog(self, *current)

    def refresh_views(self):
        if self.kb is None:
            return
        location = self.path or "belum disimpan"
        self.status.set(f"Domain: {self.kb['domain']['nama']} | KB: {location}{' *' if self.dirty else ''}")
        self.set_text(self.history, json.dumps(self.kb["riwayat"], ensure_ascii=False, indent=2))
        self.render_tree()

    def render_tree(self):
        self.canvas.delete("all")
        if self.kb is None:
            return
        positions, ordered = {}, []
        stack = []
        node, depth = self.kb["root"], 0
        while stack or node is not None:
            while node is not None:
                stack.append((node, depth))
                node, depth = node["false_child"], depth + 1
            node, depth = stack.pop()
            ordered.append((node, depth))
            positions[node["id"]] = (120 + (len(ordered) - 1) * 225, 65 + depth * 125)
            node, depth = node["true_child"], depth + 1
        path_edges = set(zip(self.highlighted, self.highlighted[1:]))
        for rule, _ in ordered:
            x, y = positions[rule["id"]]
            for label, key in (("false", "false_child"), ("true", "true_child")):
                child = rule[key]
                if child is None:
                    continue
                child_x, child_y = positions[child["id"]]
                active = (rule["id"], child["id"]) in path_edges
                color = "#1764aa" if active else "#84909b"
                self.canvas.create_line(x, y + 34, child_x, child_y - 34, fill=color, width=3 if active else 1.5, arrow="last")
                self.canvas.create_text((x + child_x) / 2, (y + child_y) / 2, text=label, fill=color, font=("Segoe UI", 9, "bold"))
        for rule, _ in ordered:
            x, y = positions[rule["id"]]
            active = rule["id"] in self.highlighted
            tag = f"rule_{rule['id']}"
            self.canvas.create_rectangle(x - 100, y - 34, x + 100, y + 34, fill="#e6f3ff" if active else "#f6f7f9",
                                         outline="#1764aa" if active else "#8d99a6", width=2, tags=tag)
            conclusion = rule["kesimpulan"]
            if len(conclusion) > 25:
                conclusion = conclusion[:22] + "..."
            condition = "TRUE" if rule["kondisi"] is None else f"{len(rule['kondisi'])} klausa"
            self.canvas.create_text(x, y, text=f"#{rule['id']}  |  {condition}\n{conclusion}", width=185,
                                    justify="center", tags=tag, font=("Segoe UI", 10))
            self.canvas.tag_bind(tag, "<Button-1>", lambda event, selected=rule: self.set_text(
                self.node_detail, json.dumps({key: value for key, value in selected.items() if key not in ("true_child", "false_child")}, ensure_ascii=False, indent=2)))
        max_depth = max(depth for _, depth in ordered)
        self.canvas.configure(scrollregion=(0, 0, max(240, len(ordered) * 225 + 20), max(130, (max_depth + 1) * 125 + 20)))

    @staticmethod
    def set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def save(self):
        if not self.require_kb():
            return False
        if self.path is None:
            return self.save_as()
        try:
            save_kb(self.kb, self.path)
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror("Gagal menyimpan", str(error), parent=self.root)
            return False
        self.dirty = False
        self.refresh_views()
        return True

    def save_as(self):
        if not self.require_kb():
            return False
        path = filedialog.asksaveasfilename(parent=self.root, title="Simpan KB", defaultextension=".json",
                                           filetypes=[("JSON", "*.json"), ("Semua file", "*.*")])
        if not path:
            return False
        old_path = self.path
        self.path = path
        if self.save():
            return True
        self.path = old_path
        return False

    def close(self):
        if self.confirm_discard():
            self.root.destroy()


def main():
    root = tk.Tk()
    RDRApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
