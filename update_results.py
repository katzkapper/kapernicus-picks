import sys
import time
from tracker import (
    update_result, load_picks,
    calculate_stats, save_picks
)
from twitter_poster import post_tweet


def build_result_tweet(pick, result, stats):
    """
    Build a result tweet for a settled pick.
    """
    if result == "WIN":
        emoji  = "✅"
        label  = "WIN"
    elif result == "LOSS":
        emoji  = "❌"
        label  = "LOSS"
    else:
        emoji  = "➡️"
        label  = "PUSH"

    units     = pick.get("units", 1)
    conf      = pick.get("confidence", 0)
    game      = pick.get("game", "—")
    market    = pick.get("market", "—")
    pick_name = pick.get("pick", "—")
    date      = pick.get("date", "—")

    # Net units on this pick
    if result == "WIN":
        net = f"+{round(units * 0.909, 2)}u"
    elif result == "LOSS":
        net = f"-{units}u"
    else:
        net = "0u (push)"

    # Overall record
    w   = stats["wins"]
    l   = stats["losses"]
    p   = stats["pushes"]
    pct = stats["win_pct"]
    net_total = stats["net_units"]
    net_sign  = "+" if net_total >= 0 else ""

    # Rule flags
    flags = []
    if pick.get("rule20"):
        flags.append("R20")
    if pick.get("rule31"):
        flags.append("R31")
    flag_str = (
        f" [{', '.join(flags)}]"
        if flags else ""
    )

    lines = [
        f"{emoji} RESULT — Kapernicus Picks",
        f"",
        f"🏀 {game}",
        f"📌 {market}: {pick_name}{flag_str}",
        f"📊 {conf}% confidence | {units}u",
        f"",
        f"Result: {label} ({net})",
        f"Record: {w}-{l}-{p} "
        f"| {pct}% "
        f"| {net_sign}{net_total}u",
        f"",
        f"#SportsBetting #NCAAB #KapernikusPicks"
    ]

    tweet = "\n".join(lines)

    # Trim if over 280 chars
    if len(tweet) > 280:
        lines = [
            f"{emoji} RESULT — Kapernicus Picks",
            f"",
            f"🏀 {game}",
            f"📌 {pick_name}",
            f"Result: {label} ({net})",
            f"Record: {w}-{l} | {pct}% "
            f"| {net_sign}{net_total}u",
            f"",
            f"#SportsBetting #NCAAB"
        ]
        tweet = "\n".join(lines)

    return tweet[:280]


def show_pending():
    picks   = load_picks()
    pending = [p for p in picks
               if p.get("result") == "PENDING"]

    if not pending:
        print("\nNo pending picks to update.")
        return

    print(f"\n{'='*55}")
    print(f"  PENDING PICKS ({len(pending)} total)")
    print(f"{'='*55}")

    for i, p in enumerate(pending, 1):
        print(f"\n  {i}. {p.get('date','—')} | "
              f"{p.get('game','—')}")
        print(f"     Market: {p.get('market','—')}")
        print(f"     Pick:   {p.get('pick','—')}")
        print(f"     Conf:   "
              f"{p.get('confidence','—')}%")
        print(f"     Units:  {p.get('units','—')}")

    print(f"\n{'='*55}")


def update_interactively():
    picks   = load_picks()
    pending = [p for p in picks
               if p.get("result") == "PENDING"]

    if not pending:
        print("\nNo pending picks to update.")
        return

    print(f"\n{'='*55}")
    print("  ENTER RESULTS")
    print(f"{'='*55}")
    print("  W = Win  |  L = Loss  |  "
          "P = Push  |  S = Skip\n")

    result_map = {
        "W": "WIN",
        "L": "LOSS",
        "P": "PUSH"
    }

    updated_count = 0

    for pick in pending:
        print(f"  {pick.get('date','—')} | "
              f"{pick.get('game','—')}")
        print(f"  {pick.get('market','—')}: "
              f"{pick.get('pick','—')} "
              f"({pick.get('confidence','—')}% — "
              f"{pick.get('units','—')}u)")

        while True:
            r = input(
                "  Result (W/L/P/S): "
            ).strip().upper()
            if r in ["W", "L", "P", "S"]:
                break
            print("  Enter W, L, P, or S only")

        if r == "S":
            print("  Skipped.\n")
            continue

        result = result_map[r]

        # Update the pick in the file
        all_picks = load_picks()
        for p in all_picks:
            if (p.get("game","").lower() ==
                    pick.get("game","").lower() and
                    p.get("date","") ==
                    pick.get("date","") and
                    p.get("result") == "PENDING" and
                    p.get("pick","") ==
                    pick.get("pick","")):
                p["result"] = result
                break
        save_picks(all_picks)
        updated_count += 1

        # Get updated stats for the tweet
        updated_picks = load_picks()
        stats = calculate_stats(updated_picks)

        # Show what was saved
        if result == "WIN":
            net = (f"+{round(pick.get('units',1)"
                   f" * 0.909, 2)}u")
        elif result == "LOSS":
            net = f"-{pick.get('units',1)}u"
        else:
            net = "0u"

        print(f"  Saved as {result} ({net})\n")

        # Post result tweet
        print(f"  Posting result to X...")
        tweet = build_result_tweet(
            pick, result, stats)

        print(f"  Tweet preview:")
        print("  " + tweet.replace("\n", "\n  "))

        tweet_id = post_tweet(tweet)

        if tweet_id:
            print(f"  ✓ Result posted to X\n")
        else:
            print(f"  ✗ Tweet failed — "
                  f"result still saved to tracker\n")

        # Small delay between tweets
        time.sleep(3)

    # ── FINAL SUMMARY ──
    final_picks = load_picks()
    stats       = calculate_stats(final_picks)

    print(f"\n{'='*55}")
    print(f"  UPDATED RECORD")
    print(f"{'='*55}")
    print(f"  Picks updated:  {updated_count}")
    print(f"  Record:         "
          f"{stats['wins']}-"
          f"{stats['losses']}-"
          f"{stats['pushes']}")
    print(f"  Win %:          {stats['win_pct']}%")

    net       = stats['net_units']
    net_sign  = "+" if net >= 0 else ""
    print(f"  Net Units:      {net_sign}{net}u")
    print(f"  Pending:        {stats['pending']}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    if "--pending" in sys.argv:
        show_pending()
    elif (len(sys.argv) >= 5 and
              sys.argv[1] == "update"):
        # Direct update from command line:
        # python update_results.py update
        # "Duke @ UNC" "March 16, 2026" WIN
        update_result(
            sys.argv[2],
            sys.argv[3],
            sys.argv[4]
        )
    else:
        update_interactively()
