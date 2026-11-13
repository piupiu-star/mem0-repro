"""Show run-level bold flags for suspect blocks."""

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

TARGETS = {7, 8, 29, 32, 34, 44, 52, 54, 61, 64, 71, 77, 84, 89, 97}

doc = Document("REPORT_before_format.docx")
blocks = [c for c in doc.element.body.iterchildren()
          if c.tag in (qn("w:p"), qn("w:tbl"))]

for i, child in enumerate(blocks, start=1):
    if i not in TARGETS or child.tag != qn("w:p"):
        continue
    p = Paragraph(child, doc)
    runs = [(r.text[:28].replace("\n", "|"), r.bold, r.font.name) for r in p.runs]
    print(f"[{i:03d}] style={p.style.name} runs={len(p.runs)}")
    for r in runs:
        print("       ", r)
