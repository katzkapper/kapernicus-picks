from tracker import update_result, load_picks, calculate_stats

def show_pending():
    picks = load_picks()
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
        print(f"     Conf:   {p.get('confidence','—')}%")
        print(f"     Units:  {p.get('units','—')}")

    print(f"\n{'='*55}")


def update_interactively():
    picks  = load_picks()
    pending= [p for p in picks
              if p.get("result") == "PENDING"]

    if not pending:
        print("\nNo pending picks.")
        return

    print("\nEnter result for each pending pick.")
    print("Options: W (win), L (loss), "
          "P (push), S (skip)\n")

    for p in pending:
        print(f"  {p.get('date','—')} | "
              f"{p.get('game','—')}")
        print(f"  {p.get('market','—')}: "
              f"{p.get('pick','—')} "
              f"({p.get('confidence','—')}% — "
              f"{p.get('units','—')}u)")

        while True:
            r = input("  Result (W/L/P/S): ").strip().upper()
            if r in ["W","L","P","S"]:
                break
            print("  Enter W, L, P, or S only")

        if r == "S":
            print("  Skipped.\n")
            continue

        result_map = {"W":"WIN","L":"LOSS","P":"PUSH"}
        update_result(
            p["game"], p["date"],
            result_map[r])
        print(f"  Saved as {result_map[r]}.\n")

    # Show updated stats
    updated_picks = load_picks()
    stats = calculate_stats(updated_picks)

    print(f"\n{'='*55}")
    print(f"  UPDATED RECORD")
    print(f"{'='*55}")
    print(f"  Record:    "
          f"{stats['wins']}-{stats['losses']}"
          f"-{stats['pushes']}")
    print(f"  Win %:     {stats['win_pct']}%")
    print(f"  Net Units: {stats['net_units']:+.2f}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "update":
        # Direct update: python update_results.py update
        # "Duke @ UNC" "March 16, 2026" WIN
        update_result(sys.argv[2],
                      sys.argv[3],
                      sys.argv[4])
    elif "--pending" in sys.argv:
        show_pending()
    else:
        update_interactively()
