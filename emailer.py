import os
import json
import base64
import smtplib
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from confidence_utils import (
    get_star, get_row_color, get_conf_text_color,
    get_confidence_tier, format_unit_label,
    HIGH_CONF_FLOOR, RECOMMENDED_FLOOR
)

# ─────────────────────────────────────────────────────────────
# YOUR EMAIL DISTRIBUTION LIST
# ─────────────────────────────────────────────────────────────
DISTRIBUTION_LIST = [
    "jrkatz123@gmail.com",
    "jessebergman1@gmail.com",
    "retserrofad@gmail.com",
]

GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get(
    "GMAIL_APP_PASSWORD", "")


def build_subject(game_data, picks):
    team1 = game_data.get("team1", "Team1")
    team2 = game_data.get("team2", "Team2")
    date  = game_data.get("game_date", "")
    best  = picks.get("best_bet", "See report")
    conf  = picks.get("best_bet_confidence", 0)
    star  = get_star(conf, picks)
    return (
        f"{star}Katz Kapper: {team1} vs {team2} "
        f"| {date} | Best Bet: {best} ({conf}%)"
    )


def build_html_body(game_data, picks):
    team1    = game_data.get("team1", "—")
    team2    = game_data.get("team2", "—")
    sport    = game_data.get("sport", "—")
    date     = game_data.get("game_date", "—")
    context  = game_data.get("context", "—")
    sp_pick  = picks.get("spread_pick", "—")
    sp_line  = picks.get("spread_line", "—")
    sp_conf  = picks.get("spread_confidence", "—")
    sp_rec   = picks.get("spread_recommendation", "—")
    tot_pick = picks.get("total_pick", "—")
    tot_line = picks.get("total_line", "—")
    tot_conf = picks.get("total_confidence", "—")
    tot_rec  = picks.get("total_recommendation", "—")
    best     = picks.get("best_bet", "—")
    best_conf= picks.get("best_bet_confidence", "—")
    score    = picks.get("predicted_score", "—")

    s_units = format_unit_label(
        sp_conf if isinstance(sp_conf, int)
        else 0, picks)
    t_units = format_unit_label(
        tot_conf if isinstance(tot_conf, int)
        else 0, picks)
    b_units = format_unit_label(
        best_conf if isinstance(best_conf, int)
        else 0, picks)

    def spread_color(rec):
        r = str(rec).upper()
        if "PASS" in r:   return "#FFF3CD"
        if "BET" in r:    return "#D4EDDA"
        if "COVER" in r:  return "#D4EDDA"
        if "LEAN" in r:   return "#CCE5FF"
        return "#F8F9FA"

    flags_html = ""
    if picks.get("rule20_active"):
        flags_html += """
        <div style="background:#CC0000;color:white;
                    padding:10px;border-radius:4px;
                    margin:8px 0;font-weight:bold;
                    font-size:13px;">
            ⚑ RULE 20 — SHARP FADE IN EFFECT:
            Do not bet the favorite.
        </div>"""
    if picks.get("rule31_active"):
        flags_html += """
        <div style="background:#E07000;color:white;
                    padding:10px;border-radius:4px;
                    margin:8px 0;font-weight:bold;
                    font-size:13px;">
            ⚑ RULE 31 — STAR ABSORPTION CEILING ACTIVE
        </div>"""
    try:
        r32_gap = float(str(
            picks.get("rule32_gap", 0)
        ).replace("—", "0") or 0)
    except (ValueError, TypeError):
        r32_gap = 0
    if r32_gap >= 2:
        flags_html += f"""
        <div style="background:#1A4A7A;color:white;
                    padding:10px;border-radius:4px;
                    margin:8px 0;font-weight:bold;
                    font-size:13px;">
            ▲ RULE 32 — LINE EXCEEDS MODEL BY
            {r32_gap} PTS |
            {picks.get('rule32_recommendation','—')}
        </div>"""

    bb2      = picks.get("best_bet_2", "PASS")
    bc2      = picks.get("best_bet_2_confidence", 0)
    bm2      = picks.get("best_bet_2_market", "PASS")
    b2_units = format_unit_label(
        bc2 if isinstance(bc2, int) else 0, picks)
    show_bb2 = (str(bb2).upper() != "PASS" and
                bb2 != "—" and
                isinstance(bc2, int) and bc2 >= 57)

    if str(best).upper() == "PASS" or best == "—":
        best_box = """
        <div style="background:#FFF3CD;padding:16px;
                    border-radius:6px;text-align:center;
                    margin:16px 0;">
            <div style="font-size:18px;
                        font-weight:bold;
                        color:#333;">
                BEST BET: PASS</div>
            <div style="font-size:13px;color:#666;
                        margin-top:4px;">
                No play meets 57% threshold</div>
        </div>"""
    else:
        bb2_box = ""
        if show_bb2:
            bb2_box = f"""
        <div style="background:#1A5A3E;padding:14px;
                    border-radius:6px;
                    text-align:center;
                    margin:8px 0;">
            <div style="font-size:10px;color:#90EE90;
                        letter-spacing:2px;">
                BEST BET 2 — {bm2}</div>
            <div style="font-size:17px;
                        font-weight:bold;
                        color:white;margin:5px 0;">
                {bb2}</div>
            <div style="font-size:13px;
                        color:#90EE90;">
                {bc2}% — {b2_units}</div>
        </div>"""

        best_box = f"""
        <div style="margin:16px 0;">
            <div style="background:#1A7A3E;
                        padding:16px;
                        border-radius:6px;
                        text-align:center;
                        margin-bottom:8px;">
                <div style="font-size:11px;
                            color:#90EE90;
                            letter-spacing:2px;">
                    BEST BET 1 — SPREAD/TOTAL</div>
                <div style="font-size:20px;
                            font-weight:bold;
                            color:white;
                            margin:6px 0;">
                    {best}</div>
                <div style="font-size:14px;
                            color:#90EE90;">
                    {best_conf}% — {b_units}</div>
            </div>
            {bb2_box}
        </div>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;
                 background:#F4F6F9;
                 font-family:Arial,sans-serif;">
    <div style="max-width:600px;margin:20px auto;
                background:white;border-radius:8px;
                overflow:hidden;
                box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#0D2240;padding:24px;
                    text-align:center;">
            <div style="font-size:11px;color:#C8A951;
                        letter-spacing:3px;
                        margin-bottom:8px;">
                KAPERNICUS PICKS</div>
            <div style="font-size:22px;
                        font-weight:bold;
                        color:white;">
                {team1} vs {team2}</div>
            <div style="font-size:13px;color:#aaa;
                        margin-top:6px;">
                {sport} | {date} | {context}</div>
        </div>
        <div style="padding:20px;">
            {flags_html}
            {best_box}
            <table style="width:100%;
                          border-collapse:collapse;
                          margin:16px 0;
                          font-size:13px;">
                <thead>
                    <tr style="background:#0D2240;
                               color:white;">
                        <th style="padding:10px;
                                   text-align:left;">
                            Market</th>
                        <th style="padding:10px;
                                   text-align:center;">
                            Pick</th>
                        <th style="padding:10px;
                                   text-align:center;">
                            Line</th>
                        <th style="padding:10px;
                                   text-align:center;">
                            Conf</th>
                        <th style="padding:10px;
                                   text-align:center;">
                            Rec</th>
                        <th style="padding:10px;
                                   text-align:center;">
                            Units</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="background:
                               {spread_color(sp_rec)};">
                        <td style="padding:10px;
                                   font-weight:bold;">
                            Spread</td>
                        <td style="padding:10px;
                                   text-align:center;">
                            {sp_pick}</td>
                        <td style="padding:10px;
                                   text-align:center;">
                            {sp_line}</td>
                        <td style="padding:10px;
                                   text-align:center;
                                   color:{get_conf_text_color(sp_conf)};
                                   font-weight:bold;">
                            {sp_conf}%</td>
                        <td style="padding:10px;
                                   text-align:center;
                                   font-weight:bold;">
                            {sp_rec}</td>
                        <td style="padding:10px;
                                   text-align:center;
                                   font-weight:bold;">
                            {s_units}</td>
                    </tr>
                    <tr style="background:
                               {spread_color(tot_rec)};">
                        <td style="padding:10px;
                                   font-weight:bold;">
                            Total</td>
                        <td style="padding:10px;
                                   text-align:center;">
                            {tot_pick}</td>
                        <td style="padding:10px;
                                   text-align:center;">
                            {tot_line}</td>
                        <td style="padding:10px;
                                   text-align:center;
                                   color:{get_conf_text_color(tot_conf)};
                                   font-weight:bold;">
                            {tot_conf}%</td>
                        <td style="padding:10px;
                                   text-align:center;
                                   font-weight:bold;">
                            {tot_rec}</td>
                        <td style="padding:10px;
                                   text-align:center;
                                   font-weight:bold;">
                            {t_units}</td>
                    </tr>
                </tbody>
            </table>
            <div style="background:#F8F9FA;
                        border-radius:6px;
                        padding:12px;
                        text-align:center;
                        margin:12px 0;">
                <span style="font-size:12px;
                             color:#666;">
                    PREDICTED SCORE: </span>
                <span style="font-size:14px;
                             font-weight:bold;
                             color:#0D2240;">
                    {score}</span>
            </div>
            <div style="font-size:11px;color:#999;
                        text-align:center;
                        margin-top:20px;
                        padding-top:16px;
                        border-top:1px solid #eee;">
                Full analysis attached as PDF.<br>
                Generated {datetime.now().strftime(
                    '%B %d, %Y at %I:%M %p')}<br><br>
                <em>For entertainment and informational
                purposes only. Gambling involves risk.
                Problem Gambling Helpline:
                1-800-GAMBLER.</em>
            </div>
        </div>
    </div>
    </body>
    </html>"""


def _send_smtp(to_addresses, msg):
    """Try SSL port 465 first, then TLS port 587"""
    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com", 465, timeout=15
        ) as server:
            server.ehlo()
            server.login(
                GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(
                GMAIL_ADDRESS, to_addresses,
                msg.as_string())
        return True
    except Exception as e1:
        print(f"  SSL 465 failed: {e1} "
              f"— trying TLS 587...")
        try:
            with smtplib.SMTP(
                "smtp.gmail.com", 587, timeout=15
            ) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(
                    GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                server.sendmail(
                    GMAIL_ADDRESS, to_addresses,
                    msg.as_string())
            return True
        except Exception as e2:
            print(f"  TLS 587 failed: {e2}")
            return False


def _build_msg(to_addresses, subject,
               html_body, pdf_path=None):
    msg = MIMEMultipart("mixed")
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = ", ".join(to_addresses)
    msg["Subject"] = subject
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(
        "See HTML version for full report.", "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()
        attachment = MIMEBase(
            "application", "octet-stream")
        attachment.set_payload(pdf_data)
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            f'attachment; filename="'
            f'{os.path.basename(pdf_path)}"'
        )
        msg.attach(attachment)
    return msg


def send_report(game_data, picks, pdf_path,
                distribution_list=None):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("  Email skipped: credentials not set")
        return False
    recipients = distribution_list or DISTRIBUTION_LIST
    if not recipients:
        print("  Email skipped: no recipients")
        return False
    if not pdf_path or not os.path.exists(pdf_path):
        print("  Email skipped: PDF not found")
        return False

    print(f"  Sending to "
          f"{len(recipients)} recipient(s)...")
    subject   = build_subject(game_data, picks)
    html_body = build_html_body(game_data, picks)
    msg       = _build_msg(
        recipients, subject, html_body, pdf_path)
    success   = _send_smtp(recipients, msg)
    if success:
        print(f"  ✓ Email sent to: "
              f"{', '.join(recipients)}")
    return success


def send_batch_summary(all_results, target_date,
                       master_pdf_path,
                       distribution_list=None):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("  Batch email skipped: "
              "credentials not set")
        return False
    recipients = distribution_list or DISTRIBUTION_LIST
    if not recipients:
        print("  Batch email skipped: no recipients")
        return False

    print(f"\n  Sending batch summary to "
          f"{len(recipients)} recipient(s)...")

    total = len(all_results)

    # ── CATEGORIZE RESULTS ──
    # High confidence: BB1 OR BB2 is 62%+
    def _is_high(r):
        p     = r.get("picks", {})
        conf  = p.get("best_bet_confidence", 0)
        conf2 = p.get("best_bet_2_confidence", 0)
        if get_confidence_tier(
                conf, p) == "high_confidence":
            return True
        if (isinstance(conf2, int) and
                conf2 >= HIGH_CONF_FLOOR):
            return True
        return False

    # Recommended: BB1 is 57-61% (not high conf)
    def _is_rec(r):
        p    = r.get("picks", {})
        conf = p.get("best_bet_confidence", 0)
        return (get_confidence_tier(
            conf, p) == "recommended" and
            not _is_high(r))

    high_conf   = [r for r in all_results
                   if _is_high(r)]
    recommended = [r for r in all_results
                   if _is_rec(r)]

    # Also add games where BB1 is high conf
    # but BB2 is recommended (57-61%)
    hc_labels = {
        r.get("game_label") for r in high_conf}
    for r in all_results:
        p    = r.get("picks", {})
        bc2  = p.get("best_bet_2_confidence", 0)
        bb2  = p.get("best_bet_2", "PASS")
        if (r.get("game_label") in hc_labels and
                str(bb2).upper() != "PASS" and
                bb2 != "—" and
                isinstance(bc2, int) and
                57 <= bc2 < HIGH_CONF_FLOOR and
                r not in recommended):
            recommended.append(r)

    # ── HIGH CONFIDENCE ROWS ──
    hc_rows = ""
    for r in sorted(
        high_conf,
        key=lambda x: x["picks"].get(
            "best_bet_confidence", 0),
        reverse=True
    ):
        p     = r.get("picks", {})
        conf  = p.get("best_bet_confidence", 0)
        units = format_unit_label(conf, p)
        bg    = get_row_color(conf, p)

        bb2  = p.get("best_bet_2", "PASS")
        bc2  = p.get("best_bet_2_confidence", 0)
        u2   = format_unit_label(
            bc2 if isinstance(bc2, int) else 0, p)

        # BB2 only shows in HC email section
        # if BB2 itself is 62%+
        bb2_cell = "—"
        if (str(bb2).upper() != "PASS" and
                bb2 != "—" and
                isinstance(bc2, int) and
                bc2 >= HIGH_CONF_FLOOR):
            bb2_cell = f"{bb2} ({bc2}% — {u2})"

        hc_rows += f"""
        <tr style="background:{bg};">
            <td style="padding:8px;
                       font-weight:bold;">
                {r.get('game_label','—')}</td>
            <td style="padding:8px;
                       text-align:center;">
                {p.get('best_bet','—')}</td>
            <td style="padding:8px;
                       text-align:center;
                       color:#1A7A3E;
                       font-weight:bold;">
                {conf}% — {units}</td>
            <td style="padding:8px;
                       text-align:center;
                       color:#1A5A3E;
                       font-weight:bold;">
                {bb2_cell}</td>
        </tr>"""

    if not hc_rows:
        hc_rows = """
        <tr><td colspan="4"
               style="padding:12px;
                      text-align:center;
                      color:#666;">
            No plays above 62% threshold today
        </td></tr>"""

    # ── RECOMMENDED ROWS ──
    rec_rows = ""
    for r in sorted(
        recommended,
        key=lambda x: x["picks"].get(
            "best_bet_confidence", 0),
        reverse=True
    ):
        p     = r.get("picks", {})
        conf  = p.get("best_bet_confidence", 0)
        units = format_unit_label(conf, p)

        bb2  = p.get("best_bet_2", "PASS")
        bc2  = p.get("best_bet_2_confidence", 0)
        u2   = format_unit_label(
            bc2 if isinstance(bc2, int) else 0, p)

        # BB2 shows in rec section only if 57-61%
        bb2_cell = "—"
        if (str(bb2).upper() != "PASS" and
                bb2 != "—" and
                isinstance(bc2, int) and
                57 <= bc2 < HIGH_CONF_FLOOR):
            bb2_cell = f"{bb2} ({bc2}% — {u2})"

        rec_rows += f"""
        <tr style="background:#FFF9E6;">
            <td style="padding:8px;
                       font-weight:bold;">
                {r.get('game_label','—')}</td>
            <td style="padding:8px;
                       text-align:center;">
                {p.get('best_bet','—')}</td>
            <td style="padding:8px;
                       text-align:center;
                       color:#856404;
                       font-weight:bold;">
                {conf}% — {units}</td>
            <td style="padding:8px;
                       text-align:center;
                       color:#856404;
                       font-weight:bold;">
                {bb2_cell}</td>
        </tr>"""

    if not rec_rows:
        rec_rows = """
        <tr><td colspan="4"
               style="padding:12px;
                      text-align:center;
                      color:#666;">
            No recommended plays today
        </td></tr>"""

    # ── ALL GAMES ROWS ──
    all_rows = ""
    for r in all_results:
        p    = r.get("picks", {})
        conf = p.get("best_bet_confidence", 0)
        bg   = get_row_color(conf, p)
        units= format_unit_label(conf, p)
        all_rows += f"""
        <tr style="background:{bg};">
            <td style="padding:7px;font-size:12px;">
                {r.get('game_label','—')}</td>
            <td style="padding:7px;
                       text-align:center;
                       font-size:12px;">
                {p.get('spread_pick','—')}
                {p.get('spread_line','—')}</td>
            <td style="padding:7px;
                       text-align:center;
                       font-size:12px;">
                {p.get('total_pick','—')}
                {p.get('total_line','—')}</td>
            <td style="padding:7px;
                       text-align:center;
                       font-size:12px;
                       font-weight:bold;">
                {str(p.get('best_bet','—'))[:30]}</td>
            <td style="padding:7px;
                       text-align:center;
                       font-size:12px;
                       font-weight:bold;">
                {conf}%</td>
            <td style="padding:7px;
                       text-align:center;
                       font-size:12px;
                       font-weight:bold;">
                {units}</td>
        </tr>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;
                 background:#F4F6F9;
                 font-family:Arial,sans-serif;">
    <div style="max-width:700px;margin:20px auto;
                background:white;border-radius:8px;
                overflow:hidden;
                box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#0D2240;padding:24px;
                    text-align:center;">
            <div style="font-size:11px;color:#C8A951;
                        letter-spacing:3px;
                        margin-bottom:8px;">
                KAPERNICUS PICKS</div>
            <div style="font-size:22px;
                        font-weight:bold;
                        color:white;">
                NCAA Men's Basketball</div>
            <div style="font-size:14px;color:#aaa;
                        margin-top:6px;">
                {target_date}</div>
        </div>
        <div style="padding:20px;">

            <!-- STATS BOXES -->
            <table style="width:100%;
                          margin-bottom:20px;">
                <tr>
                    <td style="text-align:center;
                               padding:12px;
                               background:#F8F9FA;
                               border-radius:6px;">
                        <div style="font-size:28px;
                                    font-weight:bold;
                                    color:#0D2240;">
                            {total}</div>
                        <div style="font-size:11px;
                                    color:#666;">
                            Games Analyzed</div>
                    </td>
                    <td style="width:8px;"></td>
                    <td style="text-align:center;
                               padding:12px;
                               background:#D4EDDA;
                               border-radius:6px;">
                        <div style="font-size:28px;
                                    font-weight:bold;
                                    color:#1A7A3E;">
                            {len(high_conf)}</div>
                        <div style="font-size:11px;
                                    color:#666;">
                            High Conf 62%+
                            (1.5-2u)</div>
                    </td>
                    <td style="width:8px;"></td>
                    <td style="text-align:center;
                               padding:12px;
                               background:#FFF9E6;
                               border-radius:6px;">
                        <div style="font-size:28px;
                                    font-weight:bold;
                                    color:#856404;">
                            {len(recommended)}</div>
                        <div style="font-size:11px;
                                    color:#666;">
                            Recommended 57-61%
                            (1u)</div>
                    </td>
                </tr>
            </table>

            <!-- HIGH CONFIDENCE TABLE -->
            <div style="font-size:14px;
                        font-weight:bold;
                        color:#1A7A3E;
                        margin-bottom:8px;">
                ★★ High Confidence Plays (62%+)
            </div>
            <table style="width:100%;
                          border-collapse:collapse;
                          margin-bottom:20px;
                          font-size:13px;">
                <thead>
                    <tr style="background:#0D2240;
                               color:white;">
                        <th style="padding:8px;
                                   text-align:left;">
                            Game</th>
                        <th style="padding:8px;
                                   text-align:center;">
                            Best Bet 1</th>
                        <th style="padding:8px;
                                   text-align:center;">
                            Conf / Units</th>
                        <th style="padding:8px;
                                   text-align:center;">
                            Best Bet 2 (62%+)</th>
                    </tr>
                </thead>
                <tbody>{hc_rows}</tbody>
            </table>

            <!-- RECOMMENDED TABLE -->
            <div style="font-size:14px;
                        font-weight:bold;
                        color:#856404;
                        margin-bottom:8px;">
                ★ Recommended Plays (57-61%)
            </div>
            <table style="width:100%;
                          border-collapse:collapse;
                          margin-bottom:20px;
                          font-size:13px;">
                <thead>
                    <tr style="background:#0D2240;
                               color:white;">
                        <th style="padding:8px;
                                   text-align:left;">
                            Game</th>
                        <th style="padding:8px;
                                   text-align:center;">
                            Best Bet 1</th>
                        <th style="padding:8px;
                                   text-align:center;">
                            Conf / Units</th>
                        <th style="padding:8px;
                                   text-align:center;">
                            Best Bet 2 (57-61%)</th>
                    </tr>
                </thead>
                <tbody>{rec_rows}</tbody>
            </table>

            <!-- ALL GAMES TABLE -->
            <div style="font-size:14px;
                        font-weight:bold;
                        color:#0D2240;
                        margin-bottom:8px;">
                All Games
            </div>
            <table style="width:100%;
                          border-collapse:collapse;
                          font-size:12px;">
                <thead>
                    <tr style="background:#0D2240;
                               color:white;">
                        <th style="padding:7px;
                                   text-align:left;">
                            Game</th>
                        <th style="padding:7px;
                                   text-align:center;">
                            Spread</th>
                        <th style="padding:7px;
                                   text-align:center;">
                            Total</th>
                        <th style="padding:7px;
                                   text-align:center;">
                            Best Bet</th>
                        <th style="padding:7px;
                                   text-align:center;">
                            Conf</th>
                        <th style="padding:7px;
                                   text-align:center;">
                            Units</th>
                    </tr>
                </thead>
                <tbody>{all_rows}</tbody>
            </table>

            <div style="font-size:11px;color:#999;
                        text-align:center;
                        margin-top:20px;
                        padding-top:16px;
                        border-top:1px solid #eee;">
                Master summary PDF attached.<br>
                Generated {datetime.now().strftime(
                    '%B %d, %Y at %I:%M %p')}<br><br>
                <em>For entertainment and informational
                purposes only. Gambling involves risk.
                Problem Gambling Helpline:
                1-800-GAMBLER.</em>
            </div>
        </div>
    </div>
    </body>
    </html>"""

    subject = (
        f"Katz Kapper: NCAA Basketball {target_date} | "
        f"{len(high_conf)} High Confidence | "
        f"{len(recommended)} Recommended | "
        f"{total} Games Analyzed"
    )

    msg = _build_msg(
        recipients, subject, html, master_pdf_path)
    success = _send_smtp(recipients, msg)
    if success:
        print(f"  ✓ Batch summary sent to: "
              f"{', '.join(recipients)}")
    return success
