"""
Generates the project presentation (PS91_Presentation.pptx) in the repo root.

Deliberately short — 16 slides. Every figure comes from analysis/benchmark.py
(the model) or new/EDA_INSIGHTS_REPORT.md (the delay study). No number here is
stated more strongly than its source supports.

Run:  python analysis/make_ppt.py
"""

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
CHARTS = ROOT / "new"
OUTPUT = ROOT / "PS91_Presentation.pptx"

INK = RGBColor(0x0F, 0x17, 0x2A)
MUTED = RGBColor(0x64, 0x74, 0x8B)
PAPER = RGBColor(0xFF, 0xFF, 0xFF)
WASH = RGBColor(0xF1, 0xF5, 0xF9)
ACCENT = RGBColor(0x0E, 0xA5, 0xE9)
GOOD = RGBColor(0x05, 0x96, 0x69)
BAD = RGBColor(0xDC, 0x26, 0x26)
WARN = RGBColor(0xD9, 0x77, 0x06)

FONT = "Arial"
W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.72)


def blank(prs, bg=PAPER):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg
    shape.line.fill.background()
    shape.shadow.inherit = False
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


def stat_row(slide, y, stats, box_h=Inches(1.5)):
    gap = Inches(0.26)
    box_w = int(((W - 2 * MARGIN) - gap * (len(stats) - 1)) / len(stats))
    for i, (value, label, color) in enumerate(stats):
        x = MARGIN + i * (box_w + gap)
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, box_w, box_h)
        card.fill.solid()
        card.fill.fore_color.rgb = WASH
        card.line.fill.background()
        card.shadow.inherit = False
        card.adjustments[0] = 0.06
        tf = textbox(slide, x, y + Inches(0.24), box_w, Inches(0.7), PP_ALIGN.CENTER)
        write(tf, value, 30, color, bold=True, first=True, space_after=0, align=PP_ALIGN.CENTER)
        tf = textbox(slide, x + Inches(0.1), y + Inches(0.95), box_w - Inches(0.2),
                     Inches(0.5), PP_ALIGN.CENTER)
        write(tf, label, 11, MUTED, first=True, space_after=0, align=PP_ALIGN.CENTER)


def bullets_slide(prs, title, bullets, eyebrow=None, footnote=None):
    slide = blank(prs)
    y = heading(slide, title, eyebrow)
    tf = textbox(slide, MARGIN, y, W - 2 * MARGIN, H - y - Inches(0.9))
    for i, item in enumerate(bullets):
        if isinstance(item, tuple):
            label, detail = item
            write(tf, label, 19, INK, bold=True, first=(i == 0), space_after=2)
            write(tf, detail, 15, MUTED, space_after=16)
        else:
            write(tf, "•   " + item, 17, INK, first=(i == 0), space_after=12)
    if footnote:
        tf = textbox(slide, MARGIN, H - Inches(0.82), W - 2 * MARGIN, Inches(0.4))
        write(tf, footnote, 11, MUTED, first=True, space_after=0, italic=True)
    return slide


def table_slide(prs, title, headers, rows, eyebrow=None, widths=None, footnote=None,
                row_colors=None):
    slide = blank(prs)
    y = heading(slide, title, eyebrow)
    table = slide.shapes.add_table(len(rows) + 1, len(headers), MARGIN, y,
                                   W - 2 * MARGIN,
                                   min(Inches(0.5) * (len(rows) + 1),
                                       H - y - Inches(1.0))).table
    if widths:
        total = W - 2 * MARGIN
        for i, frac in enumerate(widths):
            table.columns[i].width = Emu(int(total * frac))

    for c, text in enumerate(headers):
        cell = table.cell(0, c)
        cell.text = text
        cell.fill.solid()
        cell.fill.fore_color.rgb = INK
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        for p in cell.text_frame.paragraphs:
            for run in p.runs:
                run.font.size, run.font.bold = Pt(12), True
                run.font.color.rgb, run.font.name = PAPER, FONT

    for r, row in enumerate(rows, start=1):
        for c, text in enumerate(row):
            cell = table.cell(r, c)
            cell.text = str(text)
            cell.fill.solid()
            cell.fill.fore_color.rgb = PAPER if r % 2 else WASH
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            highlight = row_colors and row_colors.get(r - 1) and c == len(row) - 1
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(12)
                    run.font.color.rgb = row_colors[r - 1] if highlight else INK
                    run.font.bold = bool(highlight)
                    run.font.name = FONT

    if footnote:
        tf = textbox(slide, MARGIN, H - Inches(0.8), W - 2 * MARGIN, Inches(0.4))
        write(tf, footnote, 11, MUTED, first=True, space_after=0, italic=True)
    return slide


def chart_slide(prs, title, image, takeaway, eyebrow=None):
    slide = blank(prs)
    y = heading(slide, title, eyebrow)
    avail_w, avail_h = Inches(7.6), H - y - Inches(0.75)
    iw, ih = Image.open(image).size
    scale = min(avail_w / iw, avail_h / ih)
    w, h = int(iw * scale), int(ih * scale)
    slide.shapes.add_picture(str(image), MARGIN + int((avail_w - w) / 2),
                             y + int((avail_h - h) / 2), w, h)
    tx = MARGIN + avail_w + Inches(0.4)
    tf = textbox(slide, tx, y + Inches(0.1), W - tx - MARGIN, avail_h)
    write(tf, "WHY IT MATTERS", 10, ACCENT, bold=True, first=True, space_after=8)
    for i, line in enumerate(takeaway):
        write(tf, line, 14, INK if i == 0 else MUTED, bold=(i == 0), space_after=10)


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # 1 — title
    slide = blank(prs, INK)
    tf = textbox(slide, MARGIN, Inches(2.1), W - 2 * MARGIN, Inches(0.4))
    write(tf, "PROBLEM STATEMENT PS91", 13, ACCENT, bold=True, first=True, space_after=0)
    tf = textbox(slide, MARGIN, Inches(2.68), Inches(10.6), Inches(2.0))
    write(tf, "Will your train", 50, PAPER, bold=True, first=True, space_after=2)
    write(tf, "ticket actually work?", 50, PAPER, bold=True, space_after=0)
    tf = textbox(slide, MARGIN, Inches(4.75), Inches(9.6), Inches(0.9))
    write(tf, "Confirmation probability for waitlisted tickets, plus connecting-journey",
          17, RGBColor(0xCB, 0xD5, 0xE1), first=True, space_after=2)
    write(tf, "planning with the risk of missing your next train.",
          17, RGBColor(0xCB, 0xD5, 0xE1), space_after=0)
    rule(slide, MARGIN, Inches(5.95), Inches(2.2))
    tf = textbox(slide, MARGIN, Inches(6.2), Inches(11), Inches(0.6))
    write(tf, "irctc-smoky.vercel.app", 13, PAPER, first=True, space_after=3)
    write(tf, "github.com/mohammadamir0762-arch/irctc", 13, MUTED, space_after=0)

    # 2 — problem
    bullets_slide(
        prs, "Two questions nobody answers", eyebrow="The problem",
        bullets=[
            ("\"Will my waitlisted ticket confirm?\"",
             "A ticket says WL 23. Nothing tells you whether it will clear, so passengers hold "
             "tickets they cannot use, or cancel ones that would have confirmed."),
            ("\"Will I make my connection?\"",
             "Many city pairs have no direct train. You book two tickets and hope the first "
             "arrives in time. Indian trains are routinely late, so that hope is the whole plan."),
            ("Both are probability questions treated as guesswork",
             "The data to answer them exists — waitlist movement, quota, historical delays. "
             "It is simply never turned into a number for the passenger."),
        ],
    )

    # 3 — what it does
    slide = blank(prs)
    y = heading(slide, "What the system does", eyebrow="Solution")
    tf = textbox(slide, MARGIN, y, W - 2 * MARGIN, Inches(2.9))
    write(tf, "1.   Confirmation probability", 19, INK, bold=True, first=True, space_after=2)
    write(tf, "Enter a PNR. Get the chance it confirms, and the factors driving that number.",
          15, MUTED, space_after=16)
    write(tf, "2.   Direct and connecting routes", 19, INK, bold=True, space_after=2)
    write(tf, "Search city to city. See direct trains, and multi-leg options where no direct "
              "train exists or the direct one is full.", 15, MUTED, space_after=16)
    write(tf, "3.   Missed-connection risk", 19, INK, bold=True, space_after=2)
    write(tf, "For each connecting option, the chance the first train's delay causes you to "
              "miss the second.", 15, MUTED, space_after=0)
    stat_row(slide, y + Inches(3.05), [
        ("28,748", "REAL TICKETS TRAINED ON", INK),
        ("0.796", "MODEL AUC", ACCENT),
        ("66%", "OF ACHIEVABLE SIGNAL", INK),
        ("Live", "WEB + API DEPLOYED", GOOD),
    ])

    # 4 — how it works
    bullets_slide(
        prs, "How it works", eyebrow="Pipeline",
        bullets=[
            ("Look up the PNR",
             "A third-party IRCTC API returns train, class, quota, booking status and current status."),
            ("Normalise every provider into one shape",
             "Providers disagree on field names and status formats. One adapter handles it, so "
             "swapping providers changes nothing downstream."),
            ("Predict confirmation",
             "Gradient boosting model over travel class, booking position, current position and "
             "days remaining — all read directly from the lookup, nothing estimated."),
            ("Score the connection",
             "For multi-leg journeys, combine each leg's confirmation probability with the "
             "historical delay distribution of the first train against the layover time."),
        ],
    )

    # 5 — data
    table_slide(
        prs, "We only trained on data we verified", eyebrow="Real data",
        headers=["Dataset", "Rows", "Finding", "Verdict"],
        widths=[0.25, 0.11, 0.46, 0.18],
        rows=[
            ["Railway Waitinglist", "53,381",
             "Real. Confirmation falls cleanly with waitlist position, class mix matches reality.",
             "USED"],
            ["Railway Ticket Confirmation", "30,000",
             "Fabricated. Sequential PNRs, Shatabdi trains with sleeper class, label was a tautology.",
             "REJECTED"],
            ["Railofy (competition)", "36,775",
             "Real and richer, but values are encoded and cannot accept a live PNR.",
             "BENCHMARK"],
        ],
        row_colors={0: GOOD, 1: BAD, 2: WARN},
        footnote="Our first model was trained on data we generated ourselves. We deleted it — the "
                 "labels came from our own formula, so it could only re-learn our assumptions.",
    )

    # 6 — model
    slide = blank(prs)
    y = heading(slide, "The model", eyebrow="Approach")
    tf = textbox(slide, MARGIN, y, Inches(5.9), Inches(4.3))
    write(tf, "Algorithm", 13, ACCENT, bold=True, first=True, space_after=4)
    write(tf, "Histogram gradient boosting classifier", 16, INK, space_after=16)
    write(tf, "Trained on", 13, ACCENT, bold=True, space_after=4)
    write(tf, "28,748 real waitlisted tickets", 16, INK, space_after=4)
    write(tf, "Observed at 30, 7 and 2 days before travel — matching what the app knows at "
              "prediction time.", 13, MUTED, space_after=16)
    write(tf, "Validation", 13, ACCENT, bold=True, space_after=4)
    write(tf, "Grouped train/test split", 16, INK, space_after=4)
    write(tf, "One ticket never appears on both sides, so the score is not inflated by leakage.",
          13, MUTED, space_after=0)
    tf = textbox(slide, MARGIN + Inches(6.4), y, Inches(5.1), Inches(4.3))
    write(tf, "INPUTS", 13, ACCENT, bold=True, first=True, space_after=10)
    for label in ["Travel class", "Waitlist position when booked",
                  "Current waitlist position", "Days until journey"]:
        write(tf, "•   " + label, 16, INK, space_after=10)
    write(tf, "Each read straight from the PNR lookup. Nothing used in training that the live "
              "system cannot obtain.", 13, MUTED, space_after=0)

    # 7 — evidence
    table_slide(
        prs, "These are the determining factors", eyebrow="Measured on real tickets",
        headers=["Factor", "Measured effect", "Spread"],
        widths=[0.28, 0.52, 0.20],
        rows=[
            ["Waitlist position", "12.9% confirm at WL 1–5, down to 0.2% at WL 60+", "65×"],
            ["Days until journey", "6.6% at 30 days, 12.9% at 7 days, 15.1% at 2 days", "2.3×"],
            ["Travel class", "2A 5.2%, 3A 8.6%, SL 12.5%, CC 33.6%", "6.5×"],
        ],
        footnote="Across all 23 features in the benchmark dataset, current waitlist position "
                 "ranks first by more than double the next feature.",
    )

    # 8 — benchmark
    slide = blank(prs)
    y = heading(slide, "Results", eyebrow="Benchmarked against a 23-feature ceiling")
    stat_row(slide, y + Inches(0.25), [
        ("0.500", "RANDOM BASELINE", MUTED),
        ("0.796", "OUR MODEL  ·  4 INPUTS  ·  LIVE", ACCENT),
        ("0.945", "CEILING  ·  23 FEATURES", INK),
    ], box_h=Inches(1.7))
    tf = textbox(slide, MARGIN, y + Inches(2.25), W - 2 * MARGIN, Inches(2.2))
    write(tf, "We reach 66% of the achievable signal above random, using 4 inputs instead of 23.",
          21, INK, bold=True, first=True, space_after=14)
    write(tf, "The 23-feature dataset encodes waitlist position as a fraction of a denominator it "
              "does not publish, so it cannot accept a real PNR. We tested a statistical workaround "
              "and it scored 0.480 — worse than a coin flip. It stays a benchmark, and we ship the "
              "model that actually reads live data.", 15, MUTED, space_after=0)
    tf = textbox(slide, MARGIN, H - Inches(0.8), W - 2 * MARGIN, Inches(0.4))
    write(tf, "Every figure reproducible with  python analysis/benchmark.py", 11, MUTED,
          first=True, space_after=0, italic=True)

    # 9 — connection risk section
    slide = blank(prs, INK)
    tf = textbox(slide, MARGIN, Inches(2.5), Inches(2), Inches(1.2))
    write(tf, "02", 64, RGBColor(0x1E, 0x29, 0x3B), bold=True, first=True, space_after=0)
    rule(slide, MARGIN, Inches(3.35), Inches(1.6))
    tf = textbox(slide, MARGIN, Inches(3.5), Inches(10.5), Inches(1.6))
    write(tf, "Connecting journeys", 40, PAPER, bold=True, first=True, space_after=6)
    write(tf, "Using historical delay data to score the risk of missing your next train",
          16, RGBColor(0x94, 0xA3, 0xB8), space_after=0)

    # 10 — the method
    slide = blank(prs)
    y = heading(slide, "Scoring a connection", eyebrow="Method")
    tf = textbox(slide, MARGIN, y, Inches(6.0), Inches(4.4))
    write(tf, "A two-leg journey has three ways to fail", 17, INK, bold=True, first=True,
          space_after=12)
    write(tf, "1.   Leg one does not confirm", 15, INK, bold=True, space_after=2)
    write(tf, "Handled by the confirmation model.", 14, MUTED, space_after=12)
    write(tf, "2.   Leg two does not confirm", 15, INK, bold=True, space_after=2)
    write(tf, "Same model, scored independently.", 14, MUTED, space_after=12)
    write(tf, "3.   Leg one arrives too late for leg two", 15, INK, bold=True, space_after=2)
    write(tf, "Compare the first train's historical delay distribution against the layover "
              "time at the interchange station.", 14, MUTED, space_after=0)

    tf = textbox(slide, MARGIN + Inches(6.5), y, Inches(5.0), Inches(4.4))
    write(tf, "WHAT THE DELAY DATA GIVES US", 10, ACCENT, bold=True, first=True, space_after=12)
    write(tf, "Median delay   25 min", 17, INK, bold=True, space_after=4)
    write(tf, "Half of journeys arrive within this.", 13, MUTED, space_after=12)
    write(tf, "27% of journeys delayed 50 min or more", 17, INK, bold=True, space_after=4)
    write(tf, "So a 50-minute layover fails roughly one time in four.", 13, MUTED, space_after=12)
    write(tf, "Longest observed   244 min", 17, INK, bold=True, space_after=4)
    write(tf, "No realistic buffer survives the tail — which is exactly why it should be shown "
              "as a probability, not hidden.", 13, MUTED, space_after=0)
    tf = textbox(slide, MARGIN, H - Inches(0.8), W - 2 * MARGIN, Inches(0.4))
    write(tf, "Delay figures from an exploratory study of 100 journey records, 2016–2025.",
          11, MUTED, first=True, space_after=0, italic=True)

    # 11-14 — the four charts that feed connection risk
    for title, filename, takeaway in [
        ("How late do trains actually run?", "01_delay_distribution.png",
         ["This curve is the buffer calculator.",
          "Most journeys are under 50 minutes late, but a long tail reaches 244 minutes.",
          "For any layover, the area to the right of it is the probability of missing "
          "the connection."]),
        ("Baseline risk", "04_ontime_performance.png",
         ["Arriving on time is the exception.",
          "94 of 100 journeys in the sample were late.",
          "A connection planned on the scheduled time is planning for the rare case."]),
        ("Some trains are far riskier to connect from", "09_train_boxplot.png",
         ["Consistency matters more than the average.",
          "A train that is reliably 20 minutes late is safe to plan around. One that swings "
          "between on-time and two hours late is not.",
          "Spread, not the mean, is what should drive the warning."]),
        ("The corridor matters more than the distance", "10_routes_comparison.png",
         ["Route identity is the strongest signal we found.",
          "Dibrugarh–Kanyakumari covers 4,198 km at 20.4 min average, beating far shorter routes.",
          "So risk has to be scored per route, not estimated from journey length."]),
    ]:
        path = CHARTS / filename
        if path.exists():
            chart_slide(prs, title, path, takeaway, eyebrow="Delay analysis")

    # 15 — architecture
    bullets_slide(
        prs, "Architecture", eyebrow="Engineering",
        bullets=[
            ("Backend  ·  Python, FastAPI, scikit-learn",
             "Six endpoints. /model publishes the model's own provenance and scores, so the "
             "numbers on these slides can be checked against the running service."),
            ("Frontend  ·  HTML, CSS, JavaScript",
             "No build step. Detects local versus deployed and selects the right API automatically."),
            ("Mobile  ·  React Native via Expo",
             "Same flow as the web app, pointed at the same deployed API."),
            ("Hosting  ·  Vercel and Render",
             "Deployed straight from GitHub, with cold starts handled explicitly rather than "
             "leaving a frozen screen."),
        ],
    )

    # 16 — close
    slide = blank(prs, INK)
    tf = textbox(slide, MARGIN, Inches(2.4), Inches(11), Inches(1.0))
    write(tf, "Thank you", 44, PAPER, bold=True, first=True, space_after=0)
    rule(slide, MARGIN, Inches(3.5), Inches(1.6))
    tf = textbox(slide, MARGIN, Inches(3.85), Inches(11.5), Inches(2.2))
    write(tf, "Live demo   irctc-smoky.vercel.app", 17, PAPER, first=True, space_after=10)
    write(tf, "API   pnr-predictor-api.onrender.com", 17, RGBColor(0xCB, 0xD5, 0xE1), space_after=10)
    write(tf, "Source   github.com/mohammadamir0762-arch/irctc", 17, RGBColor(0xCB, 0xD5, 0xE1),
          space_after=0)

    prs.save(OUTPUT)
    return len(prs.slides._sldIdLst)


if __name__ == "__main__":
    print(f"Wrote {OUTPUT}\n{build()} slides")
