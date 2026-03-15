from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable,
                                 PageBreak, KeepTogether)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import os
import re

def generate_pdf_report(game_data, analysis_result, output_dir="reports"):
    os.makedirs(output_dir, exist_ok=True)

    t1 = game_data['team1'].replace(" ", "_")
    t2 = game_data['team2'].replace(" ", "_")
    date_str = (game_data['game_date']
                .replace("/", "-")
                .replace(" ", "_")
                .replace(",", ""))
    filename = f"{output_dir}/{t1}_vs_{t2}_{date_str}.pdf"

    doc = SimpleDocTemplate(
        filename, pagesize=letter,
        rightMargin=0.55*inch, leftMargin=0.55*inch,
        topMargin=0.55*inch, bottomMargin=0.55*inch
    )

    # ── COLORS ──
    NAVY   = colors.HexColor("#0D2240")
    GOLD   = colors.HexColor("#C8A951")
    GREEN  = colors.HexColor("#1A7A3E")
    RED    = colors.HexColor("#CC0000")
    ORANGE = colors.HexColor("#E07000")
    LGRAY  = colors.HexColor("#F5F5F5")
    MGRAY  = colors.HexColor("#888888")
    DGRAY  = colors.HexColor("#333333")
    LGREEN = colors.HexColor("#E8F8E8")
    LRED   = colors.HexColor("#FFE0E0")
    YELLOW = colors.HexColor("#FFFBE6")
    LBLUE  = colors.HexColor("#D6E4F0")

    # ── STYLES ──
    def PS(name, **kw):
        s = ParagraphStyle(name)
        d = dict(fontSize=9.5, fontName="Helvetica",
                 textColor=DGRAY, spaceAfter=4, leading=14)
        d.update(kw)
        for k, v in d.items():
            setattr(s, k, v)
        return s

    title_s   = PS("TI", fontSize=20, fontName="Helvetica-Bold",
                   textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)
    game_s    = PS("GA", fontSize=14, fontName="Helvetica-Bold",
                   textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)
    meta_s    = PS("ME", fontSize=9, textColor=MGRAY,
                   alignment=TA_CENTER, spaceAfter=4)
    section_s = PS("SE", fontSize=11, fontName="Helvetica-Bold",
                   textColor=colors.white, backColor=NAVY,
                   spaceAfter=6, spaceBefore=10, leading=18,
                   borderPad=5)
    sub_s     = PS("SU", fontSize=10, fontName="Helvetica-Bold",
                   textColor=NAVY, spaceAfter=3, spaceBefore=6)
    body_s    = PS("BO", fontSize=8.5, leading=13, spaceAfter=3)
    flag_r_s  = PS("FR", fontSize=9, fontName="Helvetica-Bold",
                   textColor=colors.white, backColor=RED,
                   borderPad=5, spaceAfter=4, leading=14)
    flag_o_s  = PS("FO", fontSize=9, fontName="Helvetica-Bold",
                   textColor=colors.white, backColor=ORANGE,
                   borderPad=5, spaceAfter=4, leading=14)
    flag_b_s  = PS("FB", fontSize=9, fontName="Helvetica-Bold",
                   textColor=colors.white,
                   backColor=colors.HexColor("#1A4A7A"),
                   borderPad=5, spaceAfter=4, leading=14)
    best_s    = PS("BE", fontSize=14, fontName="Helvetica-Bold",
                   textColor=colors.white, backColor=GREEN,
                   alignment=TA_CENTER, spaceAfter=6,
                   spaceBefore=6, leading=22, borderPad=10)
    pass_s    = PS("PA", fontSize=12, fontName="Helvetica-Bold",
                   textColor=DGRAY,
                   backColor=colors.HexColor("#FFEEAA"),
                   alignment=TA_CENTER, spaceAfter=4,
                   spaceBefore=4, leading=18, borderPad=6)
    score_s   = PS("SC", fontSize=12, fontName="Helvetica-Bold",
                   textColor=NAVY, alignment=TA_CENTER,
                   backColor=LGRAY, borderPad=6, spaceAfter=8)

    def safe(text):
        return (str(text or "—")
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>','&gt;'))

    def hr(thickness=0.5, space_after=6):
        return HRFlowable(width="100%", thickness=thickness,
                          color=MGRAY, spaceAfter=space_after)

    def sp(h=8):
        return Spacer(1, h)

    def make_table(data, widths, extra_styles=None):
        t = Table(data, colWidths=widths)
        base = [
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8.5),
            ('BACKGROUND', (0,0), (-1,0), NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.3, MGRAY),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ('ROWBACKGROUNDS', (0,1), (-1,-1),
             [colors.white, LGRAY]),
        ]
        if extra_styles:
            base += extra_styles
        t.setStyle(TableStyle(base))
        return t

    picks = analysis_result.get("picks", {})
    full_text = analysis_result.get("full_analysis", "")
    usage = analysis_result.get("usage", {})

    # Remove PICKS block from display text
    display_text = re.sub(
        r'<PICKS>.*?</PICKS>', '',
        full_text, flags=re.DOTALL
    ).strip()

    story = []

    # ══════════════════════════════════════════
    # PAGE 1 — PICKS DASHBOARD
    # ══════════════════════════════════════════

    # Header
    story.append(Paragraph(
        "PROFESSIONAL SPORTS BETTING ANALYSIS", title_s))
    story.append(Paragraph(
        f"{game_data['team1'].upper()} "
        f"vs {game_data['team2'].upper()}", game_s))
    story.append(Paragraph(
        f"{game_data['sport']}  |  "
        f"{game_data['game_date']}  |  "
        f"{game_data['context']}", meta_s))
    story.append(Paragraph(
        f"Generated: "
        f"{datetime.now().strftime('%B %d, %Y  %I:%M %p')}",
        meta_s))
    story.append(hr(thickness=2, space_after=12))

    # ── VERSION BADGE ──
    story.append(make_table(
        [["32-RULE MODEL v7",
          "RULES 1-32 APPLIED",
          "POST-MORTEM CORRECTED"]],
        [2.4*inch, 2.4*inch, 2.4*inch],
        [('BACKGROUND', (0,0), (-1,-1), NAVY),
         ('TEXTCOLOR', (0,0), (-1,-1), GOLD),
         ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
         ('FONTSIZE', (0,0), (-1,-1), 8),
         ('ALIGN', (0,0), (-1,-1), 'CENTER')]
    ))
    story.append(sp(10))

    # ── ACTIVE RULE FLAGS ──
    parse_failed = picks.get("parse_failed", False)
    if parse_failed:
        story.append(Paragraph(
            "⚠  PICKS SUMMARY — Auto-extracted from analysis text "
            "(JSON parse recovered). See full analysis for details.",
            PS("WA", fontSize=9, fontName="Helvetica-Bold",
               textColor=DGRAY,
               backColor=colors.HexColor("#FFF3CD"),
               borderPad=5, spaceAfter=6, leading=14)))

    if picks.get("rule20_active"):
        story.append(Paragraph(
            "⚑  RULE 20 — SHARP FADE IN EFFECT: "
            "Spread confidence reduced -7%. "
            "Structural credits priced in. Do not bet the favorite.",
            flag_r_s))

    if picks.get("rule31_active"):
        story.append(Paragraph(
            "⚑  RULE 31 — STAR ABSORPTION CEILING ACTIVE: "
            "Primary scorer absent. "
            "Absorbing player ceiling modeled. "
            "Total PASS unless base case is 10+ pts below line.",
            flag_o_s))

    try:
        gap = float(str(
            picks.get("rule32_gap", 0)
        ).replace("—", "0") or 0)
    except (ValueError, TypeError):
        gap = 0

    if gap >= 2:
        story.append(Paragraph(
            f"▲  RULE 32 — LINE EXCEEDS MODEL BY {gap} PTS  |  "
            f"Underdog cover probability: "
            f"{picks.get('rule32_underdog_prob','—')}%  |  "
            f"Recommendation: "
            f"{picks.get('rule32_recommendation','—')}",
            flag_b_s))

    story.append(sp(6))

    # ── PICKS SUMMARY TABLE ──
    story.append(Paragraph(
        "  PICKS SUMMARY", section_s))
    story.append(sp(4))

    def pick_bg(rec):
        r = str(rec or "").upper()
        if "PASS" in r:     return YELLOW
        if "BET" in r:      return LGREEN
        if "COVER" in r:    return LGREEN
        if "LEAN" in r:     return LBLUE
        return LGRAY

    sc = picks.get("spread_confidence", "—")
    tc = picks.get("total_confidence", "—")
    bc = picks.get("best_bet_confidence", "—")
    sr = picks.get("spread_recommendation", "—")
    tr = picks.get("total_recommendation", "—")

    picks_data = [
        ["MARKET", "PICK", "LINE", "CONFIDENCE", "RECOMMENDATION"],
        ["SPREAD",
         safe(picks.get("spread_pick", "—")),
         safe(picks.get("spread_line", "—")),
         f"{sc}%" if isinstance(sc, int) else str(sc),
         safe(sr)],
        ["TOTAL",
         safe(picks.get("total_pick", "—")),
         safe(str(picks.get("total_line", "—"))),
         f"{tc}%" if isinstance(tc, int) else str(tc),
         safe(tr)],
        ["BEST BET",
         safe(str(picks.get("best_bet", "—"))[:45]),
         "—",
         f"{bc}%" if isinstance(bc, int) else str(bc),
         "★ BEST BET"],
    ]

    extra = [
        ('BACKGROUND', (0,1), (-1,1), pick_bg(sr)),
        ('BACKGROUND', (0,2), (-1,2), pick_bg(tr)),
        ('BACKGROUND', (0,3), (-1,3), LGREEN),
        ('FONTNAME', (0,3), (-1,3), 'Helvetica-Bold'),
    ]
    story.append(make_table(
        picks_data,
        [1.0*inch, 1.8*inch, 0.9*inch, 1.1*inch, 1.8*inch],
        extra
    ))
    story.append(sp(10))

    # ── BEST BET HIGHLIGHT ──
    best_bet = picks.get("best_bet", "")
    best_conf = picks.get("best_bet_confidence", 0)

    if best_bet and str(best_bet).upper() != "PASS" and best_bet != "—":
        story.append(Paragraph(
            f"★  BEST BET:  {safe(best_bet)}  "
            f"({best_conf}% Confidence)",
            best_s))
    else:
        story.append(Paragraph(
            "BEST BET:  PASS — No play meets confidence threshold",
            pass_s))

    story.append(sp(6))

    # ── PREDICTED SCORE ──
    predicted = picks.get("predicted_score", "")
    if predicted and predicted != "See analysis":
        story.append(Paragraph(
            f"PREDICTED SCORE:  {safe(predicted)}", score_s))

    story.append(sp(6))
    story.append(hr(thickness=1, space_after=8))

    # ── BETTING LINES USED ──
    story.append(Paragraph(
        "  LINES USED IN THIS ANALYSIS", section_s))
    story.append(sp(4))
    for line in game_data.get(
            "betting_lines", "").split('\n'):
        if line.strip():
            story.append(Paragraph(safe(line), body_s))
    story.append(sp(8))

    # ══════════════════════════════════════════
    # PAGE 2+ — FULL ANALYSIS
    # ══════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph(
        "  FULL 32-RULE ANALYSIS", section_s))
    story.append(sp(8))

    # Parse and render the analysis text intelligently
    current_section = []

    for line in display_text.split('\n'):
        stripped = line.strip()

        if not stripped:
            if current_section:
                story.extend(current_section)
                current_section = []
            story.append(sp(4))
            continue

        # Section dividers
        if stripped.startswith('═') or stripped.startswith('─'):
            story.append(hr(thickness=0.3, space_after=2))
            continue

        # Step headers
        if (re.match(r'^STEP\s+\d+', stripped, re.IGNORECASE) or
                re.match(r'^SECTION\s+\d+', stripped, re.IGNORECASE)):
            story.append(sp(4))
            story.append(Paragraph(
                f"  {safe(stripped)}", section_s))
            story.append(sp(4))
            continue

        # Subsection headers (ALL CAPS lines > 10 chars)
        if (stripped.isupper() and len(stripped) > 10 and
                not stripped.startswith('[')):
            story.append(Paragraph(safe(stripped), sub_s))
            continue

        # Rule flags
        if (stripped.startswith('⚑') or
                stripped.startswith('✓') or
                stripped.startswith('▲')):
            story.append(Paragraph(safe(stripped),
                PS(f"FL{stripped[:5]}",
                   fontSize=9, fontName="Helvetica-Bold",
                   textColor=RED, leading=13, spaceAfter=3)))
            continue

        # Checklist items
        if stripped.startswith('[ ]') or stripped.startswith('[x]'):
            story.append(Paragraph(
                safe(stripped),
                PS(f"CL{stripped[:8]}",
                   fontSize=8.5, leading=13,
                   leftIndent=12, spaceAfter=2)))
            continue

        # Table-like rows with | separators
        if stripped.count('|') >= 2:
            story.append(Paragraph(
                safe(stripped),
                PS(f"TB{stripped[:5]}",
                   fontSize=8, fontName="Courier",
                   leading=12, spaceAfter=2)))
            continue

        # Bold lines starting with a number and dash
        if re.match(r'^\d+\.', stripped):
            story.append(Paragraph(
                safe(stripped),
                PS(f"NL{stripped[:5]}",
                   fontSize=8.5, fontName="Helvetica-Bold",
                   leading=13, spaceAfter=3)))
            continue

        # Regular body text
        story.append(Paragraph(safe(stripped), body_s))

    # ── FOOTER ──
    story.append(sp(20))
    story.append(hr(space_after=4))
    story.append(Paragraph(
        f"32-Rule Model v7  |  "
        f"Generated {datetime.now().strftime('%B %d, %Y')}  |  "
        f"Input tokens: {usage.get('input_tokens','—')}  |  "
        f"Output tokens: {usage.get('output_tokens','—')}",
        PS("FT", fontSize=7, textColor=MGRAY,
           alignment=TA_CENTER)))
    story.append(Paragraph(
        "FOR ENTERTAINMENT AND INFORMATIONAL PURPOSES ONLY.  "
        "Gambling involves risk.  "
        "Problem Gambling Helpline: 1-800-GAMBLER.",
        PS("DS", fontSize=7, textColor=RED,
           alignment=TA_CENTER)))

    doc.build(story)
    print(f"PDF saved: {filename}")
    return filename
