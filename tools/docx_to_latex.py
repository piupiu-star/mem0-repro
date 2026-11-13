"""Convert REPORT_before_format.docx to a LaTeX article laid out as a formal report.

Reads:  REPORT_before_format.docx   (the hand-edited final draft)
Writes: REPORT.tex

The Word file is not consistently styled: some real headings carry body styles,
some body paragraphs carry Heading 1/2 styles, and several headings are simply
bold stand-alone paragraphs.  The rules below reconstruct the intended outline.

Block rules (block index = position in document.xml body, 1-based)
------------------------------------------------------------------
style Heading 1, len > 120 chars ................ body paragraph (misstyled)
style Heading 1, numbered ....................... \section, number stripped
style Heading 1, "Appendix"/"References" ........ \section*
style Heading 1, anything else .................. \subsection
style Heading 2, len > 120 chars ................ body paragraph (misstyled)
style Heading 2 ................................. \subsection, number stripped
bold-only paragraph, "R1:"/"R2:"/"R3:" .......... \subsection
bold-only paragraph, <= 60 chars, no full stop .. \subsection
blank text "References" ......................... \section*
paragraph containing >= 2 line breaks ........... verbatim block
paragraph starting "1. " / "2. " / bullet ....... hanging-indent item
everything else ................................. body paragraph

Two sub-headings inside 4.1 are demoted to \subsubsection by index (see
LEVEL_BY_INDEX) so that the numbered outline stays 4.1, 4.2, 4.3, 4.4.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "REPORT_before_format.docx"
OUT = ROOT / "REPORT.tex"

TEXT_WIDTH_PT = 471.0      # A4 (595.3pt) minus 2 x 2.2cm margins
CHAR_PT = 4.4              # average Times 9.5pt character
COLSEP_PT = 10.0           # 2 x tabcolsep

# block index -> heading level, for cases the generic rules get wrong
LEVEL_BY_INDEX = {
    44: "subsubsection",   # "The temporal collapse, and its cause"  (inside 4.1)
    52: "subsubsection",   # "Making the headline gap interpretable" (inside 4.1)
    64: "subsection",      # "The change and Why this one." (inside 5)
    77: "subsection",      # "Why it helps, and how much of it I can attribute."
    83: "subsection",      # "Cost of the change."
}

UNICODE_MAP = {
    "\u2014": "---",
    "\u2013": "--",
    "\u2212": "$-$",
    "\u00b1": r"$\pm$",
    "\u00d7": r"$\times$",
    "\u2265": r"$\geq$",
    "\u2264": r"$\leq$",
    "\u2260": r"$\neq$",
    "\u2248": r"$\approx$",
    "\u2192": r"$\rightarrow$",
    "\u2190": r"$\leftarrow$",
    "\u00b7": r"\textperiodcentered{}",
    "\u2022": r"\textbullet{}",
    "\u2026": r"\ldots{}",
    "\u00a0": "~",
    "\u201c": "``",
    "\u201d": "''",
    "\u2018": "`",
    "\u2019": "'",
}

SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def esc(text: str) -> str:
    out = []
    for ch in text:
        if ch in UNICODE_MAP:
            out.append(UNICODE_MAP[ch])
        elif ch in SPECIAL:
            out.append(SPECIAL[ch])
        else:
            out.append(ch)
    return "".join(out)


# ------------------------------------------------------------------ runs

def _font_name(run: Run) -> str:
    rPr = run._r.rPr
    if rPr is None:
        return ""
    fonts = rPr.rFonts
    if fonts is None:
        return run.font.name or ""
    return " ".join(filter(None, [
        fonts.get(qn("w:ascii")) or "",
        fonts.get(qn("w:hAnsi")) or "",
        fonts.get(qn("w:eastAsia")) or "",
    ]))


def _render_one(run: Run) -> str:
    text = run.text
    if not text:
        return ""
    if not text.strip(" \t\u00a0\u200b"):
        return "~" if "\u00a0" in text or " " in text else ""
    body = esc(text)
    if re.search(r"Consolas|Courier|Mono|Menlo|DejaVu Sans Mono", _font_name(run), re.I):
        body = r"\texttt{%s}" % body
    if run.bold:
        body = r"\textbf{%s}" % body
    if run.italic:
        body = r"\emph{%s}" % body
    return body


def link_targets(par: Paragraph) -> dict[str, str]:
    targets: dict[str, str] = {}
    part = par.part
    for h in par._p.iter(qn("w:hyperlink")):
        rid = h.get(qn("r:id"))
        if not rid:
            continue
        try:
            rel = part.rels[rid]
            if rel.is_external:
                targets[rid] = rel.target_ref
        except Exception:
            pass
    return targets


def render_runs(par: Paragraph) -> str:
    targets = link_targets(par)
    chunks: list[str] = []
    for child in par._p.iterchildren():
        if child.tag == qn("w:r"):
            chunks.append(_render_one(Run(child, par)))
        elif child.tag == qn("w:hyperlink"):
            url = targets.get(child.get(qn("r:id")))
            inner = "".join(_render_one(Run(r, par)) for r in child.iter(qn("w:r")))
            chunks.append(r"\href{%s}{%s}" % (url, inner) if url else inner)
    return polish("".join(chunks))


MISSING_SPACE = re.compile(r"(?<=[a-z]\.)(?=[A-Z][a-z])")


def polish(text: str) -> str:
    """Repair two artefacts of run-level conversion.

    * Word splits a sentence at a formatting boundary and drops the space, so
      "...into facts.That stage..." comes out glued together.
    * Straight double quotes reach LaTeX as 'sideways' quotes, so they are
      paired into `` and '' in reading order.
    """
    text = MISSING_SPACE.sub(" ", text)
    out = []
    open_quote = True
    for ch in text:
        if ch == '"':
            out.append("``" if open_quote else "''")
            open_quote = not open_quote
        else:
            out.append(ch)
    return "".join(out)


def para_text(par: Paragraph) -> str:
    return "".join(r.text for r in (Run(c, par) for c in par._p.iter(qn("w:r"))))


def is_bold_only(par: Paragraph) -> bool:
    """True when nothing in the paragraph is explicitly non-bold.

    Word leaves bold unset on runs that inherit it, so a trailing full stop or
    space often reports None; only an explicit False disqualifies the run.
    """
    seen = False
    for r in par.runs:
        if not r.text.strip():
            continue
        if r.bold is False:
            return False
        if r.bold is True:
            seen = True
    return seen


# ------------------------------------------------------------------ headings

HEADING_MAP = {
    "标题": "title",
    "Title": "title",
    "标题 1": "h1",
    "Heading 1": "h1",
    "标题 2": "h2",
    "Heading 2": "h2",
    "标题 3": "h3",
    "Heading 3": "h3",
}

NUM_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s*")
R_LABEL = re.compile(r"^R\d\s*[:.]", re.I)
STARRED = re.compile(r"^(appendix|references|bibliography|acknowledg)", re.I)


def strip_number(text: str) -> str:
    return NUM_PREFIX.sub("", text.lstrip(". \u00a0"), count=1).strip()


def num_depth(text: str) -> int:
    """0 when the paragraph carries no leading number, else its depth."""
    m = NUM_PREFIX.match(text.lstrip(". \u00a0"))
    if not m:
        return 0
    return m.group(0).strip().rstrip(".").count(".") + 1


def heading_cmd(level: str, text: str) -> str:
    if level == "section":
        if STARRED.match(text):
            return r"\section*{%s}" % esc(text)
        return r"\section{%s}" % esc(strip_number(text))
    if level == "subsection":
        return r"\subsection{%s}" % esc(strip_number(text))
    return r"\subsubsection{%s}" % esc(strip_number(text))


# ------------------------------------------------------------------ tables

def cell_text(cell) -> str:
    return " ".join(cell.text.split())


def table_spec(rows: list[list[str]]) -> tuple[str, bool]:
    """Return (column spec, needs_wrapping).

    Narrow tables keep natural column widths so figures stay on one line;
    wide tables hand the long columns to tabularx so they can wrap.
    """
    ncols = max(len(r) for r in rows)
    widths = [max((len(r[j]) if j < len(r) else 0) for r in rows) for j in range(ncols)]
    estimate = sum(widths) * CHAR_PT + ncols * COLSEP_PT
    if estimate <= TEXT_WIDTH_PT:
        return "l" * ncols, False
    spec = ["X" if w > 25 else "l" for w in widths]
    if "X" not in spec:
        spec[max(range(ncols), key=lambda j: widths[j])] = "X"
    return "".join(spec), True


def render_table(table: Table) -> str:
    rows = [[cell_text(c) for c in r.cells] for r in table.rows]
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    spec, needs_x = table_spec(rows)
    spec_tex = spec.replace("X", r">{\RaggedRight\arraybackslash}X")

    # a two-column table is a key/value list, so only the key is a heading
    if ncols == 2:
        head = r"\textbf{%s} & %s \\" % (esc(rows[0][0]), esc(rows[0][1]))
    else:
        head = " & ".join(r"\textbf{%s}" % esc(c) for c in rows[0]) + r" \\"
    body = [" & ".join(esc(c) for c in r) + r" \\" for r in rows[1:]]

    if not needs_x:
        return "\n".join(
            [r"\begin{center}\small", r"\begin{tabular}{@{}%s@{}}" % spec_tex,
             r"\toprule", head, r"\midrule"] + body
            + [r"\bottomrule", r"\end{tabular}", r"\end{center}"]
        )

    if len(rows) <= 8:                       # fits on one page: no page breaks
        return "\n".join(
            [r"\begin{center}\small", r"\begin{tabularx}{\textwidth}{@{}%s@{}}" % spec_tex,
             r"\toprule", head, r"\midrule"] + body
            + [r"\bottomrule", r"\end{tabularx}", r"\end{center}"]
        )

    out = [r"{\small", r"\begin{xltabular}{\textwidth}{@{}%s@{}}" % spec_tex,
           r"\toprule", head, r"\midrule", r"\endfirsthead",
           r"\toprule", head, r"\midrule", r"\endhead",
           r"\bottomrule", r"\endfoot"]
    out += body
    out += [r"\end{xltabular}", r"}"]
    return "\n".join(out)


# ------------------------------------------------------------------ preamble

PREAMBLE = r"""% ---------------------------------------------------------------------------
%  FTEC5660 Reproducibility Work -- Mem0 on LOCOMO
%  Xiuling PIAO (1155267871)
%
%  Compile with pdfLaTeX, twice (the footer needs \pageref{LastPage}):
%      pdflatex REPORT.tex
%      pdflatex REPORT.tex
%  On Overleaf: upload REPORT.tex, set the compiler to pdfLaTeX.
%
%  If the PDF runs past the 10-page limit, change the first line to 10pt
%  and/or narrow the margins in \geometry.
% ---------------------------------------------------------------------------
\documentclass[11pt,a4paper]{article}

\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{newtxtext,newtxmath}
\usepackage[a4paper,left=2.2cm,right=2.2cm,top=2.1cm,bottom=2.2cm,
            headheight=12pt,footskip=1.0cm]{geometry}
\usepackage{microtype}
\usepackage{xltabular}
\usepackage{booktabs}
\usepackage{array}
\usepackage{ragged2e}
\usepackage{fancyvrb}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{caption}
\usepackage{lastpage}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage[hidelinks]{hyperref}

% ---- body text ------------------------------------------------------------
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt plus 1pt}
\linespread{1.0}
\setlength{\emergencystretch}{2em}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{5pt}
\captionsetup{font=small,labelfont=bf,skip=3pt}

% ---- headinds -------------------------------------------------------------
\titleformat{\section}
  {\normalfont\large\bfseries}{\thesection}{0.65em}{}
\titlespacing*{\section}{0pt}{13pt plus 2pt}{5pt}
\titleformat{\subsection}
  {\normalfont\normalsize\bfseries}{\thesubsection}{0.55em}{}
\titlespacing*{\subsection}{0pt}{10pt plus 1pt}{3pt}
\titleformat{\subsubsection}
  {\normalfont\normalsize\bfseries\itshape}{\thesubsubsection}{0.55em}{}
\titlespacing*{\subsubsection}{0pt}{8pt plus 1pt}{2pt}

% ---- running footer -------------------------------------------------------
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[L]{\footnotesize FTEC5660 Reproducibility Study}
\fancyfoot[C]{\footnotesize Page \thepage\ of \pageref{LastPage}}
\fancyfoot[R]{\footnotesize Xiuling PIAO (1155267871)}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0.4pt}
\fancypagestyle{plain}{%
  \fancyhf{}%
  \fancyfoot[L]{\footnotesize FTEC5660 Reproducibility Study}%
  \fancyfoot[C]{\footnotesize Page \thepage\ of \pageref{LastPage}}%
  \fancyfoot[R]{\footnotesize Xiuling PIAO (1155267871)}%
  \renewcommand{\headrulewidth}{0pt}%
  \renewcommand{\footrulewidth}{0.4pt}%
}

\hypersetup{
  pdftitle={Reproducing Mem0 on LOCOMO},
  pdfauthor={Xiuling PIAO (1155267871)},
  pdfsubject={FTEC5660 Reproducibility Work}
}

\begin{document}
"""

TEXT_FIXES = [
    # the docx repeats this label twice at the start of the same item
    (r"\textbf{Forced substitution.}~\textbf{Forced substitution.}",
     r"\textbf{Forced substitution.}"),
]

TITLE_BLOCK = r"""\begin{center}
{\LARGE\bfseries %s\par}
\vspace{0.35em}
{\large Xiuling PIAO \textperiodcentered{} 1155267871\par}
\vspace{0.25em}
{\small FTEC5660 Agentic AI for Business and FinTech \textperiodcentered{}
 Reproducibility Work\par}
\vspace{0.5em}
\rule{0.55\textwidth}{0.4pt}
\end{center}
\vspace{0.6em}
"""


# ------------------------------------------------------------------ main

def main() -> None:
    doc = Document(str(SRC))
    blocks = [c for c in doc.element.body.iterchildren()
              if c.tag in (qn("w:p"), qn("w:tbl"))]

    parts: list[str] = [PREAMBLE]
    stats = {"section": 0, "subsection": 0, "subsubsection": 0,
             "tables": 0, "paras": 0, "verbatim": 0}
    skip = set()

    for i, child in enumerate(blocks, start=1):
        if i in skip:
            continue

        if child.tag == qn("w:tbl"):
            parts += [render_table(Table(child, doc)), ""]
            stats["tables"] += 1
            continue

        par = Paragraph(child, doc)
        text = para_text(par).strip()
        if not text:
            continue
        style = HEADING_MAP.get(par.style.name if par.style is not None else "", "")
        nxt_tbl = (i < len(blocks) and blocks[i].tag == qn("w:tbl"))

        # ---- title -------------------------------------------------------
        if style == "title":
            parts.append(TITLE_BLOCK % esc(text))
            skip.update({i + 1, i + 2})   # "Xiuling PIAO ." and the ID line
            continue

        # ---- headings ----------------------------------------------------
        level = None
        if style in ("h1", "h2"):
            if len(text) > 120:
                level = None                       # misstyled body text
            elif i in LEVEL_BY_INDEX:
                level = LEVEL_BY_INDEX[i]
            elif style == "h1":
                level = "section" if (NUM_PREFIX.match(text) or STARRED.match(text)) else "subsection"
            else:
                level = "subsection"
        elif text.lower() in ("references", "bibliography") and len(text) <= 20:
            level = "section"
        elif is_bold_only(par) and len(text) <= 60:
            depth = num_depth(text)
            if i in LEVEL_BY_INDEX:
                level = LEVEL_BY_INDEX[i]
            elif R_LABEL.match(text):
                level = "subsection"
            elif depth == 1:
                level = "section"
            elif depth >= 2 or not text.endswith("."):
                level = "subsection"

        if level:
            parts += [heading_cmd(level, text), ""]
            stats[level] += 1
            continue

        # ---- verbatim block (shell transcript in the appendix) ------------
        if text.count("\n") >= 2:
            body = "\n".join(line.rstrip() for line in par.text.split("\n"))
            parts += [r"\begin{Verbatim}[fontsize=\footnotesize,frame=single,xleftmargin=4pt]",
                      body, r"\end{Verbatim}", ""]
            stats["verbatim"] += 1
            continue

        # ---- enumerated / bulleted item -----------------------------------
        if re.match(r"^\s*(?:\d+\.|[\u2022\u00b7])\s+", text):
            parts += [r"\noindent\hangindent=1.45em\hangafter=1 " + render_runs(par), ""]
            stats["paras"] += 1
            continue

        parts += [render_runs(par), ""]
        stats["paras"] += 1

    parts.append(r"\end{document}")
    tex = "\n".join(parts)
    for old, new in TEXT_FIXES:
        if old not in tex:
            print(f"  [warn] fix not applied: {old[:40]}...")
        tex = tex.replace(old, new)
    OUT.write_text(tex, encoding="utf-8")

    print(f"wrote {OUT.name}")
    for k, v in stats.items():
        print(f"  {k:<14}{v}")


if __name__ == "__main__":
    main()
