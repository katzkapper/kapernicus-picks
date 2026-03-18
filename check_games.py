from batch_analyzer import get_todays_games
from datetime import datetime

print("\nChecking what games The Odds API has today...")
print("="*55)

games = get_todays_games()

if not games:
    print("No games found.")
else:
    print(f"\nTotal games found: {len(games)}\n")
    for i, g in enumerate(games, 1):
        print(f"{i}. {g['away_team']} @ {g['home_team']}")
        print(f"   Spread: {g['spread']}")
        print(f"   Total:  {g['total']}")
        print(f"   ML:     {g['moneyline']}")
        print()

print("="*55)
print("If a game you expected is missing it means:")
print("  1. No lines posted yet on DraftKings/FanDuel/BetMGM")
print("  2. Game is under a different sport key")
print("  3. Game tip-off time puts it on a different date in UTC")
print("="*55)
