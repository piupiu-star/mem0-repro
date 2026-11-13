"""Inspect tables (column widths, headers) and multi-line paragraphs."""

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

doc = Document("REPORT_before_format.docx")
i = 0
for child in doc.element.body.iterchildren():
    i += 1
    if child.tag == qn("w:tbl"):
        t = Table(child, doc)
        rows = [[c.text.strip().replace("\n", " ") for c in r.cells] for r in t.rows]
        n = max(len(r) for r in rows)
        widths = [max((len(r[j]) if j < len(r) else 0) for r in rows) for j in range(n)]
        print(f"[{i:03d}] {len(rows)}x{n} widths={widths}")
        print("      hdr:", rows[0])
        if len(rows) > 1:
            print("      r1 :", [c[:30] for c in rows[1]])
        if len(rows) > 2:
            print("      r2 :", [c[:30] for c in rows[2]])
    elif child.tag == qn("w:p"):
        p = Paragraph(child, doc)
        if p.text.count("\n") >= 2:
            print(f"[{i:03d}] MULTILINE breaks={p.text.count(chr(10))} :: {p.text[:90]!r}")
