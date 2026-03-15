import smtplib
import os
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# YOUR EMAIL DISTRIBUTION LIST
# Add or remove email addresses here
# ─────────────────────────────────────────────────────────────
DISTRIBUTION_LIST = [
    "jrkatz123@gmail.com",
    "friend@gmail.com",
    "anotherperson@yahoo.com",
]

# ─────────────────────────────────────────────────────────────
# EMAIL SETTINGS
# ─────────────────────────────────────────────────────────────
GMAIL_ADDRESS     = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
SMTP_SERVER       = "smtp.gmail.com"
SMTP_PORT         = 587


def build_subject(game_data, picks):
    """Build a clear subject line showing the best bet"""
    team1 = game_data.get("team1", "Team1")
    team2 = game_data.get("team2", "Team2")
    date  = game_data.get("game_date", "")
    best  = picks.get("best_bet", "See report")
    conf  = picks.get("best_bet_confidence", 0)

    # Flag high confidence plays in subject line
    star = "★ " if isinstance(conf, int) and conf >= 65 else ""

    return (
        f"{star}Betting Report: {team1} vs {team2} "
        f"| {date} | Best Bet: {best} ({conf}%)"
    )


def build_html_body(game_data, picks):
    """Build a clean HTML email body summarizing the picks"""

    team1   = game_data.get("team1", "—")
    team2   = game_data.get("team2", "—")
    sport   = game_data.get("sport", "—")
    date    = game_data.get("game_date", "—")
    context = game_data.get("context", "—")

    sp_pick = picks.get("spread_pick", "—")
    sp_line = picks.get("spread_line", "—")
    sp_conf = picks.get("spread_confidence", "—")
    sp_rec  = picks.get("spread_recommendation", "—")

    tot_pick = picks.get("total_pick", "—")
    tot_line = picks.get("total_line", "—")
    tot_conf = picks.get("total_confidence", "—")
    tot_rec  = picks.get("total_recommendation", "—")

    best     = picks.get("best_bet", "—")
    best_conf= picks.get("best_bet_confidence", "—")
    score    = picks.get("predicted_score", "—")

    r20 = picks.get("rule20_active", False)
    r31 = picks.get("rule31_active", False)
    try:
        r32_gap = float(str(
            picks.get("rule32_gap", 0)
        ).replace("—", "0") or 0)
    except (ValueError, TypeError):
        r32_gap = 0

    # Color coding
    def spread_color(rec):
        r = str(rec).upper()
        if "PASS" in r:   return "#FFF3CD"
        if "BET" in r:    return "#D4EDDA"
        if "COVER" in r:  return "#D4EDDA"
        if "LEAN" in r:   return "#CCE5FF"
        return "#F8F9FA"

    def conf_color(conf):
        if not isinstance(conf, int): return "#6C757D"
        if conf >= 65: return "#1A7A3E"
        if conf >= 57: return "#856404"
        return "#721C24"

    # Build flag alerts
    flags_html = ""
    if r20:
        flags_html += """
        <div style="background:#CC0000;color:white;padding:10px;
                    border-radius:4px;margin:8px 0;
                    font-weight:bold;font-size:13px;">
            ⚑ RULE 20 — SHARP FADE IN EFFECT:
            Do not bet the favorite.
            Spread confidence reduced -7%.
        </div>"""

    if r31:
        flags_html += """
        <div style="background:#E07000;color:white;padding:10px;
                    border-radius:4px;margin:8px 0;
                    font-weight:bold;font-size:13px;">
            ⚑ RULE 31 — STAR ABSORPTION CEILING ACTIVE:
            Primary scorer absent.
            Total recommendation may be PASS.
        </div>"""

    if r32_gap >= 2:
        r32_rec = picks.get("rule32_recommendation", "—")
        r32_prob = picks.get("rule32_underdog_prob", "—")
        flags_html += f"""
        <div style="background:#1A4A7A;color:white;padding:10px;
                    border-radius:4px;margin:8px 0;
                    font-weight:bold;font-size:13px;">
            ▲ RULE 32 — LINE EXCEEDS MODEL BY {r32_gap} PTS
            | Underdog cover prob: {r32_prob}%
            | {r32_rec}
        </div>"""

    # Best bet box
    if str(best).upper() == "PASS" or best == "—":
        best_box = f"""
        <div style="background:#FFF3CD;padding:16px;
                    border-radius:6px;text-align:center;
                    margin:16px 0;">
            <div style="font-size:18px;font-weight:bold;
                        color:#333;">
                BEST BET: PASS
            </div>
            <div style="font-size:13px;color:#666;margin-top:4px;">
                No play meets confidence threshold
            </div>
        </div>"""
    else:
        best_box = f"""
        <div style="background:#1A7A3E;padding:16px;
                    border-radius:6px;text-align:center;
                    margin:16px 0;">
            <div style="font-size:11px;color:#90EE90;
                        letter-spacing:2px;">
                BEST BET
            </div>
            <div style="font-size:20px;font-weight:bold;
                        color:white;margin:6px 0;">
                {best}
            </div>
            <div style="font-size:14px;color:#90EE90;">
                {best_conf}% Confidence
            </div>
        </div>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width,
              initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#F4F6F9;
                 font-family:Arial,sans-serif;">

    <div style="max-width:600px;margin:20px auto;
                background:white;border-radius:8px;
                overflow:hidden;
                box-shadow:0 2px 8px rgba(0,0,0,0.1);">

        <!-- HEADER -->
        <div style="background:#0D2240;padding:24px;
                    text-align:center;">
            <div style="font-size:11px;color:#C8A951;
                        letter-spacing:3px;margin-bottom:8px;">
                PROFESSIONAL SPORTS BETTING ANALYSIS
            </div>
            <div style="font-size:22px;font-weight:bold;
                        color:white;">
                {team1} vs {team2}
            </div>
            <div style="font-size:13px;color:#aaa;
                        margin-top:6px;">
                {sport} | {date} | {context}
            </div>
        </div>

        <!-- BODY -->
        <div style="padding:20px;">

            {flags_html}
            {best_box}

            <!-- PICKS TABLE -->
            <table style="width:100%;border-collapse:collapse;
                          margin:16px 0;font-size:13px;">
                <thead>
                    <tr style="background:#0D2240;color:white;">
                        <th style="padding:10px;text-align:left;">
                            Market</th>
                        <th style="padding:10px;text-align:center;">
                            Pick</th>
                        <th style="padding:10px;text-align:center;">
                            Line</th>
                        <th style="padding:10px;text-align:center;">
                            Confidence</th>
                        <th style="padding:10px;text-align:center;">
                            Rec</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="background:{spread_color(sp_rec)};">
                        <td style="padding:10px;font-weight:bold;">
                            Spread</td>
                        <td style="padding:10px;text-align:center;">
                            {sp_pick}</td>
                        <td style="padding:10px;text-align:center;">
                            {sp_line}</td>
                        <td style="padding:10px;text-align:center;
                                   color:{conf_color(sp_conf)};
                                   font-weight:bold;">
                            {sp_conf}%</td>
                        <td style="padding:10px;text-align:center;
                                   font-weight:bold;">
                            {sp_rec}</td>
                    </tr>
                    <tr style="background:{spread_color(tot_rec)};">
                        <td style="padding:10px;font-weight:bold;">
                            Total</td>
                        <td style="padding:10px;text-align:center;">
                            {tot_pick}</td>
                        <td style="padding:10px;text-align:center;">
                            {tot_line}</td>
                        <td style="padding:10px;text-align:center;
                                   color:{conf_color(tot_conf)};
                                   font-weight:bold;">
                            {tot_conf}%</td>
                        <td style="padding:10px;text-align:center;
                                   font-weight:bold;">
                            {tot_rec}</td>
                    </tr>
                </tbody>
            </table>

            <!-- PREDICTED SCORE -->
            <div style="background:#F8F9FA;border-radius:6px;
                        padding:12px;text-align:center;
                        margin:12px 0;">
                <span style="font-size:12px;color:#666;">
                    PREDICTED SCORE: </span>
                <span style="font-size:14px;font-weight:bold;
                             color:#0D2240;">
                    {score}</span>
            </div>

            <!-- LINES USED -->
            <div style="background:#F8F9FA;border-radius:6px;
                        padding:12px;margin:12px 0;
                        font-size:12px;color:#555;">
                <strong>Lines used:</strong><br>
                {game_data.get('betting_lines','—')
                 .replace(chr(10),'<br>')}
            </div>

            <!-- FOOTER NOTE -->
            <div style="font-size:11px;color:#999;
                        text-align:center;margin-top:20px;
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
    </html>
    """

    return html


def send_report(game_data, picks, pdf_path,
                distribution_list=None):
    """
    Send the PDF report to the distribution list.
    Returns True if successful, False if failed.
    """

    if not GMAIL_ADDRESS:
        print("  Email skipped: GMAIL_ADDRESS not set in Secrets")
        return False

    if not GMAIL_APP_PASSWORD:
        print("  Email skipped: GMAIL_APP_PASSWORD not set in Secrets")
        return False

    recipients = distribution_list or DISTRIBUTION_LIST

    if not recipients:
        print("  Email skipped: No recipients in distribution list")
        return False

    if not pdf_path or not os.path.exists(pdf_path):
        print(f"  Email skipped: PDF not found at {pdf_path}")
        return False

    print(f"  Sending email to {len(recipients)} recipient(s)...")

    try:
        # Build message
        msg = MIMEMultipart('alternative')
        msg['From']    = GMAIL_ADDRESS
        msg['To']      = ", ".join(recipients)
        msg['Subject'] = build_subject(game_data, picks)
        msg['Reply-To']= GMAIL_ADDRESS

        # Plain text fallback
        text_body = (
            f"Betting Report: "
            f"{game_data.get('team1')} vs "
            f"{game_data.get('team2')}\n"
            f"Date: {game_data.get('game_date')}\n\n"
            f"BEST BET: {picks.get('best_bet','—')} "
            f"({picks.get('best_bet_confidence','—')}%)\n\n"
            f"SPREAD: {picks.get('spread_pick','—')} "
            f"{picks.get('spread_line','—')} | "
            f"{picks.get('spread_confidence','—')}% | "
            f"{picks.get('spread_recommendation','—')}\n"
            f"TOTAL: {picks.get('total_pick','—')} "
            f"{picks.get('total_line','—')} | "
            f"{picks.get('total_confidence','—')}%\n\n"
            f"See attached PDF for full analysis.\n\n"
            f"For entertainment purposes only."
        )

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(
            build_html_body(game_data, picks), 'html'))

        # Attach PDF
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()

        pdf_filename = os.path.basename(pdf_path)
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(pdf_data)
        encoders.encode_base64(attachment)
        attachment.add_header(
            'Content-Disposition',
            f'attachment; filename="{pdf_filename}"'
        )
        msg.attach(attachment)

        # Connect and send
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(
                GMAIL_ADDRESS,
                recipients,
                msg.as_string()
            )

        print(f"  ✓ Email sent to: {', '.join(recipients)}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("  ✗ Email failed: Authentication error.")
        print("    Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD in Secrets.")
        print("    Make sure you used an App Password, not your regular password.")
        return False

    except smtplib.SMTPException as e:
        print(f"  ✗ Email failed (SMTP error): {e}")
        return False

    except Exception as e:
        print(f"  ✗ Email failed (unexpected error): {e}")
        return False


def send_batch_summary(all_results, target_date,
                       master_pdf_path,
                       distribution_list=None):
    """
    Send a single summary email after a batch run
    with the master summary PDF attached.
    """

    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("  Batch email skipped: credentials not set")
        return False

    recipients = distribution_list or DISTRIBUTION_LIST

    if not recipients:
        print("  Batch email skipped: no recipients")
        return False

    print(f"\n  Sending batch summary email to "
          f"{len(recipients)} recipient(s)...")

    # Count stats
    total   = len(all_results)
    success = sum(1 for r in all_results if r.get("picks"))
    high_conf = [
        r for r in all_results
        if isinstance(
            r.get("picks", {}).get("best_bet_confidence"), int
        ) and r["picks"]["best_bet_confidence"] >= 65
    ]

    # Build high confidence plays HTML
    hc_rows = ""
    for r in sorted(
        high_conf,
        key=lambda x: x["picks"]["best_bet_confidence"],
        reverse=True
    ):
        p = r.get("picks", {})
        hc_rows += f"""
        <tr style="background:#D4EDDA;">
            <td style="padding:8px;font-weight:bold;">
                {r.get('game_label','—')}</td>
            <td style="padding:8px;text-align:center;">
                {p.get('best_bet','—')}</td>
            <td style="padding:8px;text-align:center;
                       color:#1A7A3E;font-weight:bold;">
                {p.get('best_bet_confidence','—')}%</td>
        </tr>"""

    if not hc_rows:
        hc_rows = """
        <tr><td colspan="3"
               style="padding:12px;text-align:center;color:#666;">
            No plays above 65% confidence threshold today
        </td></tr>"""

    # Build all games rows
    all_rows = ""
    for r in all_results:
        p = r.get("picks", {})
        bc = p.get("best_bet_confidence", 0)
        bg = "#D4EDDA" if (
            isinstance(bc, int) and bc >= 65
        ) else "white"
        all_rows += f"""
        <tr style="background:{bg};">
            <td style="padding:7px;font-size:12px;">
                {r.get('game_label','—')}</td>
            <td style="padding:7px;text-align:center;
                       font-size:12px;">
                {p.get('spread_pick','—')}
                {p.get('spread_line','—')}</td>
            <td style="padding:7px;text-align:center;
                       font-size:12px;">
                {p.get('total_pick','—')}
                {p.get('total_line','—')}</td>
            <td style="padding:7px;text-align:center;
                       font-size:12px;font-weight:bold;">
                {p.get('best_bet','—')[:30]}</td>
            <td style="padding:7px;text-align:center;
                       font-size:12px;font-weight:bold;">
                {bc}%</td>
        </tr>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background:#F4F6F9;
                 font-family:Arial,sans-serif;">
    <div style="max-width:700px;margin:20px auto;
                background:white;border-radius:8px;
                overflow:hidden;
                box-shadow:0 2px 8px rgba(0,0,0,0.1);">

        <!-- HEADER -->
        <div style="background:#0D2240;padding:24px;
                    text-align:center;">
            <div style="font-size:11px;color:#C8A951;
                        letter-spacing:3px;margin-bottom:8px;">
                BATCH ANALYSIS COMPLETE
            </div>
            <div style="font-size:22px;font-weight:bold;
                        color:white;">
                NCAA Men's Basketball
            </div>
            <div style="font-size:14px;color:#aaa;
                        margin-top:6px;">
                {target_date}
            </div>
        </div>

        <div style="padding:20px;">

            <!-- STATS ROW -->
            <table style="width:100%;margin-bottom:20px;">
                <tr>
                    <td style="text-align:center;padding:12px;
                               background:#F8F9FA;
                               border-radius:6px;">
                        <div style="font-size:28px;
                                    font-weight:bold;
                                    color:#0D2240;">
                            {total}</div>
                        <div style="font-size:11px;color:#666;">
                            Games Analyzed</div>
                    </td>
                    <td style="width:12px;"></td>
                    <td style="text-align:center;padding:12px;
                               background:#D4EDDA;
                               border-radius:6px;">
                        <div style="font-size:28px;
                                    font-weight:bold;
                                    color:#1A7A3E;">
                            {len(high_conf)}</div>
                        <div style="font-size:11px;color:#666;">
                            High Confidence Plays</div>
                    </td>
                    <td style="width:12px;"></td>
                    <td style="text-align:center;padding:12px;
                               background:#F8F9FA;
                               border-radius:6px;">
                        <div style="font-size:28px;
                                    font-weight:bold;
                                    color:#0D2240;">
                            {success}</div>
                        <div style="font-size:11px;color:#666;">
                            Successful Analyses</div>
                    </td>
                </tr>
            </table>

            <!-- HIGH CONFIDENCE PLAYS -->
            <div style="font-size:14px;font-weight:bold;
                        color:#1A7A3E;margin-bottom:8px;">
                ★ High Confidence Plays (65%+)
            </div>
            <table style="width:100%;border-collapse:collapse;
                          margin-bottom:20px;font-size:13px;">
                <thead>
                    <tr style="background:#0D2240;color:white;">
                        <th style="padding:8px;text-align:left;">
                            Game</th>
                        <th style="padding:8px;text-align:center;">
                            Best Bet</th>
                        <th style="padding:8px;text-align:center;">
                            Confidence</th>
                    </tr>
                </thead>
                <tbody>{hc_rows}</tbody>
            </table>

            <!-- ALL GAMES -->
            <div style="font-size:14px;font-weight:bold;
                        color:#0D2240;margin-bottom:8px;">
                All Games
            </div>
            <table style="width:100%;border-collapse:collapse;
                          font-size:12px;">
                <thead>
                    <tr style="background:#0D2240;color:white;">
                        <th style="padding:7px;text-align:left;">
                            Game</th>
                        <th style="padding:7px;text-align:center;">
                            Spread</th>
                        <th style="padding:7px;text-align:center;">
                            Total</th>
                        <th style="padding:7px;text-align:center;">
                            Best Bet</th>
                        <th style="padding:7px;text-align:center;">
                            Conf</th>
                    </tr>
                </thead>
                <tbody>{all_rows}</tbody>
            </table>

            <div style="font-size:11px;color:#999;
                        text-align:center;margin-top:20px;
                        padding-top:16px;
                        border-top:1px solid #eee;">
                Master summary PDF attached.<br>
                Generated {datetime.now().strftime(
                    '%B %d, %Y at %I:%M %p')}<br><br>
                <em>For entertainment and informational
                purposes only. Gambling involves risk.
                Problem Gambling Helpline: 1-800-GAMBLER.</em>
            </div>
        </div>
    </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart('alternative')
        msg['From']    = GMAIL_ADDRESS
        msg['To']      = ", ".join(recipients)
        msg['Subject'] = (
            f"Batch Analysis: NCAA Basketball {target_date} | "
            f"{len(high_conf)} High Confidence Plays | "
            f"{total} Games Analyzed"
        )

        text_body = (
            f"Batch Analysis Complete: {target_date}\n"
            f"Games analyzed: {total}\n"
            f"High confidence plays: {len(high_conf)}\n\n"
        )
        for r in high_conf:
            p = r.get("picks", {})
            text_body += (
                f"★ {r.get('game_label','—')}: "
                f"{p.get('best_bet','—')} "
                f"({p.get('best_bet_confidence','—')}%)\n"
            )
        text_body += "\nSee attached PDF for full details."

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html, 'html'))

        # Attach master summary PDF
        if master_pdf_path and os.path.exists(master_pdf_path):
            with open(master_pdf_path, 'rb') as f:
                pdf_data = f.read()
            attachment = MIMEBase('application', 'octet-stream')
            attachment.set_payload(pdf_data)
            encoders.encode_base64(attachment)
            attachment.add_header(
                'Content-Disposition',
                f'attachment; filename="'
                f'{os.path.basename(master_pdf_path)}"'
            )
            msg.attach(attachment)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(
                GMAIL_ADDRESS,
                recipients,
                msg.as_string()
            )

        print(f"  ✓ Batch summary email sent to: "
              f"{', '.join(recipients)}")
        return True

    except Exception as e:
        print(f"  ✗ Batch email failed: {e}")
        return False
