"""
Lógica do Diablo 4 Paragon XP Tracker (sem interface gráfica).

- Lê a tabela de XP diretamente da planilha .xlsx (nada de valores fixos no código).
- Todo XP é inteiro Python. Floats nunca são usados para XP.
- Percentuais são calculados com aritmética inteira (pontos-base = centésimos de %).

Semântica da tabela (confirmada na planilha S13):
    Linha do nível L:  "XP Required" = XP necessário para ir de P(L-1) até P(L).
    cum[L] = soma de XP Required de 1 até L = XP total para *alcançar* o Paragon L.
    cum[0] = 0  (Paragon 0 = ainda não alcançou o P1).
    Um jogador com XP total X está no maior L tal que cum[L] <= X.
    O "tamanho" do nível L (XP para sair dele) é XP Required[L+1].
"""

from __future__ import annotations

import glob
import os
import re
import sys
from bisect import bisect_right
from dataclasses import dataclass, field

DEFAULT_XLSX_NAME = "D4 LoH Paragon XP Current S13.xlsx"


# --------------------------------------------------------------------------
# Localização de arquivos
# --------------------------------------------------------------------------
def app_dir() -> str:
    """Pasta do programa (ao lado do .exe quando empacotado)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_xlsx(extra_dirs: list[str] | None = None) -> str:
    """Procura a planilha: nome padrão primeiro, depois qualquer *Paragon*XP*.xlsx."""
    dirs = [app_dir()]
    if getattr(sys, "_MEIPASS", None):  # cópia embutida no .exe (fallback)
        dirs.append(sys._MEIPASS)
    dirs += extra_dirs or []
    for d in dirs:
        p = os.path.join(d, DEFAULT_XLSX_NAME)
        if os.path.isfile(p):
            return p
    for d in dirs:
        cands = [
            p
            for p in glob.glob(os.path.join(d, "*.xlsx"))
            if not os.path.basename(p).startswith("~$")
            and re.search(r"paragon", os.path.basename(p), re.I)
        ]
        if cands:
            return max(cands, key=os.path.getmtime)
    raise FileNotFoundError(
        f'Planilha não encontrada. Coloque "{DEFAULT_XLSX_NAME}" na pasta do programa:\n{dirs[0]}'
    )


# --------------------------------------------------------------------------
# Leitura da planilha
# --------------------------------------------------------------------------
def _as_int(value, what: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{what}: valor inválido ({value!r}).")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"{what}: esperado número inteiro, encontrado {value!r}.")


def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip().lower() if v is not None else ""


def read_xlsx_table(path: str) -> tuple[list[int], list[str]]:
    """
    Localiza a tabela (cabeçalhos 'Level' e 'XP Required') em qualquer aba e
    devolve (xp_required_por_nivel[1..N], avisos).
    Usa os VALORES das células (data_only=True), então fórmulas precisam ter valor salvo.
    """
    import openpyxl  # importado aqui para os testes de lógica não dependerem dele

    wb = openpyxl.load_workbook(path, data_only=True)
    warnings: list[str] = []

    for ws in wb.worksheets:
        header = None
        for row in ws.iter_rows(min_row=1, max_row=60, max_col=40):
            level_cell = next((c for c in row if _norm(c.value) == "level"), None)
            if level_cell is None:
                continue
            req_cell = next((c for c in row if _norm(c.value).startswith("xp required")), None)
            if req_cell is None:
                continue
            cum_cell = next((c for c in row if _norm(c.value).startswith("cumulative xp")), None)
            header = (level_cell, req_cell, cum_cell)
            break
        if header is None:
            continue

        level_cell, req_cell, cum_cell = header
        r0 = level_cell.row + 1
        req: list[int] = []
        cum_sheet: list[int | None] = []
        r = r0
        while True:
            lv = ws.cell(r, level_cell.column).value
            if lv is None:
                break
            lv = _as_int(lv, f"{ws.title}!A{r} (nível)")
            expected = len(req) + 1
            if lv != expected:
                raise ValueError(
                    f"{ws.title}: níveis fora de sequência na linha {r} (esperado {expected}, achei {lv})."
                )
            xv = ws.cell(r, req_cell.column).value
            if xv is None:
                raise ValueError(
                    f"{ws.title}: célula de XP vazia na linha {r}. Se for fórmula, abra e salve a planilha no Excel."
                )
            xp = _as_int(xv, f"{ws.title}!{ws.cell(r, req_cell.column).coordinate} (XP Required)")
            if xp <= 0:
                raise ValueError(f"{ws.title}: XP Required deve ser positivo (linha {r}).")
            req.append(xp)
            if cum_cell is not None:
                cv = ws.cell(r, cum_cell.column).value
                cum_sheet.append(int(cv) if isinstance(cv, (int, float)) else None)
            r += 1

        if not req:
            continue

        if cum_cell is not None:  # verificação cruzada com a coluna "Cumulative XP" da planilha
            running = 0
            bad = 0
            for i, x in enumerate(req):
                running += x
                if cum_sheet[i] is not None and cum_sheet[i] != running:
                    bad += 1
            if bad:
                warnings.append(
                    f'A coluna "Cumulative XP" da planilha difere da soma de "XP Required" em {bad} linha(s). '
                    'O programa usa a soma de "XP Required".'
                )
        return req, warnings

    raise ValueError(
        'Não encontrei uma tabela com cabeçalhos "Level" e "XP Required" em nenhuma aba da planilha.'
    )


# --------------------------------------------------------------------------
# Tabela de níveis
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Position:
    xp: int  # XP total acumulado (já limitado a [0, total])
    level: int  # Paragon atual (0..max_level)
    in_level: int  # XP acumulado dentro do nível atual
    span: int  # XP total necessário para completar o nível atual (0 no nível máximo)
    level_remaining: int  # XP que falta para o próximo Paragon (0 no máximo)
    total_remaining: int  # XP que falta até o Paragon máximo
    next_level: int | None  # None no Paragon máximo


@dataclass
class ParagonTable:
    xp_required: list[int]  # índice 0 => nível 1
    source: str = ""
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.xp_required:
            raise ValueError("XP Table Blank.")
        self.max_level = len(self.xp_required)
        self.req = [0] + list(self.xp_required)  # req[L]: XP para ir de P(L-1) a P(L)
        self.cum = [0]
        for x in self.xp_required:
            self.cum.append(self.cum[-1] + x)  # cum[L]: XP para alcançar P(L)
        self.total = self.cum[-1]

    def span(self, level: int) -> int:
        """Needed XP to fulfil the level 'level' (= XP Required to next level)."""
        return 0 if level >= self.max_level else self.req[level + 1]

    def clamp(self, xp: int) -> int:
        return max(0, min(xp, self.total))

    def locate(self, xp: int) -> Position:
        xp = self.clamp(xp)
        level = bisect_right(self.cum, xp) - 1  # maior L com cum[L] <= xp
        in_level = xp - self.cum[level]
        span = self.span(level)
        at_max = level >= self.max_level
        return Position(
            xp=xp,
            level=level,
            in_level=in_level,
            span=span,
            level_remaining=0 if at_max else span - in_level,
            total_remaining=self.total - xp,
            next_level=None if at_max else level + 1,
        )

    def resolve_level(self, level: int, in_level: int) -> tuple[int, list[str]]:
        """Level + XP inside level -> (Total XP, warnings). Fix values outside the interval."""
        warns: list[str] = []
        if level < 0:
            level = 0
            warns.append("Minimum Paragon level is 0 (Before P1); adjusted.")
        elif level > self.max_level:
            level = self.max_level
            warns.append(f"Paragon limited to maximum (P{self.max_level}).")
        span = self.span(level)
        if level >= self.max_level:
            if in_level != 0:
                in_level = 0
                warns.append(f"On P{self.max_level} there is no XP inside level; progress limited to maximum.")
        elif in_level >= span:
            in_level = span - 1
            warns.append(
                f"XP inside the level limited to {fmt_int(in_level)} "
                f"(the P{level} finishes when reaching {fmt_int(span)} XP)."
            )
        return self.cum[level] + in_level, warns

    def resolve_total(self, xp: int) -> tuple[int, list[str]]:
        if xp > self.total:
            return self.total, [f"Progress limited to maximum of P{self.max_level} ({fmt_int(self.total)} XP)."]
        return xp, []


def load_table(path: str | None = None) -> ParagonTable:
    path = path or find_xlsx()
    req, warns = read_xlsx_table(path)
    return ParagonTable(req, source=os.path.basename(path), warnings=warns)


# --------------------------------------------------------------------------
# Entrada / formatação (pt-BR)
# --------------------------------------------------------------------------
def parse_int(text: str, thousands: bool = True) -> int:
    """
    Converte texto em inteiro >= 0. Aceita separadores de milhar (. espaço _ ') se thousands=True.
    Levanta ValueError com mensagem clara em português.
    """
    s = (text or "").strip()
    if not s:
        raise ValueError("Blank space.")
    if s.startswith("-"):
        raise ValueError("Negative vallues aren't allowed.")
    if "," in s:
        raise ValueError("Use only integers (without comma/decimals).")
    if thousands:
        s = re.sub(r"[.\s_']", "", s)
    if not s.isdigit() or not s.isascii():
        raise ValueError("Type only numbers (ex.: 10656835750 ou 10.656.835.750).")
    return int(s)


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def pct_bp(num: int, den: int) -> int:
    """Percentual em pontos-base (centésimos de %), inteiro, arredondado 'half up'.
    Nunca mostra 100,00% antes de completar de verdade."""
    if den <= 0:
        return 0
    bp = (num * 20000 + den) // (2 * den)
    if num < den:
        bp = min(bp, 9999)
    return bp


def fmt_bp(bp: int) -> str:
    return f"{bp // 100},{bp % 100:02d}%"


def fmt_pct(num: int, den: int) -> str:
    return fmt_bp(pct_bp(num, den))
