"""Dump the block structure of the report docx: index, kind, style, preview."""

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "REPORT_before_format.docx"

doc = Document(str(SRC))
out = []
i = 0
for child in doc.element.body.iterchildren():
    i += 1
    if child.tag == qn("w:tbl"):
        t = Table(child, doc)
        out.append(f"[{i:03d}] TABLE {len(t.rows)}x{len(t.columns)} :: {t.rows[0].cells[0].text[:50]!r}")
        continue
    if child.tag != qn("w:p"):
        out.append(f"[{i:03d}] {child.tag.split('}')[-1]}")
        continue
    p = Paragraph(child, doc)
    text = p.text.replace("\n", " ")
    style = p.style.name if p.style is not None else "?"
    bold_lead = ""
    for r in p.runs:
        if r.bold:
            bold_lead += r.text
        else:
            break
    out.append(f"[{i:03d}] P {style:<12} len={len(text):<5} :: {text[:95]!r}"
               + (f"   [bold-lead: {bold_lead[:40]!r}]" if bold_lead else ""))

(ROOT / "tools" / "_docx_dump.txt").write_text("\n".join(out), encoding="utf-8")
print(f"blocks: {i} -> tools/_docx_dump.txt")
