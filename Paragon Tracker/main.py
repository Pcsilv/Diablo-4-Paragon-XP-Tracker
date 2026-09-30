"""
Diablo 4 Paragon 300 XP Tracker
Interface Tkinter (biblioteca padrão do Python: nada a instalar além do openpyxl).
Toda a lógica de XP está em paragon_core.py e usa a tabela da planilha .xlsx.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

import paragon_core as pc

APP_TITLE = "Diablo 4 Paragon 300 XP Tracker"
PROGRESS_FILE = os.path.join(pc.app_dir(), "progress.json")

# Paleta escura estilo Diablo
BG = "#000000"
PANEL = "#1d1714"
TRACK = "#2a201c"
BORDER = "#4a3a30"
GOLD = "#e1ad01"
TEXT = "#FFFFFF"
DIM = "#9a8a78"
RED = "#b3241b"
RED_DARK = "#7d1712"
BLUE = "#3f7fbf"
WARN = "#e59a3c"
ERR = "#ff5a4d"
FONT = "Segoe UI"

# #d9b46a gold

# --------------------------------------------------------------------------
# Persistência
# --------------------------------------------------------------------------
def load_progress() -> int:
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            xp = json.load(f).get("xp", 0)
        return xp if isinstance(xp, int) and not isinstance(xp, bool) and xp >= 0 else 0
    except (OSError, ValueError, AttributeError):
        return 0


def save_progress(xp: int, table: pc.ParagonTable) -> bool:
    data = {"xp": xp, "total": table.total, "source": table.source}
    tmp = PROGRESS_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, PROGRESS_FILE)  # gravação atômica
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# Barra de progresso desenhada em Canvas (largura calculada com inteiros)
# --------------------------------------------------------------------------
class Bar(tk.Canvas):
    def __init__(self, master, height, fill, font):
        super().__init__(master, height=height, highlightthickness=0, bd=0, bg=BG)
        self.fill, self.font = fill, font
        self.num, self.den, self.text = 0, 1, ""
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, num: int, den: int, text: str):
        self.num, self.den, self.text = num, den, text
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2:
            return
        self.create_rectangle(0, 0, w - 1, h - 1, fill=TRACK, outline=BORDER)
        fw = (w - 2) * self.num // self.den if self.den else 0
        if self.num > 0:
            fw = max(fw, 1)
        if fw > 0:
            self.create_rectangle(1, 1, 1 + fw, h - 2, fill=self.fill, outline="")
        # sombra + texto centralizado
        self.create_text(w // 2 + 1, h // 2 + 1, text=self.text, fill="#000000", font=self.font)
        self.create_text(w // 2, h // 2, text=self.text, fill="#ffffff", font=self.font)


# --------------------------------------------------------------------------
# Aplicativo
# --------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self, table: pc.ParagonTable):
        super().__init__()
        self.table = table
        self._busy = False  # evita loops entre campos sincronizados
        self.source = "total"  # último grupo editado: "level" ou "total"
        self.xp = 0

        self.title(APP_TITLE)
        self.configure(bg=BG)
        self.minsize(720, 760)
        self.geometry("780x820")

        self.build_ui()
        self.setup_events()
        self.setup_xp_table()

        self.refresh(self.table.clamp(load_progress()), [], "total", commit=True)
        if table.warnings:
            self.say(" ".join(table.warnings), "warn")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.total_entry.focus_set()

    # ---------------- construção da interface ----------------
    def _lbl(self, parent, text="", size=11, bold=False, color=TEXT, **kw):
        return tk.Label(
            parent, text=text, bg=kw.pop("bg", BG), fg=color,
            font=(FONT, size, "bold" if bold else "normal"), **kw,
        )

    def build_ui(self):
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True, padx=28, pady=20)

        self._lbl(root, "DIABLO PARAGON XP TRACKER", 20, True, GOLD).pack()
        self._lbl(root, "Total Progress to Paragon 300", 12, False, DIM).pack(pady=(2, 10))

        # barra principal
        self.main_bar = Bar(root, 46, RED, (FONT, 18, "bold"))
        self.main_bar.pack(fill="x")

        self.lbl_level = self._lbl(root, "PARAGON 0", 26, True, GOLD)
        self.lbl_level.pack(pady=(12, 0))
        self.lbl_ratio = self._lbl(root, "", 12, False, TEXT)
        self.lbl_ratio.pack(pady=(0, 10))

        # cartões: acumulado / restante / total
        cards = tk.Frame(root, bg=BG)
        cards.pack(fill="x")
        self.card_vals = {}
        for i, (key, title) in enumerate(
            [("acc", "Cumulated XP"), ("rem", "Remaining XP until P300"), ("tot", "Total XP")]
        ):
            cards.columnconfigure(i, weight=1, uniform="c")
            f = tk.Frame(cards, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            f.grid(row=0, column=i, sticky="nsew", padx=4)
            self._lbl(f, title, 10, False, DIM, bg=PANEL).pack(pady=(8, 0))
            v = self._lbl(f, "0", 13, True, TEXT, bg=PANEL)
            v.pack(pady=(0, 8), padx=6)
            self.card_vals[key] = v

        # nível atual
        self._lbl(root, "Current Level Progress", 11, True, GOLD).pack(pady=(18, 4))
        self.level_bar = Bar(root, 28, BLUE, (FONT, 12, "bold"))
        self.level_bar.pack(fill="x")
        self.lbl_in_level = self._lbl(root, "", 12, False, TEXT)
        self.lbl_in_level.pack(pady=(8, 0))
        self.lbl_next = self._lbl(root, "", 11, False, DIM)
        self.lbl_next.pack()

        # entrada
        tk.Frame(root, bg=BORDER, height=1).pack(fill="x", pady=(18, 10))
        self._lbl(root, "Refresh Progress", 13, True, GOLD).pack()

        self.level_var = tk.StringVar()
        self.inlvl_var = tk.StringVar()
        self.total_var = tk.StringVar()

        form = tk.Frame(root, bg=BG)
        form.pack(pady=8)
        entry_kw = dict(
            bg=PANEL, fg=TEXT, insertbackground=GOLD, relief="flat",
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=GOLD,
            font=(FONT, 14),
        )

        self._lbl(form, "Current Level").grid(row=0, column=0, padx=8, sticky="w")
        self._lbl(form, "XP on this level").grid(row=0, column=1, padx=8, sticky="w")
        self.level_spin = tk.Spinbox(
            form, from_=0, to=self.table.max_level, width=8, textvariable=self.level_var,
            buttonbackground=TRACK, **entry_kw,
        )
        self.level_spin.grid(row=1, column=0, padx=8, pady=2, ipady=4)
        self.inlvl_entry = tk.Entry(form, width=20, textvariable=self.inlvl_var, **entry_kw)
        self.inlvl_entry.grid(row=1, column=1, padx=8, pady=2, ipady=4)

        self._lbl(form, "— OR —", 10, False, DIM).grid(row=2, column=0, columnspan=2, pady=6)

        self._lbl(form, "Total cumulated XP").grid(row=3, column=0, columnspan=2)
        self.total_entry = tk.Entry(form, width=30, textvariable=self.total_var, justify="center", **entry_kw)
        self.total_entry.grid(row=4, column=0, columnspan=2, pady=2, ipady=6)

        self.btn = tk.Button(
            root, text="SAVE", command=self.commit, bg=RED_DARK, fg="white",
            activebackground=RED, activeforeground="white", relief="flat",
            font=(FONT, 12, "bold"), padx=24, pady=6, cursor="hand2",
        )
        self.btn.pack(pady=(6, 6))

        self.lbl_msg = self._lbl(root, "", 10, False, DIM, wraplength=700, justify="center")
        self.lbl_msg.pack(fill="x")

    def setup_events(self):
        # atualização em tempo real: qualquer alteração recalcula na hora
        self.level_var.trace_add("write", lambda *a: self._on_edit("level"))
        self.inlvl_var.trace_add("write", lambda *a: self._on_edit("level"))
        self.total_var.trace_add("write", lambda *a: self._on_edit("total"))
        for w in (self.level_spin, self.inlvl_entry, self.total_entry):
            w.bind("<Return>", lambda e: self.commit())
            w.bind("<KP_Enter>", lambda e: self.commit())
            w.bind("<FocusOut>", lambda e: self.commit())
        self.bind("<Return>", lambda e: self.commit())

    # ---------------- lógica de atualização ----------------
    def _on_edit(self, source: str):
        if self._busy:
            return
        self.source = source
        self.apply(commit=False)

    def commit(self):
        """Enter / botão / sair do campo: recalcula e normaliza (formata) os campos."""
        if not self._busy:
            self.apply(commit=True)

    def apply(self, commit: bool):
        if self.source == "level":
            try:
                level = pc.parse_int(self.level_var.get(), thousands=False)
            except ValueError as e:
                return self.say(f"Current Level: {e}", "error")
            txt = self.inlvl_var.get().strip()
            try:
                in_xp = pc.parse_int(txt) if txt else 0
            except ValueError as e:
                return self.say(f"XP on this Level: {e}", "error")
            xp, warns = self.table.resolve_level(level, in_xp)
        else:
            try:
                xp = pc.parse_int(self.total_var.get())
            except ValueError as e:
                return self.say(f"Total cumulated XP: {e}", "error")
            xp, warns = self.table.resolve_total(xp)
        self.refresh(xp, warns, self.source, commit)

    def refresh(self, xp: int, warns: list, source: str, commit: bool):
        pos = self.table.locate(xp)
        self.xp = pos.xp
        self.render(pos)

        self._busy = True  # escrever nos campos sem disparar novo cálculo
        try:
            if source == "level":
                self.total_var.set(pc.fmt_int(pos.xp))
                if commit:
                    self.level_var.set(str(pos.level))
                    self.inlvl_var.set(pc.fmt_int(pos.in_level))
            else:
                self.level_var.set(str(pos.level))
                self.inlvl_var.set(pc.fmt_int(pos.in_level))
                if commit:
                    self.total_var.set(pc.fmt_int(pos.xp))
        finally:
            self._busy = False

        saved = save_progress(pos.xp, self.table)
        if warns:
            self.say(" ".join(warns), "warn")
        elif not saved:
            self.say("Não consegui salvar progress.json (pasta sem permissão de escrita?).", "warn")
        elif pos.next_level is None:
            self.say(f"Paragon {self.table.max_level} Reached!", "ok")
        else:
            self.say("Progress Saved", "dim")

    def render(self, pos: pc.Position):
        t = self.table
        self.main_bar.set(pos.xp, t.total, pc.fmt_pct(pos.xp, t.total))
        self.lbl_level.configure(text=f"PARAGON {pos.level}")
        self.lbl_ratio.configure(text=f"{pc.fmt_int(pos.xp)} / {pc.fmt_int(t.total)} XP")
        self.card_vals["acc"].configure(text=pc.fmt_int(pos.xp))
        self.card_vals["rem"].configure(text=pc.fmt_int(pos.total_remaining))
        self.card_vals["tot"].configure(text=pc.fmt_int(t.total))

        if pos.next_level is None:
            self.level_bar.set(1, 1, "100,00%")
            self.lbl_in_level.configure(text=f"Max Paragon (P{t.max_level}) Reached")
            self.lbl_next.configure(text="Remaining XP to the next level: 0 XP")
        else:
            self.level_bar.set(pos.in_level, pos.span, pc.fmt_pct(pos.in_level, pos.span))
            self.lbl_in_level.configure(
                text=f"XP on this level: {pc.fmt_int(pos.in_level)} / {pc.fmt_int(pos.span)}"
            )
            self.lbl_next.configure(
                text=f"Remaining to P{pos.next_level}: {pc.fmt_int(pos.level_remaining)} XP"
            )

    def say(self, text: str, kind: str = "dim"):
        color = {"error": ERR, "warn": WARN, "ok": GOLD, "dim": DIM}.get(kind, DIM)
        self.lbl_msg.configure(text=text, fg=color)
    
    # ---------------- tabela de consulta: XP por nível (somente leitura) ----------------
    def setup_xp_table(self):
        """Cria só o botão discreto no canto inferior esquerdo. O painel da tabela é criado ao abrir."""
        self._xp_panel = None
        self._xp_tree = None
        self._xp_style = None
        self._xp_size = 0
        self.xp_btn = tk.Button(
            self, text="XP Table", command=self.open_xp_table,
            bg=PANEL, fg=DIM, activebackground=TRACK, activeforeground=GOLD,
            relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDER,
            font=(FONT, 9), padx=10, pady=0, cursor="hand2",
        )
        # place() é relativo à janela: relx=0/rely=1 = canto inferior esquerdo; anchor="sw" prende
        # o canto do botão nesse ponto; x/y são só a margem (não é posição absoluta).
        self.xp_btn.place(relx=0.0, rely=1.0, x=12, y=-10, anchor="sw")
        self.xp_btn.bind("<Enter>", lambda e: self.xp_btn.configure(fg=GOLD))
        self.xp_btn.bind("<Leave>", lambda e: self.xp_btn.configure(fg=DIM))
        self.bind("<Escape>", lambda e: self.close_xp_table())

    def _build_xp_table(self):
        st = ttk.Style(self)
        st.theme_use("clam")  # permite cores customizadas (o app não usa outros widgets ttk)
        st.configure("XP.Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                     bordercolor=BORDER, borderwidth=0, rowheight=27, font=(FONT, 11))
        st.map("XP.Treeview", background=[("selected", PANEL)], foreground=[("selected", TEXT)])
        st.configure("XP.Treeview.Heading", background=TRACK, foreground=GOLD, relief="flat",
                     bordercolor=BORDER, font=(FONT, 11, "bold"))
        st.map("XP.Treeview.Heading", background=[("active", TRACK)])
        st.configure("XP.Vertical.TScrollbar", background=TRACK, troughcolor=BG, bordercolor=BORDER,
                     arrowcolor=GOLD, lightcolor=TRACK, darkcolor=TRACK)
        st.map("XP.Vertical.TScrollbar", background=[("active", BORDER)])
        self._xp_style = st

        p = tk.Frame(self, bg=BG)
        self._xp_panel = p

        top = tk.Frame(p, bg=BG)
        top.pack(fill="x", padx=28, pady=(20, 0))
        tk.Button(
            top, text="← Back", command=self.close_xp_table, bg=RED_DARK, fg="white",
            activebackground=RED, activeforeground="white", relief="flat",
            font=(FONT, 10, "bold"), padx=14, pady=3, cursor="hand2",
        ).pack(side="left")

        self._lbl(p, "XP PER LEVEL", 20, True, GOLD).pack(pady=(0, 2))
        self._lbl(p, "Level N: XP to next level = XP to go from PN to PN+1  ·  "
                     "Cumulative XP = total XP to reach PN", 10, False, DIM).pack()
        self._lbl(p, f"Reference only · values read from {self.table.source}", 10, False, DIM).pack(pady=(0, 8))

        box = tk.Frame(p, bg=BG)
        box.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        tree = ttk.Treeview(box, columns=("level", "next", "cum"), show="headings",
                            selectmode="none", style="XP.Treeview")  # selectmode="none": sem seleção/edição
        tree.heading("level", text="Level", anchor="center")
        tree.heading("next", text="XP to next level", anchor="e")
        tree.heading("cum", text="Cumulative XP", anchor="e")
        tree.column("level", width=110, minwidth=90, anchor="center")
        tree.column("next", width=250, minwidth=150, anchor="e")
        tree.column("cum", width=300, minwidth=170, anchor="e")
        tree.tag_configure("even", background=PANEL)
        tree.tag_configure("odd", background="#241c18")
        tree.tag_configure("current", background="#3b3008", foreground=GOLD)
        # impede arrastar as bordas do cabeçalho (redimensionar colunas)
        tree.bind("<Button-1>", lambda e: "break" if tree.identify_region(e.x, e.y) == "separator" else None)
        sb = ttk.Scrollbar(box, orient="vertical", command=tree.yview, style="XP.Vertical.TScrollbar")
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")  # o cabeçalho do Treeview fica fixo enquanto as linhas rolam
        tree.pack(side="left", fill="both", expand=True)
        self._xp_tree = tree
        p.bind("<Configure>", self._xp_table_resize)

    def _xp_table_resize(self, e):
        """Fonte/altura de linha maiores em janelas grandes; menores na janela pequena."""
        if e.widget is not self._xp_panel:
            return
        size = 11 if e.width < 1000 else (13 if e.width < 1500 else 15)
        if size == self._xp_size:
            return
        self._xp_size = size
        self._xp_style.configure("XP.Treeview", font=(FONT, size), rowheight=int(size * 2.5))
        self._xp_style.configure("XP.Treeview.Heading", font=(FONT, size, "bold"))

    def _fill_xp_table(self):
        t = self.table
        cur = t.locate(self.xp).level  # nível atual do jogador (mesma lógica do Tracker)
        tree = self._xp_tree
        tree.delete(*tree.get_children())
        for lv in range(0, t.max_level + 1):  # P0 = ponto de partida (0 XP), como no Tracker
            nxt = pc.fmt_int(t.span(lv)) if lv < t.max_level else "N/A"
            tag = "current" if lv == cur else ("odd" if lv % 2 else "even")
            tree.insert("", "end", iid=str(lv), tags=(tag,),
                        values=(f"{lv}  ◄" if lv == cur else str(lv), nxt, pc.fmt_int(t.cum[lv])))
        self.update_idletasks()
        tree.see(str(min(cur + 8, t.max_level)))  # mostra o nível atual com algumas linhas de contexto
        tree.see(str(cur))

    def open_xp_table(self):
        if self._xp_panel is None:
            self._build_xp_table()
        self._fill_xp_table()  # recarrega a cada abertura => destaque sempre atualizado
        self._xp_panel.place(x=0, y=0, relwidth=1, relheight=1)  # cobre a tela principal
        self._xp_panel.lift()
        self._xp_tree.focus_set()

    def close_xp_table(self):
        if self._xp_panel is not None and self._xp_panel.winfo_ismapped():
            self._xp_panel.place_forget()
            self.total_entry.focus_set()

    def on_close(self):
        save_progress(self.xp, self.table)
        self.destroy()


def main():
    try:
        table = pc.load_table()
    except Exception as e:  # planilha ausente ou fora do formato
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror(APP_TITLE, f"Não foi possível ler a planilha de XP:\n\n{e}")
        r.destroy()
        sys.exit(1)
    App(table).mainloop()


if __name__ == "__main__":
    main()
