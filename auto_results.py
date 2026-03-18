import os
import json
import requests
from datetime import datetime, timedelta
from tracker import load_picks, save_picks, calculate_stats
from twitter_poster import post_tweet

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
SPORT_KEY    = "basketball_ncaab"


def fetch_completed_scores(date_str=None):
    """
    Fetch completed game scores from The Odds API.
    date_str format: 'March 15, 2026'
    If None uses yesterday's date since games
    finish late and results are checked next morning.
    """
    url = (f"https://api.the-odds-api.com/v4"
           f"/sports/{SPORT_KEY}/scores/")

    params = {
        "apiKey":        ODDS_API_KEY,
        "daysFrom":      1,
        "dateFormat":    "iso"
    }

    print("Fetching completed scores "
          "from The Odds API...")

    try:
        response = requests.get(
            url, params=params, timeout=15)
        data = response.json()

        if isinstance(data, dict) and \
                "message" in data:
            print(f"  API error: {data['message']}")
            return []

        # Filter for completed games only
        completed = [
            g for g in data
            if g.get("completed") is True
        ]

        print(f"  Found {len(completed)} "
              f"completed games.")
        return completed

    except Exception as e:
        print(f"  Error fetching scores: {e}")
        return []


def find_matching_game(pick_game, completed_games):
    """
    Match a pick's game label to a completed game
    from the API. Uses fuzzy team name matching.
    """
    pick_lower = pick_game.lower()

    # Extract team names from pick label
    # Format is "Away @ Home"
    parts = pick_lower.split(" @ ")
    if len(parts) != 2:
        parts = pick_lower.split(" vs ")
    if len(parts) != 2:
        return None

    away_search = parts[0].strip()
    home_search = parts[1].strip()

    # Get last word of each team name
    # e.g. "purdue boilermakers" → "boilermakers"
    away_key = away_search.split()[-1]
    home_key = home_search.split()[-1]

    for game in completed_games:
        home = game.get("home_team","").lower()
        away = game.get("away_team","").lower()

        # Check if team names match
        home_match = (
            home_key in home or
            away_search in home or
            home.split()[-1] in away_search or
            any(w in home for w in
                away_search.split() if len(w) > 4)
        )
        away_match = (
            away_key in away or
            home_search in away or
            away.split()[-1] in home_search or
            any(w in away for w in
                home_search.split() if len(w) > 4)
        )

        # Also try direct name matching
        direct_home = (
            home_search in home or
            home in home_search
        )
        direct_away = (
            away_search in away or
            away in away_search
        )

        if (home_match and away_match) or \
                (direct_home and direct_away):
            return game

    return None


def get_final_scores(game):
    """
    Extract final scores from a completed game dict.
    Returns (home_score, away_score) or (None, None).
    """
    scores = game.get("scores")
    if not scores:
        return None, None

    home_team = game.get("home_team","")
    home_score = None
    away_score = None

    for score in scores:
        name  = score.get("name","")
        value = score.get("score")
        try:
            pts = int(value)
        except (TypeError, ValueError):
            continue

        if name == home_team:
            home_score = pts
        else:
            away_score = pts

    return home_score, away_score


def determine_spread_result(pick, home_score,
                             away_score, game):
    """
    Determine WIN/LOSS/PUSH for a spread pick.
    """
    home_team = game.get("home_team","").lower()
    pick_text = pick.get("pick","").lower()
    line_str  = str(pick.get("pick",""))

    # Extract the spread number from the pick text
    # Pick format examples:
    # "Michigan -1.5" or "Purdue +3.5"
    import re
    spread_match = re.search(
        r'([+-]?\d+\.?\d*)\s*$', line_str)
    if not spread_match:
        return None

    spread = float(spread_match.group(1))

    # Determine which team was picked
    # and what the actual margin was
    margin = home_score - away_score

    # Is the pick on the home team or away team
    home_team_words = home_team.split()
    pick_is_home = any(
        w in pick_text
        for w in home_team_words
        if len(w) > 3
    )

    if pick_is_home:
        # Picked home team
        # Home team covers if margin > -spread
        # (spread is negative for home favorite)
        covered_margin = margin + spread
    else:
        # Picked away team
        # Away covers if (-margin) > -spread
        covered_margin = (-margin) + spread

    if covered_margin > 0:
        return "WIN"
    elif covered_margin < 0:
        return "LOSS"
    else:
        return "PUSH"


def determine_total_result(pick, home_score,
                            away_score):
    """
    Determine WIN/LOSS/PUSH for an over/under pick.
    """
    import re
    pick_text  = pick.get("pick","").lower()
    line_str   = str(pick.get("pick",""))
    actual_total = home_score + away_score

    # Extract the total line number
    line_match = re.search(
        r'(\d+\.?\d*)', line_str)
    if not line_match:
        return None

    line = float(line_match.group(1))

    if "under" in pick_text:
        if actual_total < line:
            return "WIN"
        elif actual_total > line:
            return "LOSS"
        else:
            return "PUSH"
    else:  # over
        if actual_total > line:
            return "WIN"
        elif actual_total < line:
            return "LOSS"
        else:
            return "PUSH"
