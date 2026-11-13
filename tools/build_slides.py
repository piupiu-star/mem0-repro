"""Build the 14-slide presentation deck for the Mem0 reproduction talk.

Output: slides/Mem0_Reproduction.pptx   (16:9, 13.333 x 7.5 in)

Run from anywhere:  python -m tools.build_slides
Every number on every slide is copied from REPORT.docx / results/summary.md.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "slides"
OUT = OUT_DIR / "Mem0_Reproduction.pptx"

# ---------------------------------------------------------------- design tokens
INK = RGBColor(0x1F, 0x23, 0x28)
MUTED = RGBColor(0x6E, 0x77, 0x81)
RULE = RGBColor(0xD0, 0xD7, 0xDE)
ACCENT = RGBColor(0x0B, 0x3C, 0x5D)
ALERT = RGBColor(0xA4, 0x26, 0x2C)
PANEL = RGBColor(0xF2, 0xF4, 0xF7)

HEAD = "Calibri Light"
BODY = "Calibri"

LEFT = Inches(0.9)
WIDTH = 11.5
FOOTER = "Mem0 on LOCOMO  ·  reproducibility study  ·  Xiuling PIAO 1155267871"


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def text(slide, x, y, w, h, body, size=18, bold=False, color=INK, font=BODY,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line=1.12, space=6,
         italic=False, caps=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0

    paras = body if isinstance(body, list) else [body]
    for i, item in enumerate(paras):
        if isinstance(item, tuple):
            chunk, opts = item[0], item[1]
        else:
            chunk, opts = item, {}
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = opts.get("align", align)
        p.line_spacing = opts.get("line", line)
        p.space_after = Pt(opts.get("space", space))
        run = p.add_run()
        run.text = chunk.upper() if caps else chunk
        f = run.font
        f.name = opts.get("font", font)
        f.size = Pt(opts.get("size", size))
        f.bold = opts.get("bold", bold)
        f.italic = opts.get("italic", italic)
        f.color.rgb = opts.get("color", color)
    return box


def rule(slide, x, y, w, thick=0.9, color=RULE):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y),
                                 Inches(w), Pt(thick))
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def rect(slide, x, y, w, h, fill=PANEL, line=None):
    box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y),
                                 Inches(w), Inches(h))
    box.fill.solid()
    box.fill.fore_color.rgb = fill
    if line is None:
        box.line.fill.background()
    else:
        box.line.color.rgb = line
        box.line.width = Pt(0.75)
    box.shadow.inherit = False
    return box


def header(slide, kicker, title, subtitle=None):
    text(slide, LEFT.inches, 0.62, WIDTH, 0.3, kicker, size=11, color=ACCENT,
         bold=True, caps=True)
    text(slide, LEFT.inches, 0.95, WIDTH, 0.75, title, size=32, font=HEAD,
         bold=True)
    rule(slide, LEFT.inches, 1.72, WIDTH, 1.2, ACCENT)
    if subtitle:
        text(slide, LEFT.inches, 1.88, WIDTH, 0.4, subtitle, size=15, color=MUTED)


def footer(slide, n):
    text(slide, LEFT.inches, 7.02, 9.6, 0.25, FOOTER, size=9, color=MUTED)
    text(slide, 11.4, 7.02, 1.0, 0.25, str(n), size=9, color=MUTED,
         align=PP_ALIGN.RIGHT)


def grid(slide, x, y, w, fracs, rows, row_h=0.46, size=16, header_row=True,
         aligns=None, colors=None, bold_first=True, top=True):
    """Booktabs-style table: rules only, no fills, no grid lines."""
    cols = [f * w for f in fracs]
    xs, acc = [], x
    for c in cols:
        xs.append(acc)
        acc += c

    if top:
        rule(slide, x, y, w, 1.4, INK)
    ry = y + 0.08
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            is_head = header_row and i == 0
            align = aligns[j] if aligns else (PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT)
            colour = colors[i][j] if colors and colors[i][j] else (MUTED if is_head else INK)
            text(slide, xs[j] + 0.06, ry + 0.02, cols[j] - 0.12, row_h - 0.04, cell,
                 size=size, bold=is_head or (bold_first and j == 0),
                 color=colour, align=align, anchor=MSO_ANCHOR.MIDDLE)
        ry += row_h
        if is_head and header_row:
            rule(slide, x, ry, w, 0.9, INK)
    rule(slide, x, ry, w, 1.4, INK)


# ---------------------------------------------------------------- slides

def s01_cover(prs):
    s = blank(prs)
    rect(s, 0, 0, 0.28, 7.5, ACCENT)
    text(s, 1.1, 1.55, 10.6, 0.4, "FTEC5660  ·  Agentic AI for Business and FinTech",
         size=12, color=MUTED, bold=True, caps=True)
    text(s, 1.1, 2.05, 11.0, 1.5, "Reproducing Mem0 on LOCOMO", size=46,
         font=HEAD, bold=True)
    text(s, 1.1, 3.15, 10.6, 0.9,
         "What reproduces, what does not, and one missing parameter that explains the gap",
         size=20, color=MUTED)
    rule(s, 1.1, 4.25, 4.2, 1.4, ACCENT)
    text(s, 1.1, 4.55, 6.0, 0.35, "Xiuling PIAO  ·  1155267871", size=17, bold=True)
    text(s, 1.1, 4.95, 8.0, 0.35, "github.com/piupiu-star/mem0-repro", size=15, color=MUTED)
    text(s, 1.1, 6.5, 9.0, 0.3, "Recorded presentation  ·  13 November 2026", size=12, color=MUTED)


def s02_scoreboard(prs):
    s = blank(prs)
    header(s, "summary", "Three targets, three different outcomes")
    rows = [
        ("R1  accuracy", "65.3 %", "Part reproduces. Exact away from the temporal block."),
        ("R2  efficiency", "58.9 %", "Direction holds at 58.9 % against a claimed >90 %."),
        ("R3  version drift", "found", "Not a number to hit. A cause I could name."),
    ]
    y = 2.15
    for label, value, note in rows:
        text(s, LEFT.inches, y, 3.2, 0.35, label, size=17, bold=True, color=ACCENT)
        text(s, 4.1, y - 0.18, 2.4, 0.7, value, size=34, font=HEAD, bold=True)
        text(s, 6.6, y - 0.05, 5.6, 0.9, note, size=15, color=MUTED)
        rule(s, LEFT.inches, y + 0.62, WIDTH, 0.75, RULE)
        y += 1.05

    text(s, LEFT.inches, 5.45, WIDTH, 0.9,
         [("The headline gap is not a weaker system.", {"bold": True, "size": 19}),
          ("Remove the one category the SDK cannot support and the rest lands at 92.0 % against 92.5 % reported.",
           {"size": 17, "color": MUTED})],
         )
    footer(s, 2)


def s03_scope(prs):
    s = blank(prs)
    header(s, "what I attempted", "One benchmark, one conversation, three trials")
    items = [
        ("Paper and code", "Mem0 (arXiv:2504.19413), open-source v3 SDK, mem0ai 2.2.1"),
        ("Data", "LOCOMO conversation 0: 19 sessions, reference date 22 October 2023"),
        ("Questions", "120 in scope: multi-hop 32, temporal 37, open-domain 13, single-hop 38"),
        ("Metric", "LLM-as-a-judge accuracy, the authors' judge prompt and parsing"),
        ("Claims under test", "92.5 % overall, >90 % fewer tokens, 91 % lower p95 latency"),
    ]
    y = 2.2
    for label, body in items:
        text(s, LEFT.inches, y, 2.9, 0.35, label, size=16, bold=True, color=ACCENT)
        text(s, 3.9, y, 8.2, 0.6, body, size=16)
        rule(s, LEFT.inches, y + 0.58, WIDTH, 0.75, RULE)
        y += 0.86
    footer(s, 3)


def s04_setup(prs):
    s = blank(prs)
    header(s, "setup", "Held fixed what defines the task, swapped what I could not reach")
    quad = [
        ("Environment", "Windows 11 laptop, Python 3.11.6, mem0ai 2.2.1, Qdrant local mode"),
        ("Model substitution", "DeepSeek chat for answers and judging, DeepSeek embeddings"),
        ("Held fixed", "Dataset, questions, judge prompt, retrieval depth frozen at top-200"),
        ("Cost", "$3.80 of API billing for the whole study, about 45 minutes of compute"),
    ]
    for i, (label, body) in enumerate(quad):
        x = LEFT.inches + (i % 2) * 5.85
        y = 2.05 + (i // 2) * 1.95
        rect(s, x, y, 5.45, 1.6, PANEL)
        text(s, x + 0.3, y + 0.2, 4.9, 0.3, label, size=13, bold=True, color=ACCENT, caps=True)
        text(s, x + 0.3, y + 0.58, 4.85, 0.9, body, size=15)
    text(s, LEFT.inches, 6.1, WIDTH, 0.4,
         "Substitution is documented and held constant, so A/B comparisons inside the study stay valid.",
         size=13, italic=True, color=MUTED)
    footer(s, 4)


def s05_accuracy(prs):
    s = blank(prs)
    header(s, "results  ·  R1", "Accuracy: 65.3 % against 92.5 % reported")
    rows = [
        ["category", "reported", "measured", "verdict"],
        ["overall", "92.5", "65.3 ± 0.5", "27.2 points below"],
        ["single-hop", "91.2", "96.5", "5.3 above"],
        ["multi-hop", "91.3", "84.4", "6.9 below"],
        ["open-domain", "72.7", "97.4", "24.7 above"],
        ["temporal", "92.0", "5.4", "86.6 below"],
    ]
    colors = [[None] * 4 for _ in rows]
    colors[5][2] = ALERT
    colors[5][3] = ALERT
    grid(s, LEFT.inches, 2.05, WIDTH, [0.28, 0.18, 0.24, 0.30], rows,
         row_h=0.56, size=17, colors=colors, top=False)
    text(s, LEFT.inches, 5.85, WIDTH, 0.9,
         [("Two categories beat the reported score, one is within seven points, one is destroyed.",
           {"size": 17}),
          ("A single averaged number hides all of that, which is why I do not report one.",
           {"size": 15, "color": MUTED})])
    footer(s, 5)


def s06_bignumber(prs):
    s = blank(prs)
    header(s, "results  ·  the collapse", "The damage is total, and it is not noise")
    text(s, 0.85, 2.0, 5.6, 1.9, "5.4 %", size=120, font=HEAD, bold=True, color=ALERT)
    text(s, 0.95, 4.15, 5.6, 0.9,
         [("6 correct out of 111 question-instances", {"size": 18, "bold": True}),
          ("2 out of 37 in every one of three trials", {"size": 16, "color": MUTED})])
    rect(s, 7.2, 2.15, 0.014, 3.45, RULE)
    text(s, 7.6, 2.15, 4.6, 0.4, "Why this cannot be sampling", size=13, bold=True, color=ACCENT, caps=True)
    text(s, 7.6, 2.6, 4.6, 2.6,
         [("Identical counts in all three trials, so the spread is zero.", {"size": 16, "space": 14}),
          ("The answering model is confident and wrong, because the memories it retrieves carry wrong dates.",
           {"size": 16, "space": 14}),
          ("Per-trial overall stability is ±0.5 points. This is not a coin flip.", {"size": 16})])
    footer(s, 6)


def s07_chain(prs):
    s = blank(prs)
    header(s, "results  ·  cause", "One parameter the open-source package will not accept")
    steps = [
        ("1", "The authors' runner anchors every session",
         "mem0.add(messages, user_id, timestamp=session_epoch)"),
        ("2", "The open-source SDK refuses it",
         "timestamp is gated in mem0/memory/notices.py and raises ValueError"),
        ("3", "My adapter catches the refusal and retries without it",
         "ingestion succeeds, so nothing looks wrong"),
        ("4", "Extraction then anchors on the wall clock",
         "a 2023 conversation gets dates such as November 2026"),
    ]
    y = 2.1
    for num, head, detail in steps:
        rect(s, LEFT.inches, y, 0.42, 0.42, ACCENT)
        text(s, LEFT.inches, y + 0.04, 0.42, 0.35, num, size=17, bold=True,
             color=RGBColor(0xFF, 0xFF, 0xFF), align=PP_ALIGN.CENTER)
        text(s, 1.6, y - 0.04, 10.4, 0.35, head, size=18, bold=True)
        text(s, 1.6, y + 0.36, 10.4, 0.35, detail, size=14, color=MUTED)
        y += 1.12
    footer(s, 7)


def s08_evidence(prs):
    s = blank(prs)
    header(s, "results  ·  evidence", "What the store actually returned")
    rect(s, LEFT.inches, 2.15, WIDTH, 1.55, PANEL)
    text(s, 1.2, 2.35, 10.9, 0.3, "RETRIEVED MEMORY", size=11, bold=True, color=MUTED, caps=True)
    text(s, 1.2, 2.7, 10.9, 0.9,
         "“Caroline attended an LGBTQ support group on November 11, 2026, and found the experience very powerful”",
         size=19, italic=True)
    text(s, LEFT.inches, 4.0, 5.0, 0.4, "Gold answer", size=13, bold=True, color=ACCENT, caps=True)
    text(s, LEFT.inches, 4.35, 5.0, 0.5, "7 May 2023", size=26, font=HEAD, bold=True)
    text(s, 6.3, 4.0, 5.9, 0.4, "The conversation", size=13, bold=True, color=ACCENT, caps=True)
    text(s, 6.3, 4.35, 5.9, 0.5, "a session from 2023", size=26, font=HEAD, bold=True)
    rule(s, LEFT.inches, 5.25, WIDTH, 0.75, RULE)
    text(s, LEFT.inches, 5.5, WIDTH, 1.1,
         [("Nothing threw an error.", {"size": 17, "bold": True}),
          ("Ingestion reported success, the store filled up, the run exited cleanly, and the only trace was one warning line about the adapted call.",
           {"size": 15, "color": MUTED})])
    footer(s, 8)


def s09_mod(prs):
    s = blank(prs)
    header(s, "modification", "The change is one flag")
    text(s, LEFT.inches, 2.05, WIDTH, 0.6,
         "add(..., infer=False)", size=34, font="Consolas", bold=True, color=ACCENT)
    text(s, LEFT.inches, 2.75, WIDTH, 0.4,
         "turns off Mem0's LLM fact-extraction stage, so turns are stored verbatim instead of rewritten into facts.",
         size=17, color=MUTED)
    points = [
        ("It tests the mechanism", "Extraction is the stage the paper credits for accuracy."),
        ("It is isolated", "One boolean, set on every ingest call and every fallback path."),
        ("It is measurable", "A paired test on identical questions, same judge, same depth."),
        ("It cannot flip back unnoticed", "If the SDK changes its signature, the flag still applies."),
    ]
    x, y = LEFT.inches, 3.75
    for i, (head, body) in enumerate(points):
        cx = x + (i % 2) * 5.85
        cy = y + (i // 2) * 1.35
        text(s, cx, cy, 5.4, 0.3, head, size=15, bold=True)
        text(s, cx, cy + 0.32, 5.35, 0.6, body, size=14, color=MUTED)
    footer(s, 9)


def s10_result(prs):
    s = blank(prs)
    header(s, "modification  ·  result", "What the flag bought: +12.2 points")
    rows = [
        ["category", "extraction on", "extraction off", "change"],
        ["overall", "65.3 %", "77.5 %", "+12.2"],
        ["temporal", "5.4 %", "36.9 %", "+31.5"],
        ["multi-hop", "84.4 %", "92.7 %", "+8.3"],
        ["single-hop", "96.5 %", "98.2 %", "+1.7"],
        ["open-domain", "97.4 %", "94.9 %", "−2.5"],
    ]
    colors = [[None] * 4 for _ in rows]
    colors[2][3] = ACCENT
    colors[5][3] = ALERT
    grid(s, LEFT.inches, 2.05, WIDTH, [0.28, 0.22, 0.24, 0.20], rows,
         row_h=0.5, size=16, colors=colors, top=False)
    text(s, LEFT.inches, 5.5, 5.6, 0.9,
         [("44 questions gained out of 360", {"size": 17, "bold": True}),
          ("35 temporal, 8 multi-hop, 2 single-hop, and one lost in open-domain.",
           {"size": 14, "color": MUTED})])
    text(s, 6.6, 5.45, 5.7, 1.2,
         [("51 gained, 7 lost, McNemar p < 0.001, CI [+8.3, +16.4]", {"size": 14}),
          ("At top-10 the gain disappears: +1.7 points, p = 0.791", {"size": 14}),
          ("So the gain needs a broad slice of memory to appear.", {"size": 14, "color": MUTED})])
    footer(s, 10)


def s11_cost(prs):
    s = blank(prs)
    header(s, "modification  ·  cost", "It is not a free win")
    stats = [
        ("10.1 K to 11.4 K", "prompt tokens per query, so the token saving falls from 58.9 % to 53.3 %"),
        ("535 s to 10 s", "ingest wall clock, because extraction was the expensive stage"),
        ("about 13 %", "more text reaches the answerer, since raw turns are longer than extracted facts"),
    ]
    y = 2.15
    for value, note in stats:
        text(s, LEFT.inches, y, 3.6, 0.5, value, size=26, font=HEAD, bold=True, color=ACCENT)
        text(s, 4.7, y + 0.02, 7.7, 0.9, note, size=15, color=MUTED)
        rule(s, LEFT.inches, y + 0.95, WIDTH, 0.75, RULE)
        y += 1.25
    text(s, LEFT.inches, 6.0, WIDTH, 0.8,
         [("The honest reading", {"size": 15, "bold": True, "color": ACCENT, "space": 4}),
          ("Part of the accuracy gain could come from seeing more text rather than from cleaner memories. The top-10 result, where the gain vanishes, is consistent with that.",
           {"size": 15, "color": MUTED})])
    footer(s, 11)


def s12_notrepro(prs):
    s = blank(prs)
    header(s, "results  ·  the rest", "What did not reproduce, and what that tells me")
    rows = [
        ("Token saving", "58.9 % against >90 % claimed",
         "The direction holds. The magnitude does not."),
        ("Latency", "retrieval 14x faster, end to end 3.55 s against 3.80 s",
         "It is a search-latency claim, not a request-latency claim."),
        ("Full-context", "99.2 % (119 of 120)",
         "So the loss is in the memory pipeline, not in my harness or the model."),
    ]
    y = 2.05
    for head, fact, verdict in rows:
        text(s, LEFT.inches, y, 2.6, 0.35, head, size=16, bold=True, color=ACCENT)
        text(s, 3.6, y, 4.6, 0.8, fact, size=15)
        text(s, 8.4, y, 4.0, 0.9, verdict, size=15, color=MUTED)
        rule(s, LEFT.inches, y + 0.85, WIDTH, 0.75, RULE)
        y += 1.12
    text(s, LEFT.inches, 5.85, WIDTH, 0.8,
         [("99.2 % is the control that makes the rest readable.", {"size": 15, "bold": True, "space": 4}),
          ("A full-context baseline scoring that high says the harness, the judge and the model all work. The 65.3 % is what the memory layer does to them.",
           {"size": 15, "color": MUTED})])
    footer(s, 12)


def s13_recs(prs):
    s = blank(prs)
    header(s, "lessons", "Three things I would tell the next person")
    recs = [
        ("Do not self-host Mem0 unpatched if your task involves dates.",
         "Temporal accuracy is close to zero and nothing warns you."),
        ("Never trust Memory.get_all() for a count.",
         "It defaults to top_k = 20, so a store of 500 reports 20."),
        ("Measure full-context before adopting a memory layer.",
         "It scored 99.2 % here at 2.4 times the tokens. The trade depends on your budget."),
    ]
    y = 2.15
    for i, (head, body) in enumerate(recs, start=1):
        text(s, LEFT.inches, y - 0.05, 0.5, 0.5, str(i), size=30, font=HEAD, bold=True, color=RULE)
        text(s, 1.55, y, 10.3, 0.4, head, size=18, bold=True)
        text(s, 1.55, y + 0.42, 10.3, 0.6, body, size=15, color=MUTED)
        y += 1.3
    footer(s, 13)


def s14_close(prs):
    s = blank(prs)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = RGBColor(0x0B, 0x3C, 0x5D)
    text(s, 1.1, 2.1, 11.0, 0.4, "closing", size=12, bold=True, caps=True,
         color=RGBColor(0x9C, 0xB8, 0xCC))
    text(s, 1.1, 2.6, 11.0, 1.6,
         "The number did not match.\nThe reason did.",
         size=40, font=HEAD, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
    rule(s, 1.1, 4.45, 3.6, 1.4, RGBColor(0x9C, 0xB8, 0xCC))
    text(s, 1.1, 4.8, 11.0, 0.9,
         "One missing parameter, one warning line in a log, and nothing else went wrong.",
         size=17, color=RGBColor(0xD6, 0xE1, 0xEA))
    text(s, 1.1, 6.35, 11.0, 0.35,
         "Xiuling PIAO  ·  1155267871  ·  github.com/piupiu-star/mem0-repro",
         size=13, color=RGBColor(0x9C, 0xB8, 0xCC))


NOTES = {
    1: "Thirty seconds on who I am and what the study is. Say the conclusion early: three targets, "
       "three different outcomes. Do not read the subtitle.",
    2: "This is the whole talk in one slide. R1 reproduces exactly away from one category. R2 reproduces "
       "in direction, not in size. R3 is not a number, it is a cause. If someone stops watching after "
       "two minutes, they should still know these three lines.",
    3: "Scope, fast. One benchmark, one conversation, 120 questions, three trials. Mention that the "
       "adversarial category is excluded because the authors exclude it.",
    4: "Setup in twenty seconds. The substitution matters: DeepSeek replaces their model stack, so "
       "absolute numbers are not comparable, which is why every claim I make rests on comparisons "
       "inside my own study. Total spend was 3.80 dollars.",
    5: "Read two rows only: overall and temporal. Two categories beat the reported score, one is within "
       "seven points, one is destroyed. A single average hides that, which is why I do not report one.",
    6: "Let the number sit. Six correct out of 111. Identical counts in all three trials, so there is no "
       "spread to measure. Then the key sentence: the model is not confused, the memories it reads are "
       "wrong.",
    7: "This is the core of the talk. Four steps, in order. The authors anchor each session with a "
       "timestamp, the open-source SDK refuses that argument, my adapter retries without it, and "
       "extraction then anchors on the wall clock.",
    8: "Read the quoted memory out loud, then say the date of the conversation. Pause. Then make the "
       "point that nothing threw an error: this is a silent failure, and only the temporal questions "
       "reveal it.",
    9: "One flag. It is isolated, it is measurable, and it tests the mechanism the paper credits for "
       "accuracy. Say why an ablation on identical questions gives a clean paired comparison.",
    10: "Up 12.2 points overall, 31.5 in temporal, and one question lost in open-domain. Then the caveat: "
        "51 gained, 7 lost, p below 0.001. And the honest one: at top-10 the gain disappears, so the "
        "effect needs a broad slice of memory.",
    11: "Not free. About 1.3 K extra tokens per query, a much faster ingest, and 13 percent more text in "
         "the prompt. Say plainly that part of the gain may come from volume rather than from cleaner "
         "memories.",
    12: "Two claims that did not reproduce: the size of the token saving and the latency framing. Then "
         "the control that makes the rest readable: full-context scores 99.2 percent, so the harness, "
         "the judge and the model all work.",
    13: "Three recommendations, one sentence each. Do not read all six from the report.",
    14: "Recap in three beats: accuracy reproduces once the unsupported category is set aside, efficiency and "
        "latency hold in direction only. Then the lesson, that the failure never raised an error, so silence "
        "is not success. Do not read the slide aloud, it repeats you. Stop talking three seconds before you "
        "stop the recording.",
}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    for build in (s01_cover, s02_scoreboard, s03_scope, s04_setup, s05_accuracy,
                  s06_bignumber, s07_chain, s08_evidence, s09_mod, s10_result,
                  s11_cost, s12_notrepro, s13_recs, s14_close):
        build(prs)

    for n, slide in enumerate(prs.slides, start=1):
        if n in NOTES:
            slide.notes_slide.notes_text_frame.text = NOTES[n]

    prs.save(str(OUT))
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(prs.slides._sldIdLst)} slides, "
          f"{len(NOTES)} with speaker notes)")


if __name__ == "__main__":
    main()
