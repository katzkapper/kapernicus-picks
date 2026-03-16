import os
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
from datetime import datetime
from confidence_utils import (
    get_confidence_tier, get_unit_size,
    format_unit_label, get_tier_label
)

# ─────────────────────────────────────────────────────────────
# X (TWITTER) API CREDENTIALS
# ─────────────────────────────────────────────────────────────
X_API_KEY      = os.environ.get("X_API_KEY", "")
X_API_SECRET   = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET= os.environ.get("X_ACCESS_SECRET", "")

TWEET_URL = "https://api.twitter.com/2/tweets"

# ─────────────────────────────────────────────────────────────
# MINIMUM UNITS TO POST
# Only posts plays at this unit size or above
# ─────────────────────────────────────────────────────────────
MIN_UNITS_TO_POST = 1.0


def _oauth_header(method, url, params):
    """Build OAuth 1.0a authorization header for X API v2."""
    oauth_params = {
        "oauth_consumer_key":     X_API_KEY,
        "oauth_nonce":            base64.b64encode(
            os.urandom(32)).decode("utf-8").replace(
                "+","").replace("/","").replace("=","")[:32],
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        str(int(time.time())),
        "oauth_token":            X_ACCESS_TOKEN,
        "oauth_version":          "1.0",
    }

    # Combine all params for signature base string
    all_params = {**oauth_params, **params}
    sorted_params = "&".join(
        f"{urllib.parse.quote(str(k), safe='')}"
        f"={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )

    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(sorted_params, safe="")
    ])

    signing_key = (
        f"{urllib.parse.quote(X_API_SECRET, safe='')}"
        f"&"
        f"{urllib.parse.quote(X_ACCESS_SECRET, safe='')}"
    )

    signature = base64.b64encode(
        hmac.new(
            signing_key.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha1
        ).digest()
    ).decode("utf-8")

    oauth_params["oauth_signature"] = signature

    header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(str(k), safe="")}='
        f'"{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )

    return header


def build_tweet_text(game_label, pick, conf,
                     market, units, picks_dict):
    """
    Build the tweet text for a single pick.
    Stays under 280 characters.
    """
    tier  = get_tier_label(conf, picks_dict)
    stars = "⭐⭐" if tier == "HIGH CONFIDENCE" else "⭐"

    # Rule flags
    flags = []
    if picks_dict.get("rule20_active"):
        flags.append("🔴 Sharp Fade")
    if picks_dict.get("rule31_active"):
        flags.append("⚠️ R31")
    try:
        gap = float(str(
            picks_dict.get("rule32_gap", 0)
        ).replace("—","0") or 0)
        if gap >= 3:
            flags.append(f"📊 R32 Gap {gap}pts")
    except (ValueError, TypeError):
        pass

    flag_str = " | ".join(flags)
    date_str = datetime.now().strftime("%b %d")

    # Build the tweet
    lines = [
        f"{stars} KAPERNICUS PICKS — {date_str}",
        f"",
        f"🏀 {game_label}",
        f"📌 {market}: {pick}",
        f"📈 Confidence: {conf}%",
        f"💰 Units: {units}",
    ]

    if flag_str:
        lines.append(f"🚩 {flag_str}")

    lines.append("")
    lines.append("#SportsBetting #NCAAB #KapernikusPicks")

    tweet = "\n".join(lines)

    # Trim if over 280 characters
    if len(tweet) > 280:
        lines[-1] = "#SportsBetting #NCAAB"
        tweet = "\n".join(lines)

    if len(tweet) > 280:
        # Last resort — drop flags
        lines = [
            f"{stars} KAPERNICUS PICKS — {date_str}",
            f"",
            f"🏀 {game_label}",
            f"📌 {market}: {pick}",
            f"📈 {conf}% | 💰 {units}",
            f"",
            f"#SportsBetting #NCAAB"
        ]
        tweet = "\n".join(lines)

    return tweet[:280]


def post_tweet(text):
    """Post a single tweet using X API v2."""
    if not all([X_API_KEY, X_API_SECRET,
                X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        print("  X credentials not set — skipping tweet")
        return False

    payload = {"text": text}
    header  = _oauth_header(
        "POST", TWEET_URL, {})

    try:
        response = requests.post(
            TWEET_URL,
            headers={
                "Authorization":  header,
                "Content-Type":   "application/json"
            },
            json=payload,
            timeout=15
        )

        if response.status_code in [200, 201]:
            data = response.json()
            tweet_id = data.get("data", {}).get("id","")
            print(f"  ✓ Tweet posted (ID: {tweet_id})")
            return tweet_id
        else:
            print(f"  ✗ Tweet failed: "
                  f"{response.status_code} "
                  f"{response.text[:100]}")
            return False

    except Exception as e:
        print(f"  ✗ Tweet error: {e}")
        return False


def post_picks_from_batch(all_results, target_date):
    """
    Called after batch analysis completes.
    Posts one tweet per qualifying pick (>= 1 unit).
    Handles both Best Bet 1 and Best Bet 2.
    Waits 5 seconds between tweets to avoid rate limits.
    Returns list of posted picks for the tracker.
    """
    if not all([X_API_KEY, X_API_SECRET,
                X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        print("\n  X posting skipped — "
              "credentials not set in Secrets")
        return []

    posted = []
    tweet_count = 0

    print(f"\n{'='*60}")
    print("  POSTING PICKS TO X")
    print(f"{'='*60}")

    for result in all_results:
        picks     = result.get("picks", {})
        game_label= result.get("game_label","Unknown")

        # ── BEST BET 1 ──
        conf1 = picks.get("best_bet_confidence", 0)
        bb1   = picks.get("best_bet","")
        if (isinstance(conf1, int) and
                bb1 and
                str(bb1).upper() != "PASS" and
                bb1 != "—"):

            units1 = get_unit_size(conf1, picks)

            if units1 >= MIN_UNITS_TO_POST:
                # Determine market label
                sp_rec = str(picks.get(
                    "spread_recommendation","")).upper()
                tc_rec = str(picks.get(
                    "total_recommendation","")).upper()
                if "BET" in sp_rec or "COVER" in sp_rec:
                    market1 = "SPREAD"
                elif "BET" in tc_rec:
                    market1 = "TOTAL"
                else:
                    market1 = "BEST BET"

                u1_label = format_unit_label(conf1, picks)
                tweet1   = build_tweet_text(
                    game_label, bb1, conf1,
                    market1, u1_label, picks)

                print(f"\n  Game: {game_label}")
                print(f"  BB1:  {bb1} "
                      f"({conf1}% — {u1_label})")
                print(f"  Tweet preview:")
                print("  " + tweet1.replace(
                    "\n", "\n  "))

                tweet_id = post_tweet(tweet1)

                if tweet_id:
                    tweet_count += 1
                    posted.append({
                        "date":      target_date,
                        "game":      game_label,
                        "market":    market1,
                        "pick":      bb1,
                        "confidence":conf1,
                        "units":     units1,
                        "tier":      get_tier_label(
                            conf1, picks),
                        "tweet_id":  tweet_id,
                        "result":    "PENDING",
                        "rule20":    picks.get(
                            "rule20_active", False),
                        "rule31":    picks.get(
                            "rule31_active", False),
                        "rule32_gap":picks.get(
                            "rule32_gap", 0),
                    })
                    time.sleep(5)

        # ── BEST BET 2 ──
        conf2 = picks.get("best_bet_2_confidence", 0)
        bb2   = picks.get("best_bet_2","PASS")
        bm2   = picks.get("best_bet_2_market","TOTAL")

        if (isinstance(conf2, int) and
                conf2 >= 57 and
                bb2 and
                str(bb2).upper() != "PASS" and
                bb2 != "—"):

            units2 = get_unit_size(conf2, picks)

            if units2 >= MIN_UNITS_TO_POST:
                u2_label = format_unit_label(conf2, picks)
                tweet2   = build_tweet_text(
                    game_label, bb2, conf2,
                    bm2, u2_label, picks)

                print(f"\n  Game: {game_label}")
                print(f"  BB2:  {bb2} "
                      f"({conf2}% — {u2_label}) [{bm2}]")
                print(f"  Tweet preview:")
                print("  " + tweet2.replace(
                    "\n", "\n  "))

                tweet_id2 = post_tweet(tweet2)

                if tweet_id2:
                    tweet_count += 1
                    posted.append({
                        "date":      target_date,
                        "game":      game_label,
                        "market":    bm2,
                        "pick":      bb2,
                        "confidence":conf2,
                        "units":     units2,
                        "tier":      get_tier_label(
                            conf2, picks),
                        "tweet_id":  tweet_id2,
                        "result":    "PENDING",
                        "rule20":    picks.get(
                            "rule20_active", False),
                        "rule31":    picks.get(
                            "rule31_active", False),
                        "rule32_gap":picks.get(
                            "rule32_gap", 0),
                    })
                    time.sleep(5)

    print(f"\n  Total tweets posted: {tweet_count}")
    print(f"{'='*60}\n")
    return posted
