import requests
import os
from datetime import datetime

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
SPORTS_API_KEY = os.environ.get("SPORTS_API_KEY", "")

SPORT_MAP = {
    "NBA": "basketball_nba",
    "NCAAMB": "basketball_ncaab",
    "NFL": "americanfootball_nfl",
    "NHL": "icehockey_nhl",
    "MLB": "baseball_mlb"
}

def get_betting_lines(team1, team2, sport="NCAAMB"):
    """Fetch current betting lines from The Odds API"""
    sport_key = SPORT_MAP.get(sport.upper(), "basketball_ncaab")
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "spreads,totals,h2h",
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
            t1 = team1.lower()
            t2 = team2.lower()
            if (t1 in home or t1 in away or t2 in home or t2 in away):
                games.append(game)
        return games
    except Exception as e:
        return {"error": str(e)}

def format_lines_for_analysis(lines_data, team1, team2):
    """Format betting lines into clean text for the prompt"""
    if not lines_data:
        return "No line data found — verify current lines manually."
    if isinstance(lines_data, dict) and "error" in lines_data:
        return f"Line data error: {lines_data['error']} — verify current lines manually."

    output = []
    for game in lines_data:
        output.append(f"Game: {game.get('away_team')} @ {game.get('home_team')}")
        output.append(f"Commence: {game.get('commence_time', 'TBD')}")
        for bookmaker in game.get("bookmakers", []):
            book_name = bookmaker.get("title", "Unknown")
            for market in bookmaker.get("markets", []):
                if market["key"] == "spreads":
                    for outcome in market.get("outcomes", []):
                        output.append(
                            f"  {book_name} Spread — "
                            f"{outcome['name']}: {outcome['point']:+.1f} "
                            f"({outcome['price']:+d})"
                        )
                elif market["key"] == "totals":
                    for outcome in market.get("outcomes", []):
                        if outcome["name"] == "Over":
                            output.append(
                                f"  {book_name} Total: "
                                f"{outcome['point']} "
                                f"O{outcome['price']:+d}"
                            )
                elif market["key"] == "h2h":
                    for outcome in market.get("outcomes", []):
                        output.append(
                            f"  {book_name} ML — "
                            f"{outcome['name']}: {outcome['price']:+d}"
                        )
    return "\n".join(output) if output else "No matching lines found for these teams."

def collect_all_data(team1, team2, sport, game_date, context):
    """Master function — collects all available data for the game"""
    print(f"Fetching betting lines for {team1} vs {team2}...")
    lines = get_betting_lines(team1, team2, sport)
    formatted_lines = format_lines_for_analysis(lines, team1, team2)
    print("Done.")

    return {
        "team1": team1,
        "team2": team2,
        "sport": sport,
        "game_date": game_date,
        "context": context,
        "betting_lines": formatted_lines,
        "data_timestamp": datetime.now().isoformat()
    }
