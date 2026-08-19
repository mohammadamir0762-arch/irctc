"""
Generates the project presentation (PS91_Presentation.pptx) in the repo root.

Concept-led and deliberately short. The deck presents one platform with four
capabilities serving two audiences — passengers and railway operations — rather
than a set of separate features. Charts and detailed statistics are kept out on
purpose; the analysis behind them lives in analysis/benchmark.py and
new/EDA_INSIGHTS_REPORT.md for anyone who asks.

Run:  python analysis/make_ppt.py
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "PS91_Presentation.pptx"

INK = RGBColor(0x0F, 0x17, 0x2A)
SLATE = RGBColor(0x1E, 0x29, 0x3B)
MUTED = RGBColor(0x64, 0x74, 0x8B)
PALE = RGBColor(0xCB, 0xD5, 0xE1)
PAPER = RGBColor(0xFF, 0xFF, 0xFF)
WASH = RGBColor(0xF1, 0xF5, 0xF9)
ACCENT = RGBColor(0x0E, 0xA5, 0xE9)
GOOD = RGBColor(0x05, 0x96, 0x69)
WARN = RGBColor(0xD9, 0x77, 0x06)
BAD = RGBColor(0xDC, 0x26, 0x26)

FONT = "Arial"
W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.72)


def blank(prs, bg=PAPER):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bgshape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
    bgshape.fill.solid()
    bgshape.fill.fore_color.rgb = bg
    bgshape.line.fill.background()
    bgshape.shadow.inherit = False
    return slide


def textbox(slide, x, y, w, h, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.paragraphs[0].alignment = align
    return tf


def write(tf, text, size, color=INK, bold=False, space_after=6, first=False,
          align=None, italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.text = text
    p.space_after = Pt(space_after)
    if align is not None:
        p.alignment = align
    for run in p.runs:
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.bold = bold
        run.font.italic = italic
        run.font.name = FONT
    return p


def rule(slide, x, y, w, color=ACCENT, thickness=Pt(3)):
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, thickness)
    line.fill.solid()
    line.fill.fore_color.rgb = color
    line.line.fill.background()
    line.shadow.inherit = False


def heading(slide, title, eyebrow=None):
    y = Inches(0.5)
    if eyebrow:
        tf = textbox(slide, MARGIN, y, W - 2 * MARGIN, Inches(0.3))
        write(tf, eyebrow.upper(), 11, MUTED, bold=True, first=True, space_after=0)
        y += Inches(0.34)
    tf = textbox(slide, MARGIN, y, W - 2 * MARGIN, Inches(0.6))
    write(tf, title, 30, INK, bold=True, first=True, space_after=0)
    rule(slide, MARGIN, y + Inches(0.66), Inches(1.1))
    return y + Inches(1.02)


def card(slide, x, y, w, h, fill=WASH):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    shape.shadow.inherit = False
    shape.adjustments[0] = 0.05
    return shape


def bullets_slide(prs, title, bullets, eyebrow=None, footnote=None):
    slide = blank(prs)
    y = heading(slide, title, eyebrow)
    tf = textbox(slide, MARGIN, y, W - 2 * MARGIN, H - y - Inches(0.9))
    for i, item in enumerate(bullets):
        if isinstance(item, tuple):
            label, detail = item
            write(tf, label, 19, INK, bold=True, first=(i == 0), space_after=3)
            write(tf, detail, 15, MUTED, space_after=17)
        else:
            write(tf, "•   " + item, 17, INK, first=(i == 0), space_after=13)
    if footnote:
        tf = textbox(slide, MARGIN, H - Inches(0.82), W - 2 * MARGIN, Inches(0.4))
        write(tf, footnote, 11, MUTED, first=True, space_after=0, italic=True)
    return slide


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # ---------------------------------------------------------------- 1 title
    slide = blank(prs, INK)
    tf = textbox(slide, MARGIN, Inches(2.05), W - 2 * MARGIN, Inches(0.4))
    write(tf, "PROBLEM STATEMENT PS91", 13, ACCENT, bold=True, first=True, space_after=0)
    tf = textbox(slide, MARGIN, Inches(2.62), Inches(11), Inches(2.1))
    write(tf, "RailSure", 54, PAPER, bold=True, first=True, space_after=6)
    write(tf, "Journey confidence for Indian Railways", 26, PALE, space_after=0)
    tf = textbox(slide, MARGIN, Inches(4.85), Inches(10.2), Inches(1.0))
    write(tf, "One platform that tells passengers whether their ticket will confirm and whether",
          16, PALE, first=True, space_after=2)
    write(tf, "they will make their connection — and tells railway staff who is about to miss one.",
          16, PALE, space_after=0)
    rule(slide, MARGIN, Inches(6.05), Inches(2.2))
    tf = textbox(slide, MARGIN, Inches(6.3), Inches(11), Inches(0.5))
    write(tf, "irctc-smoky.vercel.app     ·     github.com/mohammadamir0762-arch/irctc",
          12, MUTED, first=True, space_after=0)

    # -------------------------------------------------------------- 2 problem
    bullets_slide(
        prs, "A journey has more than one way to fail", eyebrow="The problem",
        bullets=[
            ("The ticket might not confirm",
             "A ticket says WL 23 and nothing tells you whether it will clear. Passengers hold "
             "tickets they cannot use, or cancel ones that would have confirmed."),
            ("The connection might not hold",
             "Many city pairs have no direct train, so passengers book two legs and hope the "
             "first arrives in time. Delays are routine, so that hope is the entire plan."),
            ("Nobody is watching the handover",
             "When a train runs late, no one knows how many people on board are due to board "
             "another train at the next junction. The connection is treated as the passenger's "
             "problem, even when a short hold would have saved it."),
        ],
    )

    # ------------------------------------------------------------- 3 solution
    slide = blank(prs)
    y = heading(slide, "One platform, four capabilities", eyebrow="The solution")
    tf = textbox(slide, MARGIN, y, W - 2 * MARGIN, Inches(0.5))
    write(tf, "Built around a single question: will this journey actually work, end to end?",
          16, MUTED, first=True, space_after=0)

    top = y + Inches(0.72)
    gap = Inches(0.3)
    cw = int(((W - 2 * MARGIN) - gap) / 2)
    ch = Inches(1.75)
    items = [
        ("01", "Confirmation prediction",
         "Enter a PNR and get the probability it confirms, with the factors behind it.", ACCENT),
        ("02", "Connecting route search",
         "Find direct trains, and multi-leg routes where none exists or the direct train is full.", ACCENT),
        ("03", "Missed-connection risk",
         "Score the chance the first train's delay costs you the second one.", ACCENT),
        ("04", "Operations dashboard",
         "Show staff how many passengers are transferring between two trains at a junction.", GOOD),
    ]
    for i, (num, title, detail, colour) in enumerate(items):
        x = MARGIN + (i % 2) * (cw + gap)
        yy = top + (i // 2) * (ch + Inches(0.26))
        card(slide, x, yy, cw, ch)
        tf = textbox(slide, x + Inches(0.34), yy + Inches(0.22), Inches(1), Inches(0.4))
        write(tf, num, 13, colour, bold=True, first=True, space_after=0)
        tf = textbox(slide, x + Inches(0.34), yy + Inches(0.6), cw - Inches(0.68), Inches(1.0))
        write(tf, title, 19, INK, bold=True, first=True, space_after=4)
        write(tf, detail, 13, MUTED, space_after=0)

    tf = textbox(slide, MARGIN, H - Inches(0.8), W - 2 * MARGIN, Inches(0.4))
    write(tf, "The first three serve passengers. The fourth serves the railway — and it is only "
              "possible because the first three already exist.", 12, MUTED, first=True,
          space_after=0, italic=True)

    # --------------------------------------------------- 4 connection anatomy
    slide = blank(prs)
    y = heading(slide, "Where a connecting journey breaks", eyebrow="Capabilities 02 and 03")

    box_w, box_h = Inches(2.7), Inches(1.15)
    row_y = y + Inches(0.5)
    positions = [
        (MARGIN, "Train A", "Leg one", ACCENT),
        (MARGIN + Inches(4.0), "Junction", "Layover window", WARN),
        (MARGIN + Inches(8.0), "Train B", "Leg two", ACCENT),
    ]
    for x, title, sub, colour in positions:
        shape = card(slide, x, row_y, box_w, box_h, WASH)
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, row_y, Pt(4), box_h)
        bar.fill.solid()
        bar.fill.fore_color.rgb = colour
        bar.line.fill.background()
        bar.shadow.inherit = False
        tf = textbox(slide, x + Inches(0.28), row_y + Inches(0.22), box_w - Inches(0.4),
                     Inches(0.8))
        write(tf, title, 18, INK, bold=True, first=True, space_after=2)
        write(tf, sub, 12, MUTED, space_after=0)

    for x in (MARGIN + Inches(2.85), MARGIN + Inches(6.85)):
        arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x, row_y + Inches(0.42),
                                       Inches(1.0), Inches(0.3))
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = PALE
        arrow.line.fill.background()
        arrow.shadow.inherit = False

    risks = [
        (MARGIN, "Risk 1 — leg one never confirms",
         "The confirmation model scores this before the passenger commits to the journey."),
        (MARGIN + Inches(4.0), "Risk 2 — the delay eats the layover",
         "The first train's historical delay behaviour is compared against the time available "
         "at the junction."),
        (MARGIN + Inches(8.0), "Risk 3 — leg two never confirms",
         "Scored independently by the same model, then combined into one journey-level number."),
    ]
    for x, title, detail in risks:
        tf = textbox(slide, x, row_y + Inches(1.55), box_w + Inches(0.5), Inches(2.0))
        write(tf, title, 14, INK, bold=True, first=True, space_after=5)
        write(tf, detail, 13, MUTED, space_after=0)

    tf = textbox(slide, MARGIN, H - Inches(0.85), W - 2 * MARGIN, Inches(0.45))
    write(tf, "The passenger sees one number for the whole journey, not three separate ones "
              "they have to reason about.", 13, INK, first=True, space_after=0)

    # ------------------------------------------------------------- 5 ops view
    slide = blank(prs)
    y = heading(slide, "The view the railway does not currently have",
                eyebrow="Capability 04  ·  operations")
    tf = textbox(slide, MARGIN, y, Inches(6.3), Inches(4.4))
    write(tf, "Once the system knows every passenger's full journey, it knows something the "
              "railway does not:", 16, INK, first=True, space_after=16)
    write(tf, "How many people on a delayed train are about to miss a specific connection, "
              "at a specific junction, right now.", 19, INK, bold=True, space_after=16)
    write(tf, "Today that handover is invisible. Each train is managed on its own schedule, so a "
              "late arrival and a punctual departure are treated as two unrelated events — even "
              "when the same passengers are on both.", 15, MUTED, space_after=0)

    panel_x = MARGIN + Inches(6.8)
    panel_w = W - panel_x - MARGIN
    card(slide, panel_x, y, panel_w, Inches(4.35), INK)
    tf = textbox(slide, panel_x + Inches(0.4), y + Inches(0.35), panel_w - Inches(0.8), Inches(3.7))
    write(tf, "WHAT A CONTROLLER WOULD SEE", 10, ACCENT, bold=True, first=True, space_after=14)
    write(tf, "Train A is running late into this junction.", 15, PAPER, bold=True, space_after=10)
    write(tf, "A number of passengers on board are booked onto Train B, which is scheduled to "
              "depart before Train A now arrives.", 14, PALE, space_after=16)
    write(tf, "So the choice becomes explicit:", 13, ACCENT, bold=True, space_after=8)
    write(tf, "•   Hold Train B briefly and keep them moving", 14, PAPER, space_after=6)
    write(tf, "•   Let it go and arrange for those passengers", 14, PAPER, space_after=6)
    write(tf, "•   Do nothing — but now it is a decision, not an oversight", 14, PAPER, space_after=0)

    tf = textbox(slide, MARGIN, H - Inches(0.8), W - 2 * MARGIN, Inches(0.4))
    write(tf, "A short, informed hold can protect a whole group of journeys. Without this view, "
              "nobody knows the hold was worth making.", 12, MUTED, first=True, space_after=0,
          italic=True)

    # ------------------------------------------------------------ 6 pipeline
    bullets_slide(
        prs, "How it works", eyebrow="End to end",
        bullets=[
            ("Read the ticket",
             "A PNR lookup returns train, class, quota, booking status and current status. One "
             "adapter normalises every provider into a single internal shape."),
            ("Predict confirmation",
             "A machine learning model trained on real waitlisted tickets scores each leg, and "
             "explains which factors moved the number."),
            ("Build and score routes",
             "Direct and multi-leg options between two cities, each scored for confirmation and "
             "for the risk that a delay breaks the connection."),
            ("Aggregate for operations",
             "Passenger journeys sharing an interchange are grouped by junction and train pair, "
             "turning individual risk into a decision staff can act on."),
        ],
    )

    # --------------------------------------------------------------- 7 model
    slide = blank(prs)
    y = heading(slide, "The prediction engine", eyebrow="Under the hood")
    tf = textbox(slide, MARGIN, y, Inches(6.0), Inches(4.3))
    write(tf, "Trained only on verified real data", 18, INK, bold=True, first=True, space_after=6)
    write(tf, "We audited three public datasets and used the one that held up. One was "
              "fabricated — sequential ticket numbers and impossible train and class "
              "combinations — so we discarded it.", 15, MUTED, space_after=16)
    write(tf, "We deleted our own first model too", 18, INK, bold=True, space_after=6)
    write(tf, "It was trained on data we generated ourselves, which meant it could only re-learn "
              "our own assumptions. It would have scored well and known nothing.", 15, MUTED,
          space_after=0)

    tf = textbox(slide, MARGIN + Inches(6.5), y, Inches(5.0), Inches(4.3))
    write(tf, "WHAT THE MODEL READS", 10, ACCENT, bold=True, first=True, space_after=12)
    for label in ["Travel class", "Waitlist position when booked",
                  "Current waitlist position", "Days until the journey"]:
        write(tf, "•   " + label, 16, INK, space_after=10)
    write(tf, "Every input comes straight from the ticket lookup. Nothing is estimated, and "
              "nothing is used in training that the live system cannot actually obtain.",
          14, MUTED, space_after=14)
    write(tf, "Delay behaviour per train and per route feeds the connection risk separately.",
          14, MUTED, space_after=0)

    # ---------------------------------------------------------- 8 architecture
    bullets_slide(
        prs, "Built and deployed", eyebrow="Engineering",
        bullets=[
            ("Backend  ·  Python, FastAPI, scikit-learn",
             "A REST API serving predictions, with an endpoint that publishes the model's own "
             "provenance so its numbers can be verified against the running service."),
            ("Web  ·  HTML, CSS, JavaScript",
             "No build step. Detects whether it is running locally or deployed and selects the "
             "right API automatically."),
            ("Mobile  ·  React Native via Expo",
             "The same journey flow on a phone, pointed at the same deployed API."),
            ("Hosting  ·  Vercel and Render, deployed from GitHub",
             "Live and publicly reachable, with slow cold starts surfaced to the user instead of "
             "leaving a frozen screen."),
        ],
    )

    # -------------------------------------------------------------- 9 impact
    slide = blank(prs)
    y = heading(slide, "Why it matters", eyebrow="Impact")
    gap = Inches(0.3)
    cw = int(((W - 2 * MARGIN) - gap) / 2)
    ch = Inches(2.0)
    blocks = [
        ("For passengers",
         "Decide with a number instead of a guess. Know whether to hold a ticket, whether a "
         "connection is realistic, and how much time to leave at a junction.", ACCENT),
        ("For the railway",
         "See transfers that are currently invisible. Turn a missed connection from something "
         "discovered afterwards into a decision that can be made in time.", GOOD),
    ]
    for i, (title, detail, colour) in enumerate(blocks):
        x = MARGIN + i * (cw + gap)
        card(slide, x, y + Inches(0.2), cw, ch)
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y + Inches(0.2), Pt(4), ch)
        bar.fill.solid()
        bar.fill.fore_color.rgb = colour
        bar.line.fill.background()
        bar.shadow.inherit = False
        tf = textbox(slide, x + Inches(0.36), y + Inches(0.5), cw - Inches(0.72), Inches(1.5))
        write(tf, title, 21, INK, bold=True, first=True, space_after=8)
        write(tf, detail, 15, MUTED, space_after=0)

    tf = textbox(slide, MARGIN, y + Inches(2.6), W - 2 * MARGIN, Inches(1.6))
    write(tf, "The same prediction that helps one passenger decide, aggregated across everyone "
              "on the train, becomes an operational signal for the railway.", 19, INK, bold=True,
          first=True, space_after=10)
    write(tf, "That is why these are one system and not four features — each capability is built "
              "on the one before it.", 15, MUTED, space_after=0)

    # --------------------------------------------------------------- 10 close
    slide = blank(prs, INK)
    tf = textbox(slide, MARGIN, Inches(2.4), Inches(11), Inches(1.0))
    write(tf, "Thank you", 44, PAPER, bold=True, first=True, space_after=0)
    rule(slide, MARGIN, Inches(3.5), Inches(1.6))
    tf = textbox(slide, MARGIN, Inches(3.85), Inches(11.5), Inches(2.2))
    write(tf, "Live demo   irctc-smoky.vercel.app", 17, PAPER, first=True, space_after=10)
    write(tf, "API   pnr-predictor-api.onrender.com", 17, PALE, space_after=10)
    write(tf, "Source   github.com/mohammadamir0762-arch/irctc", 17, PALE, space_after=0)

    prs.save(OUTPUT)
    return len(prs.slides._sldIdLst)


if __name__ == "__main__":
    print(f"Wrote {OUTPUT}\n{build()} slides")
