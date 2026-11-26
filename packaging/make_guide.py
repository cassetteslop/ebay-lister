"""Render docs/USER_GUIDE.md to a PDF that ships with the built app.

    python packaging/make_guide.py [output.pdf]     (default: build/guide/Ebay Lister User Guide.pdf)

Needs reportlab (in requirements-build.txt). Both PyInstaller specs run this script, so every build
gets a fresh guide; you can also run it by hand to check the result.

Only the Markdown the guide uses is supported: #/##/### headings, paragraphs, "* " and "1. " lists,
"> " tip boxes, pipe tables, ``` code blocks, and inline **bold**, *italic*, `code` and [links](url).
The PDF uses the built-in Helvetica fonts (no font files to bundle), so the text must stay within
the Windows-1252 character set; the script stops with an error if it finds anything else.
"""

import html
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    CondPageBreak,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "docs", "USER_GUIDE.md")
sys.path.insert(0, ROOT)
from ebay_lister.config import APP_NAME, GUIDE_PDF  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "build", "guide", GUIDE_PDF)

ACCENT = colors.HexColor("#3665f3")      # eBay-ish blue, for headings and rules
INK = colors.HexColor("#1f2328")
MUTED = colors.HexColor("#59636e")
TIP_BG = colors.HexColor("#eef3ff")
CODE_BG = colors.HexColor("#f3f4f6")
RULE = colors.HexColor("#d0d7de")


def version():
    with open(os.path.join(ROOT, "ebay_lister", "__init__.py"), encoding="utf-8") as f:
        return re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)


# ---------------------------------------------------------------------------- styles
def _styles():
    base = dict(fontName="Helvetica", fontSize=10.5, leading=14.5, textColor=INK)
    s = {
        "body": ParagraphStyle("body", spaceAfter=7, **base),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 9.5, "leading": 12.5}),
        "cellhead": ParagraphStyle("cellhead", **{**base, "fontName": "Helvetica-Bold", "fontSize": 9.5, "leading": 12.5,
                                                  "textColor": colors.white}),
        "tip": ParagraphStyle("tip", **{**base, "textColor": INK}),
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=30, leading=36, textColor=INK, alignment=TA_CENTER),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=ACCENT,
                             spaceBefore=16, spaceAfter=8),
        "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=INK,
                             spaceBefore=10, spaceAfter=5),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=13, leading=18, textColor=MUTED,
                                   alignment=TA_CENTER),
        "toc": ParagraphStyle("toc", **{**base, "fontSize": 11, "leading": 17}),
        "code": ParagraphStyle("code", fontName="Courier", fontSize=9, leading=12, textColor=INK),
    }
    return s


# ---------------------------------------------------------------------------- inline markup
def inline(text):
    """Markdown inline markup -> reportlab's mini-HTML."""
    out, pos = [], 0
    for m in re.finditer(r"`([^`]+)`", text):  # protect code spans first
        out.append(_emphasis(html.escape(text[pos:m.start()], quote=False)))
        out.append(f'<font face="Courier" color="#0b4f9e">{html.escape(m.group(1), quote=False)}</font>')
        pos = m.end()
    out.append(_emphasis(html.escape(text[pos:], quote=False)))
    return "".join(out)


def _emphasis(s):
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" color="#3665f3"><u>\1</u></a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    return s


# ---------------------------------------------------------------------------- block parser
def parse(md):
    """Yield (kind, payload) blocks from the Markdown source."""
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            yield "code", "\n".join(lines[i + 1:j])
            i = j + 1
            continue
        m = re.match(r"(#{1,3})\s+(.*)", stripped)
        if m:
            yield f"h{len(m.group(1))}", m.group(2)
            i += 1
            continue
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            yield "table", rows
            continue
        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            yield "tip", " ".join(buf)
            continue
        m = re.match(r"([*-]|\d+\.)\s+", stripped)
        if m:
            ordered = m.group(1)[0].isdigit()
            items = []
            while i < len(lines):
                s = lines[i].strip()
                mm = re.match(r"([*-]|\d+\.)\s+(.*)", s)
                if mm:
                    items.append(mm.group(2))
                elif s and lines[i].startswith((" ", "\t")) and items:
                    items[-1] += " " + s          # continuation line
                else:
                    break
                i += 1
            yield ("ol" if ordered else "ul"), items
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"(#{1,3}\s|```|\||>|[*-]\s|\d+\.\s)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        yield "p", " ".join(buf)


# ---------------------------------------------------------------------------- flowables
def build_story(md, st):
    blocks = list(parse(md))
    title = next((p for k, p in blocks if k == "h1"), APP_NAME + " User Guide")
    chapters = [p for k, p in blocks if k == "h2"]

    story = [Spacer(1, 2.2 * inch), Paragraph(inline(title), st["h1"]), Spacer(1, 14),
             Paragraph(f"Quick start and user guide &middot; version {version()}", st["subtitle"]), Spacer(1, 0.6 * inch)]
    intro_done = False
    pending = []  # heading flowables waiting to be kept together with the first block after them

    def emit(*flowables):
        flowables = list(flowables)
        if pending:
            story.append(KeepTogether(pending[:] + flowables[:1]))
            pending.clear()
            flowables = flowables[1:]
        story.extend(flowables)
    width = LETTER[0] - 2 * 0.9 * inch

    for kind, payload in blocks:
        if kind == "h1":
            continue
        if kind == "h2":
            if not intro_done:  # cover page ends with the intro paragraphs, then a contents page
                story += [PageBreak(), Paragraph("Contents", st["h2"])]
                story += [Paragraph(f"{n}.&nbsp;&nbsp;{inline(c)}", st["toc"]) for n, c in enumerate(chapters, 1)]
                story.append(PageBreak())
                intro_done = True
            else:
                story.append(CondPageBreak(1.6 * inch))  # don't strand a heading at the bottom of a page
            n = chapters.index(payload) + 1
            pending += [Paragraph(f"{n}.&nbsp;&nbsp;{inline(payload)}", st["h2"]), _rule(width)]
        elif kind == "h3":
            story.append(CondPageBreak(1.1 * inch))
            pending.append(Paragraph(inline(payload), st["h3"]))
        elif kind == "p":
            emit(Paragraph(inline(payload), st["body"] if intro_done else st["subtitle"]))
            if not intro_done:
                story.append(Spacer(1, 6))
        elif kind in ("ul", "ol"):
            items = [ListItem(Paragraph(inline(t), st["body"]), leftIndent=16) for t in payload]
            kw = dict(bulletType="1", bulletFormat="%s.", bulletFontName="Helvetica-Bold") if kind == "ol" else \
                dict(bulletType="bullet", start="•", bulletColor=ACCENT)
            emit(ListFlowable(items, leftIndent=16, bulletFontSize=10, **kw), Spacer(1, 3))
        elif kind == "tip":
            t = Table([[Paragraph(inline(payload), st["tip"])]], colWidths=[width])
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TIP_BG), ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                   ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
            emit(Spacer(1, 4), t, Spacer(1, 10))
        elif kind == "code":
            t = Table([[Preformatted(payload, st["code"])]], colWidths=[width])
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CODE_BG), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                                   ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
            emit(t, Spacer(1, 9))
        elif kind == "table":
            table = _table(payload, width, st)
            if len(payload) <= 8 and not pending and story and isinstance(story[-1], (Paragraph, KeepTogether)):
                table = KeepTogether([story.pop(), table])  # keep the lead-in sentence with its table
            emit(table, Spacer(1, 10))
    return story


def _rule(width):
    t = Table([[""]], colWidths=[width], rowHeights=[2])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1, RULE)]))
    return t


def _table(rows, width, st):
    head, body = rows[0], rows[1:]
    data = [[Paragraph(inline(c), st["cellhead"]) for c in head]] + \
           [[Paragraph(inline(c), st["cell"]) for c in r] for r in body]
    first = 0.3 if len(head) == 2 else 1 / len(head)
    cols = [width * first] + [width * (1 - first) / (len(head) - 1)] * (len(head) - 1) if len(head) > 1 else [width]
    t = Table(data, colWidths=cols, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), ACCENT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE), ("TOPPADDING", (0, 0), (-1, -1), 5),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 7)]
    style += [("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f6f8fa")) for r in range(2, len(data), 2)]
    t.setStyle(TableStyle(style))
    return t


def _page(canvas, doc):
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.9 * inch, 0.55 * inch, f"{APP_NAME} User Guide")
    canvas.drawRightString(LETTER[0] - 0.9 * inch, 0.55 * inch, str(doc.page))
    canvas.restoreState()


# ---------------------------------------------------------------------------- main
def check_charset(md):
    """Helvetica only covers Windows-1252; anything else would print as a black box."""
    bad = []
    for n, line in enumerate(md.splitlines(), 1):
        for ch in line:
            try:
                ch.encode("cp1252")
            except UnicodeEncodeError:
                bad.append(f"  line {n}: {ch!r} (U+{ord(ch):04X})")
    return bad


def render(out=DEFAULT_OUT, source=SOURCE):
    with open(source, encoding="utf-8") as f:
        md = f.read()
    bad = check_charset(md)
    if bad:
        raise SystemExit(f"{source} has characters the PDF fonts can't show; replace them:\n" + "\n".join(bad))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    doc = SimpleDocTemplate(out, pagesize=LETTER, leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.85 * inch, bottomMargin=0.9 * inch,
                            title=f"{APP_NAME} User Guide", author=APP_NAME, subject="Quick start and user guide")
    doc.build(build_story(md, _styles()), onFirstPage=_page, onLaterPages=_page)
    return out


if __name__ == "__main__":
    print("User guide written to", render(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT))
