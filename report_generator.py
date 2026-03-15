from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
import os

def generate_pdf_report(game_data, analysis_result, output_dir="reports"):
    """Generate the full PDF report"""
    os.makedirs(output_dir, exist_ok=True)

    t1 = game_data['team1'].replace(" ", "_")
    t2 = game_data['team2'].replace(" ", "_")
    date_str = game_data['game_date'].replace("/","-").replace(" ","_")
    filename = f"{output_dir}/{t1}_vs_{t2}_{date_str}.pdf"

    doc = SimpleDocTemplate(
        filename, pagesize=letter,
        rightMargin=0.6*inch, leftMargin=0.6*inch,
        topMargin=0.6*inch, bottomMargin=0.6*inch
    )

    NAVY  = colors.HexColor("#0D2240")
    GOLD  = colors.HexColor("#C8A951")
    GREEN = colors.HexColor("#1A7A3E")
    RED   = colors.HexColor("#CC0000")
    LGRAY = colors.HexColor("#F5F5F5")
    MGRAY = colors.HexColor("#888888")
    DGRAY = colors.HexColor("#333333")
    LGREEN= colors.HexColor("#E8F8E8")
    LRED  = colors.HexColor("#FFE0E0")
    YELLOW= colors.HexColor("#FFFBE6")
    LBLUE = colors.HexColor("#D6E4F0")
    ORANGE= colors.HexColor("#E07000")

    def PS(name, **kw):
        s = ParagraphStyle(name)
        d = dict(fontSize=9.5, fontName="Helvetica",
                 textColor=DGRAY, spaceAfter=4, leading=14)
        d.update(kw)
        for k,v in d.items(): setattr(s,k,v)
        return s

    def safe(text):
        return (str(text)
                .replace('&','&amp;')
                .replace('<','&lt;')
                .replace('>','&gt;'))

    story = []
    picks = analysis_result.get("picks", {})
    full_text = analysis_result.get("full_analysis", "")

    # ── HEADER ──
    story.append(Paragraph(
        "PROFESSIONAL SPORTS BETTING ANALYSIS",
        PS("H", fontSize=20, fontName="Helvetica-Bold",
           textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph(
        f"{game_data['team1'].upper()} vs {game_data['team2'].upper()}",
        PS("T", fontSize=16, fontName="Helvetica-Bold",
           textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph(
        f"{game_data['sport']} | {game_data['game_date']} | {game_data['context']}",
        PS("ST", fontSize=10, textColor=MGRAY,
           alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}",
        PS("DT", fontSize=9, textColor=MGRAY,
           alignment=TA_CENTER, spaceAfter=10)))
    story.append(HRFlowable(width="100%", thickness=1,
                            color=NAVY, spaceAfter=10))

    # ── PICKS SUMMARY ──
    story.append(Paragraph(
        "PICKS SUMMARY",
        PS("PSH", fontSize=12, fontName="Helvetica-Bold",
           textColor=colors.white, backColor=NAVY,
           alignment=TA_CENTER, borderPad=5,
           spaceAfter=6, leading=18)))

    def pick_bg(rec):
        rec = str(rec or "").upper()
        if "PASS" in rec:    return YELLOW
        if "BET" in rec:     return LGREEN
        if "COVER" in rec:   return LGREEN
        if "LEAN" in rec:    return LBLUE
        return LGRAY

    sc = picks.get("spread_confidence","—")
    tc = picks.get("total_confidence","—")
    bc = picks.get("best_bet_confidence","—")

    pd_data = [
        ["MARKET","PICK","LINE","CONFIDENCE","RECOMMENDATION"],
        ["SPREAD",
         safe(picks.get("spread_pick","—")),
         safe(picks.get("spread_line","—")),
         f"{sc}%" if isinstance(sc,int) else "—",
         safe(picks.get("spread_recommendation","—"))],
        ["TOTAL",
         safe(picks.get("total_pick","—")),
         safe(picks.get("total_line","—")),
         f"{tc}%" if isinstance(tc,int) else "—",
         safe(picks.get("total_recommendation","—"))],
        ["BEST BET",
         safe(str(picks.get("best_bet","—"))[:45]),
         "—",
         f"{bc}%" if isinstance(bc,int) else "—",
         "★ BEST BET"],
    ]
    pt = Table(pd_data,
               colWidths=[1.0*inch,1.8*inch,0.8*inch,1.1*inch,1.8*inch])
    pt.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('BACKGROUND',(0,0),(-1,0),NAVY),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,MGRAY),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),5),
        ('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),5),
        ('BACKGROUND',(0,1),(-1,1),
         pick_bg(picks.get("spread_recommendation",""))),
        ('BACKGROUND',(0,2),(-1,2),
         pick_bg(picks.get("total_recommendation",""))),
        ('BACKGROUND',(0,3),(-1,3),LGREEN),
        ('FONTNAME',(0,3),(-1,3),'Helvetica-Bold'),
    ]))
    story.append(pt)
    story.append(Spacer(1,10))

    # ── ACTIVE RULE FLAGS ──
    if picks.get("rule20_active"):
        story.append(Paragraph(
            "⚑  RULE 20 — SHARP FADE ACTIVE: Spread confidence reduced -7%. "
            "Structural credits already priced. Do not bet the favorite.",
            PS("R20",fontSize=9,fontName="Helvetica-Bold",
               textColor=colors.white,backColor=RED,
               borderPad=5,spaceAfter=4,leading=14)))

    if picks.get("rule31_active"):
        story.append(Paragraph(
            "⚑  RULE 31 — STAR ABSORPTION CEILING ACTIVE: Primary scorer absent. "
            "Absorbing player ceiling modeled. Total PASS unless base case "
            "is 10+ pts below line.",
            PS("R31",fontSize=9,fontName="Helvetica-Bold",
               textColor=colors.white,backColor=ORANGE,
               borderPad=5,spaceAfter=4,leading=14)))

    r32_gap = picks.get("rule32_gap", 0)
    try:
        gap_val = float(str(r32_gap).replace("—","0") or 0)
    except (ValueError, TypeError):
        gap_val = 0

    if gap_val >= 2:
        r32_text = (
            f"▲  RULE 32 — LINE EXCEEDS MODEL BY {r32_gap} PTS | "
            f"Underdog cover probability: {picks.get('rule32_underdog_prob','—')}% | "
            f"Recommendation: {picks.get('rule32_recommendation','—')}"
        )
        story.append(Paragraph(
            r32_text,
            PS("R32",fontSize=9,fontName="Helvetica-Bold",
               textColor=colors.white,backColor=colors.HexColor("#1A4A7A"),
               borderPad=5,spaceAfter=4,leading=14)))

    # ── PREDICTED SCORE ──
    predicted = picks.get("predicted_score","")
    if predicted:
        story.append(Paragraph(
            f"PREDICTED SCORE: {safe(predicted)}",
            PS("SC",fontSize=11,fontName="Helvetica-Bold",
               textColor=NAVY,alignment=TA_CENTER,
               backColor=LGRAY,borderPad=6,spaceAfter=8)))

    story.append(HRFlowable(width="100%",thickness=0.5,
                            color=MGRAY,spaceAfter=8))

    # ── FULL ANALYSIS TEXT ──
    story.append(Paragraph(
        "FULL ANALYSIS",
        PS("FA",fontSize=12,fontName="Helvetica-Bold",
           textColor=colors.white,backColor=NAVY,
           alignment=TA_CENTER,borderPad=5,
           spaceAfter=8,leading=18)))

    body_s = PS("BODY",fontSize=8.5,leading=13,spaceAfter=3)
    bold_s = PS("BOLD",fontSize=8.5,fontName="Helvetica-Bold",
                textColor=NAVY,leading=13,spaceAfter=3)
    flag_s = PS("FLAG",fontSize=8.5,fontName="Helvetica-Bold",
                textColor=RED,leading=13,spaceAfter=3)

    # Remove the PICKS JSON block from display
    display_text = full_text
    try:
        import re
        display_text = re.sub(
            r'<PICKS>.*?</PICKS>', '', full_text, flags=re.DOTALL).strip()
    except Exception:
        pass

    for line in display_text.split('\n'):
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1,4))
            continue
        if stripped.startswith('═') or stripped.startswith('─'):
            story.append(HRFlowable(width="100%",thickness=0.3,
                                    color=MGRAY,spaceAfter=2))
        elif (stripped.startswith('STEP ') or
              stripped.startswith('SECTION ') or
              stripped.isupper() and len(stripped) > 4):
            story.append(Paragraph(safe(stripped), bold_s))
        elif stripped.startswith('⚑') or stripped.startswith('[ ]'):
            story.append(Paragraph(safe(stripped), flag_s))
        else:
            story.append(Paragraph(safe(stripped), body_s))

    # ── FOOTER ──
    story.append(Spacer(1,20))
    story.append(HRFlowable(width="100%",thickness=0.5,
                            color=MGRAY,spaceAfter=4))
    usage = analysis_result.get("usage",{})
    story.append(Paragraph(
        f"32-Rule Model v7 | "
        f"Generated {datetime.now().strftime('%B %d, %Y')} | "
        f"Tokens in: {usage.get('input_tokens','—')} | "
        f"Tokens out: {usage.get('output_tokens','—')}",
        PS("FT",fontSize=7,textColor=MGRAY,alignment=TA_CENTER)))
    story.append(Paragraph(
        "FOR ENTERTAINMENT AND INFORMATIONAL PURPOSES ONLY. "
        "Gambling involves risk. Problem Gambling Helpline: 1-800-GAMBLER.",
        PS("DS",fontSize=7,textColor=RED,alignment=TA_CENTER)))

    doc.build(story)
    print(f"PDF saved: {filename}")
    return filename
