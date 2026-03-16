import requests
import os
from datetime import datetime

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

SPORT_MAP = {
    "NBA":    "basketball_nba",
    "NCAAMB": "basketball_ncaab",
    "NFL":    "americanfootball_nfl",
    "NHL":    "icehockey_nhl",
    "MLB":    "baseball_mlb"
}


def get_betting_lines(team1, team2, sport="NCAAMB"):
    sport_key = SPORT_MAP.get(sport.upper(), "basketball_ncaab")
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "us",
        "markets":    "spreads,totals,h2h",
        "oddsFormat": "american",
        "bookmakers": "draftkings,fanduel,betmgm,bet365"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if isinstance(data, dict) and "message" in data:
            return {"error": data["message"]}
        games = []
        for game in data:
            home = game.get("home_team", "").lower()
            away = game.get("away_team", "").lower()
            t1   = team1.lower()
            t2   = team2.lower()
            if (t1 in home or t1 in away or
                    t2 in home or t2 in away):
                games.append(game)
        return games
    except Exception as e:
        return {"error": str(e)}


def format_lines_for_analysis(lines_data, team1, team2):
    if not lines_data:
        return (
            "No line data found — "
            "Claude will search for current lines."
        )
    if isinstance(lines_data, dict) and "error" in lines_data:
        return (
            f"Line data unavailable ({lines_data['error']}) — "
            "Claude will search for current lines."
        )
    output = []
    for game in lines_data:
        output.append(
            f"Game: {game.get('away_team')} "
            f"@ {game.get('home_team')}"
        )
        output.append(
            f"Commence: {game.get('commence_time', 'TBD')}")
        for bookmaker in game.get("bookmakers", []):
            book = bookmaker.get("title", "Unknown")
            for market in bookmaker.get("markets", []):
                if market["key"] == "spreads":
                    for o in market.get("outcomes", []):
                        output.append(
                            f"  {book} Spread — "
                            f"{o['name']}: "
                            f"{o['point']:+.1f} "
                            f"({o['price']:+d})"
                        )
                elif market["key"] == "totals":
                    for o in market.get("outcomes", []):
                        if o["name"] == "Over":
                            output.append(
                                f"  {book} Total: "
                                f"{o['point']} "
                                f"O{o['price']:+d}"
                            )
                elif market["key"] == "h2h":
                    for o in market.get("outcomes", []):
                        output.append(
                            f"  {book} ML — "
                            f"{o['name']}: "
                            f"{o['price']:+d}"
                        )
    return "\n".join(output) if output else (
        "No matching lines found — "
        "Claude will search for current lines."
    )


def collect_all_data(team1, team2, sport,
                     game_date, context):
    print(f"Fetching betting lines for "
          f"{team1} vs {team2}...")
    lines = get_betting_lines(team1, team2, sport)
    formatted = format_lines_for_analysis(
        lines, team1, team2)
    if isinstance(lines, dict) and "error" in lines:
        print("  Note: Line data unavailable — "
              "Claude will search for lines.")
    else:
        print("  Lines fetched successfully.")
    return {
        "team1":          team1,
        "team2":          team2,
        "sport":          sport,
        "game_date":      game_date,
        "context":        context,
        "betting_lines":  formatted,
        "data_timestamp": datetime.now().isoformat()
    }
