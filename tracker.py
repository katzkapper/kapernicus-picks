import os
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

TRACKER_FILE = "posted_picks.json"


def load_picks():
    if not os.path.exists(TRACKER_FILE):
        return []
    try:
        with open(TRACKER_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_picks(picks):
    with open(TRACKER_FILE, "w") as f:
        json.dump(picks, f, indent=2)


def add_posted_picks(new_picks):
    """Add newly posted picks to the tracker file."""
    existing = load_picks()
    existing.extend(new_picks)
    save_picks(existing)
    print(f"  Tracker updated — {len(new_picks)} new picks added.")


def update_result(game, date, result):
    """
    Update the result of a posted pick.
    result should be: 'WIN', 'LOSS', or 'PUSH'
    Call this manually after games finish.
    """
    picks = load_picks()
    updated = 0
    for p in picks:
        if (
            p.get("game", "").lower() == game.lower()
            and p.get("date", "") == date
            and p.get("result") == "PENDING"
        ):
            p["result"] = result.upper()
            updated += 1
    save_picks(picks)
    print(f"Updated {updated} pick(s) for {game} on {date} → {result}")


def calculate_stats(picks):
    """Calculate running record and ROI from all picks."""
    settled = [p for p in picks if p.get("result") in ["WIN", "LOSS", "PUSH"]]
    pending = [p for p in picks if p.get("result") == "PENDING"]

    wins = sum(1 for p in settled if p["result"] == "WIN")
    losses = sum(1 for p in settled if p["result"] == "LOSS")
    pushes = sum(1 for p in settled if p["result"] == "PUSH")

    total_settled = wins + losses

    win_pct = round(wins / total_settled * 100, 1) if total_settled > 0 else 0

    # Units won/lost (wins pay -110 by default)
    units_won = sum(p.get("units", 1) * 0.909 for p in settled if p["result"] == "WIN")
    units_lost = sum(p.get("units", 1) for p in settled if p["result"] == "LOSS")
    net_units = round(units_won - units_lost, 2)

    # By tier
    tier_stats = {}
    for p in settled:
        tier = p.get("tier", "UNKNOWN")
        if tier not in tier_stats:
            tier_stats[tier] = {"wins": 0, "losses": 0, "pushes": 0}
        tier_stats[tier][p["result"].lower() + "s"] += 1

    # By market
    market_stats = {}
    for p in settled:
        mkt = p.get("market", "UNKNOWN")
        if mkt not in market_stats:
            market_stats[mkt] = {"wins": 0, "losses": 0, "pushes": 0}
        market_stats[mkt][p["result"].lower() + "s"] += 1

    # By rule flag
    r20_picks = [p for p in settled if p.get("rule20")]
    r31_picks = [p for p in settled if p.get("rule31")]

    r20_wins = sum(1 for p in r20_picks if p["result"] == "WIN")
    r31_wins = sum(1 for p in r31_picks if p["result"] == "WIN")

    return {
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "total_settled": total_settled,
        "pending": len(pending),
        "win_pct": win_pct,
        "net_units": net_units,
        "units_won": round(units_won, 2),
        "units_lost": round(units_lost, 2),
        "tier_stats": tier_stats,
        "market_stats": market_stats,
        "r20_record": f"{r20_wins}-{len(r20_picks) - r20_wins}",
        "r31_record": f"{r31_wins}-{len(r31_picks) - r31_wins}",
    }


def build_html(picks, stats):
    """Build the full tracker webpage HTML."""

    net_color = "#1A7A3E" if stats["net_units"] >= 0 else "#CC0000"
    net_sign = "+" if stats["net_units"] >= 0 else ""

    # Build pick rows
    rows = ""
    for p in sorted(picks, key=lambda x: x.get("date", ""), reverse=True):
        result = p.get("result", "PENDING")
        if result == "WIN":
            bg = "#D4EDDA"
            emoji = "✅"
        elif result == "LOSS":
            bg = "#FFE0E0"
            emoji = "❌"
        elif result == "PUSH":
            bg = "#FFF9E6"
            emoji = "➡️"
        else:
            bg = "#F8F9FA"
            emoji = "⏳"

        conf = p.get("confidence", 0)
        stars = "⭐⭐" if conf >= 62 else "⭐"

        flags = []
        if p.get("rule20"):
            flags.append("R20")
        if p.get("rule31"):
            flags.append("R31")
        try:
            gap = float(str(p.get("rule32_gap", 0)).replace("—", "0") or 0)
            if gap >= 3:
                flags.append(f"R32({gap})")
        except (ValueError, TypeError):
            pass

        flag_str = " ".join(flags) if flags else "—"

        tweet_id = p.get("tweet_id", "")
        tweet_link = ""
        if tweet_id:
            tweet_link = (
                f'<a href="https://twitter.com/i/'
                f'status/{tweet_id}" '
                f'target="_blank" '
                f'style="color:#1DA1F2;'
                f'font-size:11px;">🐦 View</a>'
            )

        rows += f"""
        <tr style="background:{bg};">
            <td style="padding:8px;font-size:12px;">
                {p.get("date", "—")}</td>
            <td style="padding:8px;font-size:12px;
                       font-weight:bold;">
                {p.get("game", "—")}</td>
            <td style="padding:8px;font-size:12px;">
                {p.get("market", "—")}</td>
            <td style="padding:8px;font-size:12px;
                       font-weight:bold;">
                {p.get("pick", "—")}</td>
            <td style="padding:8px;text-align:center;
                       font-size:12px;">
                {stars} {conf}%</td>
            <td style="padding:8px;text-align:center;
                       font-size:12px;">
                {p.get("units", "—")}u</td>
            <td style="padding:8px;text-align:center;
                       font-size:11px;color:#666;">
                {flag_str}</td>
            <td style="padding:8px;text-align:center;
                       font-weight:bold;">
                {emoji} {result}</td>
            <td style="padding:8px;text-align:center;">
                {tweet_link}</td>
        </tr>"""

    # Build tier breakdown rows
    tier_rows = ""
    for tier, ts in stats.get("tier_stats", {}).items():
        t_total = ts["wins"] + ts["losses"]
        t_winpct = round(ts["wins"] / t_total * 100, 1) if t_total > 0 else 0
        tier_rows += f"""
        <tr>
            <td style="padding:6px;font-size:12px;">
                {tier}</td>
            <td style="padding:6px;text-align:center;
                       font-size:12px;color:#1A7A3E;
                       font-weight:bold;">
                {ts["wins"]}</td>
            <td style="padding:6px;text-align:center;
                       font-size:12px;color:#CC0000;
                       font-weight:bold;">
                {ts["losses"]}</td>
            <td style="padding:6px;text-align:center;
                       font-size:12px;">
                {t_winpct}%</td>
        </tr>"""

    # Build market breakdown rows
    market_rows = ""
    for mkt, ms in stats.get("market_stats", {}).items():
        m_total = ms["wins"] + ms["losses"]
        m_winpct = round(ms["wins"] / m_total * 100, 1) if m_total > 0 else 0
        market_rows += f"""
        <tr>
            <td style="padding:6px;font-size:12px;">
                {mkt}</td>
            <td style="padding:6px;text-align:center;
                       font-size:12px;color:#1A7A3E;
                       font-weight:bold;">
                {ms["wins"]}</td>
            <td style="padding:6px;text-align:center;
                       font-size:12px;color:#CC0000;
                       font-weight:bold;">
                {ms["losses"]}</td>
            <td style="padding:6px;text-align:center;
                       font-size:12px;">
                {m_winpct}%</td>
        </tr>"""

    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Kapernicus Picks — Public Tracker</title>
    <meta name="viewport"
          content="width=device-width,
                   initial-scale=1">
    <style>
        body {{
            margin:0;padding:0;
            background:#F4F6F9;
            font-family:Arial,sans-serif;
        }}
        .container {{
            max-width:1100px;
            margin:20px auto;
            padding:0 15px;
        }}
        table {{
            width:100%;
            border-collapse:collapse;
        }}
        th {{
            background:#0D2240;
            color:white;
            padding:8px;
            font-size:12px;
            text-align:left;
        }}
        td {{ vertical-align:middle; }}
        .card {{
            background:white;
            border-radius:8px;
            padding:20px;
            margin-bottom:20px;
            box-shadow:0 2px 6px rgba(0,0,0,0.08);
        }}
        .stat-box {{
            text-align:center;
            padding:15px;
            border-radius:6px;
            flex:1;
        }}
        .stats-row {{
            display:flex;
            gap:10px;
            flex-wrap:wrap;
        }}
    </style>
</head>
<body>
<div class="container">

    <!-- HEADER -->
    <div class="card" style="background:#0D2240;
                              text-align:center;
                              padding:28px;">
        <div style="font-size:11px;color:#C8A951;
                    letter-spacing:3px;
                    margin-bottom:8px;">
            PUBLIC PICK TRACKER
        </div>
        <div style="font-size:28px;font-weight:bold;
                    color:white;">
            KAPERNICUS PICKS
        </div>
        <div style="font-size:13px;color:#aaa;
                    margin-top:6px;">
            32-Rule Model v7 | NCAA Men's Basketball
        </div>
        <div style="font-size:11px;color:#888;
                    margin-top:8px;">
            Updated: {generated}
        </div>
    </div>

    <!-- OVERALL RECORD -->
    <div class="card">
        <div style="font-size:14px;
                    font-weight:bold;
                    color:#0D2240;
                    margin-bottom:14px;">
            OVERALL RECORD
        </div>
        <div class="stats-row">
            <div class="stat-box"
                 style="background:#D4EDDA;">
                <div style="font-size:32px;
                            font-weight:bold;
                            color:#1A7A3E;">
                    {stats["wins"]}</div>
                <div style="font-size:11px;
                            color:#666;">WINS</div>
            </div>
            <div class="stat-box"
                 style="background:#FFE0E0;">
                <div style="font-size:32px;
                            font-weight:bold;
                            color:#CC0000;">
                    {stats["losses"]}</div>
                <div style="font-size:11px;
                            color:#666;">LOSSES</div>
            </div>
            <div class="stat-box"
                 style="background:#FFF9E6;">
                <div style="font-size:32px;
                            font-weight:bold;
                            color:#856404;">
                    {stats["pushes"]}</div>
                <div style="font-size:11px;
                            color:#666;">PUSHES</div>
            </div>
            <div class="stat-box"
                 style="background:#E8F4FD;">
                <div style="font-size:32px;
                            font-weight:bold;
                            color:#1A4A7A;">
                    {stats["win_pct"]}%</div>
                <div style="font-size:11px;
                            color:#666;">WIN %</div>
            </div>
            <div class="stat-box"
                 style="background:#{
        "D4EDDA" if stats["net_units"] >= 0 else "FFE0E0"
    };">
                <div style="font-size:32px;
                            font-weight:bold;
                            color:{net_color};">
                    {net_sign}{stats["net_units"]}u
                </div>
                <div style="font-size:11px;
                            color:#666;">NET UNITS</div>
            </div>
            <div class="stat-box"
                 style="background:#F8F9FA;">
                <div style="font-size:32px;
                            font-weight:bold;
                            color:#0D2240;">
                    {stats["pending"]}</div>
                <div style="font-size:11px;
                            color:#666;">PENDING</div>
            </div>
        </div>
    </div>

    <!-- BREAKDOWNS -->
    <div style="display:flex;gap:20px;
                flex-wrap:wrap;margin-bottom:20px;">

        <!-- BY TIER -->
        <div class="card" style="flex:1;
                                  min-width:280px;">
            <div style="font-size:13px;
                        font-weight:bold;
                        color:#0D2240;
                        margin-bottom:10px;">
                BY CONFIDENCE TIER
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Tier</th>
                        <th style="text-align:center;">
                            W</th>
                        <th style="text-align:center;">
                            L</th>
                        <th style="text-align:center;">
                            Win%</th>
                    </tr>
                </thead>
                <tbody>{tier_rows}</tbody>
            </table>
        </div>

        <!-- BY MARKET -->
        <div class="card" style="flex:1;
                                  min-width:280px;">
            <div style="font-size:13px;
                        font-weight:bold;
                        color:#0D2240;
                        margin-bottom:10px;">
                BY MARKET
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Market</th>
                        <th style="text-align:center;">
                            W</th>
                        <th style="text-align:center;">
                            L</th>
                        <th style="text-align:center;">
                            Win%</th>
                    </tr>
                </thead>
                <tbody>{market_rows}</tbody>
            </table>
        </div>

        <!-- RULE FLAGS -->
        <div class="card" style="flex:1;
                                  min-width:280px;">
            <div style="font-size:13px;
                        font-weight:bold;
                        color:#0D2240;
                        margin-bottom:10px;">
                RULE FLAG PERFORMANCE
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Rule</th>
                        <th style="text-align:center;">
                            Record</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="padding:6px;
                                   font-size:12px;">
                            Rule 20 Sharp Fade</td>
                        <td style="padding:6px;
                                   text-align:center;
                                   font-size:12px;
                                   font-weight:bold;">
                            {stats["r20_record"]}</td>
                    </tr>
                    <tr style="background:#F5F5F5;">
                        <td style="padding:6px;
                                   font-size:12px;">
                            Rule 31 Star Absorption</td>
                        <td style="padding:6px;
                                   text-align:center;
                                   font-size:12px;
                                   font-weight:bold;">
                            {stats["r31_record"]}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- ALL PICKS TABLE -->
    <div class="card">
        <div style="font-size:14px;
                    font-weight:bold;
                    color:#0D2240;
                    margin-bottom:14px;">
            ALL POSTED PICKS
        </div>
        <div style="overflow-x:auto;">
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Game</th>
                    <th>Market</th>
                    <th>Pick</th>
                    <th style="text-align:center;">
                        Conf</th>
                    <th style="text-align:center;">
                        Units</th>
                    <th style="text-align:center;">
                        Flags</th>
                    <th style="text-align:center;">
                        Result</th>
                    <th style="text-align:center;">
                        Tweet</th>
                </tr>
            </thead>
            <tbody>{
        rows
        if rows
        else '<tr><td colspan="9" '
        'style="padding:20px;'
        'text-align:center;color:#999;">'
        "No picks posted yet</td></tr>"
    }
            </tbody>
        </table>
        </div>
    </div>

    <!-- FOOTER -->
    <div style="text-align:center;
                font-size:11px;color:#999;
                padding:20px;">
        Kapernicus Picks — 32-Rule Model v7<br>
        For entertainment and informational
        purposes only.<br>
        Gambling involves risk.
        Problem Gambling Helpline: 1-800-GAMBLER.
    </div>

</div>
</body>
</html>"""


class TrackerHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to serve the tracker page."""

    def do_GET(self):
        picks = load_picks()
        stats = calculate_stats(picks)
        html = build_html(picks, stats)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress default access logs


def serve_tracker(port=8080):
    """Start the public tracker web server."""
    server = HTTPServer(("0.0.0.0", port), TrackerHandler)
    print(f"\nTracker running at port {port}")
    print("Share your Replit URL with .repl.co at the end for public access")
    print("Press Ctrl+C to stop\n")
    server.serve_forever()


def update_pick_result(game, date, result):
    """
    Quick helper to update a result from command line.
    Usage: python tracker.py update "Duke @ UNC" "March 16, 2026" WIN
    """
    update_result(game, date, result)
