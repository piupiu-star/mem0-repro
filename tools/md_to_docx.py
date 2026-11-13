"""Render REPORT.md as an editable Word document.

There is no pandoc / LibreOffice on the target machine, so instead of shelling
out this parses the Markdown subset the report actually uses: ATX headings,
pipe tables, bullet and numbered lists, blockquotes, fenced code, and the inline
**bold** / *italic* / `code` / [link](url) forms.

The output is a plain .docx with real Word styles and real tables -- not an
image or an embedded HTML blob -- so it can be edited, re-styled and exported to
PDF from Word itself.

Usage (from the repository root):
    python -m tools.md_to_docx
    python -m tools.md_to_docx --in REPORT.md --out REPORT.docx
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

BODY_FONT = "Calibri"
CODE_FONT = "Consolas"
EA_FONT = "Microsoft YaHei"          # so Chinese typed into the doc still renders
ACCENT = RGBColor(0x1E, 0x3A, 0x5F)
MUTED = RGBColor(0x5A, 0x5A, 0x5A)
CODE_INK = RGBColor(0x2B, 0x2B, 0x2B)
BODY_PT = 10.5                        # Word default is 11; report is page-limited

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
ORDERED_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
RULE_RE = re.compile(r"^-{3,}$")

INLINE_RE = re.compile(
    r"(?P<bold>\*\*(?P<bold_text>.+?)\*\*)"
    r"|(?P<code>`(?P<code_text>[^`]+)`)"
    r"|(?P<ital>\*(?P<ital_text>[^*\n]+)\*)"
    r"|(?P<link>\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^)\s]+)\))",
    re.S,
)


# --------------------------------------------------------------------------- #
# low-level helpers
# --------------------------------------------------------------------------- #
def _style_run(run, *, bold=False, italic=False, mono=False, size=None) -> None:
    run.bold = bold
    run.italic = italic
    if mono:
        run.font.name = CODE_FONT
        run._element.rPr.rFonts.set(qn("w:eastAsia"), CODE_FONT)
        run.font.size = Pt((size or BODY_PT) - 1.0)
        run.font.color.rgb = CODE_INK
    elif size:
        run.font.size = Pt(size)


def _add_hyperlink(paragraph, url: str, text: str, *, bold=False, size=None) -> None:
    """A real clickable hyperlink (python-docx has no API for this)."""
    r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)

    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0B5CAD")
    rpr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(underline)
    if bold:
        rpr.append(OxmlElement("w:b"))
    if size:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(size * 2)))
        rpr.append(sz)
    run.append(rpr)

    node = OxmlElement("w:t")
    node.set(qn("xml:space"), "preserve")
    node.text = text
    run.append(node)
    link.append(run)
    paragraph._p.append(link)


def _add_inline(paragraph, text: str, *, bold=False, italic=False, size=None) -> None:
    """Emit runs for **bold**, *italic*, `code` and [links](url)."""
    if not text:
        return
    pos = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos:match.start()])
            _style_run(run, bold=bold, italic=italic, size=size)
        if match.group("bold") is not None:
            # Recurse so `code` nested inside **bold** still gets its font.
            _add_inline(paragraph, match.group("bold_text"), bold=True, italic=italic, size=size)
        elif match.group("code") is not None:
            run = paragraph.add_run(match.group("code_text"))
            _style_run(run, bold=bold, italic=italic, mono=True, size=size)
        elif match.group("ital") is not None:
            _add_inline(paragraph, match.group("ital_text"), bold=bold, italic=True, size=size)
        elif match.group("link") is not None:
            _add_hyperlink(
                paragraph, match.group("link_url"), match.group("link_text"),
                bold=bold, size=size,
            )
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        _style_run(run, bold=bold, italic=italic, size=size)


def _shade(cell_or_par, hex_fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    element = cell_or_par._tc if hasattr(cell_or_par, "_tc") else cell_or_par._p
    pr = element.get_or_add_tcPr() if hasattr(cell_or_par, "_tc") else element.get_or_add_pPr()
    pr.append(shd)


def _repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def _full_width(table) -> None:
    tbl_pr = table._tbl.tblPr
    width = OxmlElement("w:tblW")
    width.set(qn("w:type"), "pct")
    width.set(qn("w:w"), "5000")   # fiftieths of a percent -> 100 %
    tbl_pr.append(width)


def _add_field(paragraph, field: str) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {field} "
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for node in (begin, instr, sep, placeholder, end):
        run._r.append(node)
    run.font.size = Pt(8.5)
    run.font.color.rgb = MUTED


# --------------------------------------------------------------------------- #
# document scaffold
# --------------------------------------------------------------------------- #
def _new_document() -> Document:
    doc = Document()

    section = doc.sections[0]
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.9)
    section.top_margin = Inches(0.85)
    section.bottom_margin = Inches(0.85)

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(BODY_PT)
    normal.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), EA_FONT)
    para = normal.paragraph_format
    para.line_spacing = 1.22
    para.space_after = Pt(6)
    para.space_before = Pt(0)

    # The default template's Title style draws a rule under the heading. Kept
    # off: the title is followed by the author line, so the rule would split
    # the two rather than separate the block below it.
    title_style = doc.styles["Title"]
    title_p_pr = title_style.element.find(qn("w:pPr"))
    if title_p_pr is not None:
        border = title_p_pr.find(qn("w:pBdr"))
        if border is not None:
            title_p_pr.remove(border)

    for name in ("List Bullet", "List Bullet 2"):
        style = doc.styles[name]
        style.font.name = BODY_FONT
        style.font.size = Pt(BODY_PT)
        style.paragraph_format.space_after = Pt(3)

    footer = section.footer.paragraphs[0]
    footer.text = ""
    footer.paragraph_format.tab_stops.add_tab_stop(Inches(6.7), WD_TAB_ALIGNMENT.RIGHT)
    stamp = footer.add_run("FTEC5660 Reproducibility · Mem0 · Xiuling PIAO 1155267871\t")
    stamp.font.size = Pt(8.5)
    stamp.font.color.rgb = MUTED
    _add_field(footer, "PAGE")
    return doc


def _add_heading(doc, level: int, text: str) -> None:
    """Real Word heading styles, so the Navigation pane and a TOC both work.

    The appearance is set on the run, which overrides the template's blue
    Calibri Light without changing the style's outline level.
    """
    style_name = {1: "Title", 2: "Heading 1", 3: "Heading 2"}.get(level, "Heading 3")
    paragraph = doc.add_paragraph(style=style_name)
    fmt = paragraph.paragraph_format
    fmt.keep_with_next = True

    if level == 1:
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(4)
        size, color = 19.0, ACCENT
    elif level == 2:
        fmt.space_before = Pt(16)
        fmt.space_after = Pt(5)
        size, color = 14.5, ACCENT
    elif level == 3:
        fmt.space_before = Pt(11)
        fmt.space_after = Pt(3)
        size, color = 12.0, RGBColor(0x2A, 0x2A, 0x2A)
    else:
        fmt.space_before = Pt(9)
        fmt.space_after = Pt(3)
        size, color = 11.0, RGBColor(0x2A, 0x2A, 0x2A)

    run = paragraph.add_run(text)
    run.bold = True
    run.italic = level >= 4
    run.font.name = BODY_FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), EA_FONT)
    run.font.size = Pt(size)
    run.font.color.rgb = color


def _add_table(doc, block: list[str]) -> None:
    rows: list[list[str]] = []
    for line in block:
        if TABLE_SEP_RE.match(line):
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    if not rows:
        return

    ncols = max(len(row) for row in rows)
    table = doc.add_table(rows=len(rows), cols=ncols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    _full_width(table)

    for r_idx, cells in enumerate(rows):
        for c_idx in range(ncols):
            cell = table.cell(r_idx, c_idx)
            paragraph = cell.paragraphs[0]
            fmt = paragraph.paragraph_format
            fmt.space_before = Pt(2)
            fmt.space_after = Pt(2)
            fmt.line_spacing = 1.05
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            text = cells[c_idx] if c_idx < len(cells) else ""
            _add_inline(paragraph, text, bold=(r_idx == 0), size=8.5)
            if r_idx == 0:
                _shade(cell, "E6ECF4")

    _repeat_header(table.rows[0])
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def _add_code_block(doc, lines: list[str]) -> None:
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.left_indent = Inches(0.18)
    fmt.space_before = Pt(6)
    fmt.space_after = Pt(9)
    fmt.line_spacing = 1.0
    for index, line in enumerate(lines):
        run = paragraph.add_run(line)
        run.font.name = CODE_FONT
        run._element.rPr.rFonts.set(qn("w:eastAsia"), CODE_FONT)
        run.font.size = Pt(8.5)
        run.font.color.rgb = CODE_INK
        if index < len(lines) - 1:
            run.add_break()
    _shade(paragraph, "F3F5F8")


def _add_quote(doc, text: str) -> None:
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.left_indent = Inches(0.34)
    fmt.right_indent = Inches(0.15)
    fmt.space_before = Pt(7)
    fmt.space_after = Pt(9)
    _add_inline(paragraph, text)

    borders = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:space"), "10")
    left.set(qn("w:color"), "8FA6C4")
    borders.append(left)
    paragraph._p.get_or_add_pPr().append(borders)


# --------------------------------------------------------------------------- #
# main conversion
# --------------------------------------------------------------------------- #
def convert(markdown: str, out_path: Path) -> tuple[int, int]:
    doc = _new_document()
    lines = markdown.splitlines()

    para_buf: list[str] = []
    quote_buf: list[str] = []
    # A list item can wrap over several source lines. Collecting it in its own
    # buffer (instead of emitting one paragraph per source line) is what keeps
    # inline markup such as a **bold run** that spans a line break intact.
    item_buf: list[str] = []
    item_kind: str | None = None
    item_depth = 0
    item_number = ""
    code_buf: list[str] = []
    in_code = False
    n_tables = 0

    def flush_paragraph() -> None:
        nonlocal para_buf
        if para_buf:
            paragraph = doc.add_paragraph()
            _add_inline(paragraph, " ".join(part.strip() for part in para_buf))
            para_buf = []

    def flush_quote() -> None:
        nonlocal quote_buf
        if quote_buf:
            _add_quote(doc, " ".join(part.strip() for part in quote_buf))
            quote_buf = []

    def flush_item() -> None:
        nonlocal item_buf, item_kind
        if item_kind is None:
            return
        text = " ".join(part.strip() for part in item_buf)
        if item_kind == "bullet":
            style = "List Bullet 2" if item_depth >= 1 else "List Bullet"
            paragraph = doc.add_paragraph(style=style)
            _add_inline(paragraph, text)
        else:
            # Literal numbers rather than Word auto-numbering: two separate
            # lists in one document would otherwise share a counter and the
            # second would silently continue from the first.
            paragraph = doc.add_paragraph()
            fmt = paragraph.paragraph_format
            fmt.left_indent = Inches(0.3)
            fmt.first_line_indent = Inches(-0.22)
            fmt.space_after = Pt(5)
            _add_inline(paragraph, f"{item_number}. {text}")
        item_buf, item_kind = [], None

    def flush_all() -> None:
        flush_paragraph()
        flush_quote()
        flush_item()

    index = 0
    while index < len(lines):
        raw = lines[index]
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                _add_code_block(doc, code_buf)
                in_code, code_buf = False, []
            else:
                flush_all()
                in_code = True
            index += 1
            continue
        if in_code:
            code_buf.append(raw)
            index += 1
            continue

        if not stripped:
            flush_all()
            index += 1
            continue

        if RULE_RE.match(stripped):
            flush_all()
            index += 1
            continue

        heading = HEADING_RE.match(stripped)
        if heading:
            flush_all()
            _add_heading(doc, len(heading.group(1)), heading.group(2).strip())
            index += 1
            continue

        is_table = (
            stripped.startswith("|")
            and index + 1 < len(lines)
            and TABLE_SEP_RE.match(lines[index + 1].strip())
        )
        if is_table:
            flush_all()
            block: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                block.append(lines[index].strip())
                index += 1
            _add_table(doc, block)
            n_tables += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            flush_item()
            quote_buf.append(stripped.lstrip(">").strip())
            index += 1
            continue

        bullet = BULLET_RE.match(line)
        if bullet:
            flush_all()
            item_kind = "bullet"
            item_depth = len(bullet.group(1)) // 2
            item_buf = [bullet.group(2).strip()]
            index += 1
            continue

        ordered = ORDERED_RE.match(line)
        if ordered:
            flush_all()
            item_kind = "ordered"
            item_depth = len(ordered.group(1)) // 2
            item_number = ordered.group(2)
            item_buf = [ordered.group(3).strip()]
            index += 1
            continue

        # Anything else continues whatever is open: a list item's wrapped line,
        # an open blockquote, or a plain paragraph.
        if item_kind is not None:
            item_buf.append(line)
        elif quote_buf:
            quote_buf.append(line)
        else:
            para_buf.append(line)
        index += 1

    if in_code and code_buf:
        _add_code_block(doc, code_buf)
    flush_all()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    return len(doc.paragraphs), n_tables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="source", default="REPORT.md")
    parser.add_argument("--out", dest="target", default="REPORT.docx")
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)
    markdown = source.read_text(encoding="utf-8")
    n_paragraphs, n_tables = convert(markdown, target)
    size_kb = target.stat().st_size / 1024
    print(f"{source} -> {target}")
    print(f"  {n_paragraphs} paragraphs, {n_tables} tables, {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
