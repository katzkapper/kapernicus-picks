import anthropic
import os
import json
import re

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """You are a professional sports betting \
analyst specializing in data-driven game predictions. \
Before making any prediction, you must pull live data, \
verify box scores, and cross-reference all inputs against \
actual rosters.

Follow the complete 32-rule analytical framework provided \
in each user message. Apply every rule explicitly and \
thoroughly.

CONFIDENCE THRESHOLDS:
- Below 57%: state PASS — do not issue a pick
- 57-61%: RECOMMENDED — valid play, 1 unit
- 62%+: HIGH CONFIDENCE — strong play, 1.5 units
- Rule 20 active + 57%+: HIGH CONFIDENCE — 1 unit
- Rule 32 gap 3+ pts + 57%+: HIGH CONFIDENCE — 1.5 units
- Rule 20 AND Rule 32 both active: HIGH CONFIDENCE — 2 units
- Spread confidence below 57% after all adjustments: \
state PASS on spread
- Total confidence below 57% after all adjustments: \
state PASS on total
- Each market is evaluated INDEPENDENTLY
- Issue a Best Bet for every market that clears 57%

CRITICAL INSTRUCTION: You MUST end every response with \
a picks summary block. After your full analysis, on a new \
line write <PICKS> then on the next line write a valid JSON \
object, then on the next line write </PICKS>. Do not put \
anything else inside those tags. The JSON must use this \
exact structure with no missing fields:

<PICKS>
{
  "spread_pick": "Team Name or PASS",
  "spread_line": "-9.5",
  "spread_confidence": 65,
  "spread_recommendation": "BET or PASS or UNDERDOG COVER",
  "total_pick": "Under or Over or PASS",
  "total_line": 141.5,
  "total_confidence": 70,
  "total_recommendation": "BET or PASS",
  "best_bet": "describe the primary best bet here",
  "best_bet_confidence": 70,
  "best_bet_2": "describe the secondary best bet or PASS",
  "best_bet_2_confidence": 65,
  "best_bet_2_market": "SPREAD or TOTAL or PASS",
  "predicted_score": "Team1 75 - Team2 67",
  "rule20_active": false,
  "rule31_active": false,
  "rule32_gap": 0,
  "rule32_underdog_prob": 0,
  "rule32_recommendation": "PASS"
}
</PICKS>

Use only lowercase true/false for booleans. Use only \
numbers (no quotes) for confidence values and gaps. \
Never omit any field."""


def build_user_prompt(game_data, full_model_prompt):
    return f"""{full_model_prompt}

═══════════════════════════════════════════
LIVE DATA FOR THIS GAME
═══════════════════════════════════════════

GAME: {game_data['team1']} (Away) vs \
{game_data['team2']} (Home)
DATE: {game_data['game_date']}
SPORT: {game_data['sport']}
CONTEXT: {game_data['context']}
DATA PULLED AT: {game_data['data_timestamp']}

CURRENT BETTING LINES:
{game_data['betting_lines']}

INSTRUCTIONS:
1. Use the betting lines above as your starting point
2. Use web search to find and verify:
   - Current injury reports (within 48 hours)
   - Last 5 game results and box scores
   - H2H history with verified box scores
   - KenPom/NET rankings for both teams
   - Any lineup changes in the last 3 days
3. Apply all 32 rules explicitly in sequence
4. Generate the complete report
5. You MUST end with the <PICKS> JSON block

REMINDER: End your response with the <PICKS> block. \
It is mandatory."""


def run_analysis(game_data, full_model_prompt):
    import threading

    print("  [0:00] Sending to Claude "
          "(60-120 seconds)...")

    def print_progress():
        import time
        intervals = [30, 60, 90, 120, 150, 180]
        for seconds in intervals:
            time.sleep(30)
            print(f"  [{seconds//60}:"
                  f"{seconds%60:02d}] "
                  f"Still waiting...")

    progress_thread = threading.Thread(
        target=print_progress, daemon=True)
    progress_thread.start()

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user",
                 "content": build_user_prompt(
                     game_data, full_model_prompt)}
            ]
        )
        full_response = response.content[0].text
        print("  Analysis complete.")
        picks = extract_picks(full_response)
        if picks.get("parse_failed"):
            print("  Parse failed — trying recovery...")
            picks = extract_picks_fallback(
                full_response)
        return {
            "full_analysis": full_response,
            "picks":         picks,
            "usage": {
                "input_tokens":
                    response.usage.input_tokens,
                "output_tokens":
                    response.usage.output_tokens
            }
        }
    except Exception as e:
        return {
            "error":         str(e),
            "full_analysis": f"Analysis failed: {e}",
            "picks":         {}
        }


def extract_picks(response_text):
    try:
        match = re.search(
            r'<PICKS>\s*(.*?)\s*</PICKS>',
            response_text, re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('\n', ' ')
            raw = re.sub(r',\s*}', '}', raw)
            raw = re.sub(r',\s*]', ']', raw)
            return json.loads(raw)
    except Exception as e:
        print(f"  Primary parse error: {e}")
    return {"parse_failed": True}


def extract_picks_fallback(response_text):
    try:
        matches = list(re.finditer(
            r'\{[^{}]+\}',
            response_text, re.DOTALL))
        if matches:
            for match in reversed(matches[-5:]):
                try:
                    candidate = match.group(0)
                    parsed    = json.loads(candidate)
                    if any(k in parsed for k in [
                        "spread_pick", "total_pick",
                        "best_bet",
                        "spread_recommendation"
                    ]):
                        print(
                            "  Fallback parse succeeded.")
                        return parsed
                except Exception:
                    continue
    except Exception as e:
        print(f"  Fallback parse error: {e}")
    print("  Using text extraction as last resort.")
    return extract_picks_from_text(response_text)


def extract_picks_from_text(text):
    picks = {
        "spread_pick":           "See analysis",
        "spread_line":           "—",
        "spread_confidence":     0,
        "spread_recommendation": "See analysis",
        "total_pick":            "See analysis",
        "total_line":            0,
        "total_confidence":      0,
        "total_recommendation":  "See analysis",
        "best_bet":              "See full analysis",
        "best_bet_confidence":   0,
        "best_bet_2":            "PASS",
        "best_bet_2_confidence": 0,
        "best_bet_2_market":     "PASS",
        "predicted_score":       "See analysis",
        "rule20_active":         False,
        "rule31_active":         False,
        "rule32_gap":            0,
        "rule32_underdog_prob":  0,
        "rule32_recommendation": "See analysis"
    }

    text_lower = text.lower()

    if ("sharp fade in effect" in text_lower or
            ("rule 20" in text_lower and
             "triggered" in text_lower)):
        picks["rule20_active"] = True

    if ("rule 31 active" in text_lower or
            "star absorption" in text_lower):
        picks["rule31_active"] = True

    bb = re.search(
        r'best bet[:\s]+([^\n]+)',
        text, re.IGNORECASE)
    if bb:
        picks["best_bet"] = bb.group(1).strip()[:80]

    sc = re.search(
        r'predicted score[:\s]+([^\n]+)',
        text, re.IGNORECASE)
    if sc:
        picks["predicted_score"] = \
            sc.group(1).strip()

    if ("best bet" in text_lower and
            "under" in text_lower):
        picks["total_pick"]           = "Under"
        picks["total_recommendation"] = "BET"
    elif ("best bet" in text_lower and
          "over" in text_lower):
        picks["total_pick"]           = "Over"
        picks["total_recommendation"] = "BET"

    if ("pass" in text_lower and
            "spread" in text_lower):
        picks["spread_recommendation"] = "PASS"
        picks["spread_pick"]           = "PASS"

    bb2 = re.search(
        r'best bet[^:]*2[^:]*:[^\n]+|'
        r'best bet[^:]*total[:\s]+([^\n]+)|'
        r'best bet[^:]*spread[:\s]+([^\n]+)',
        text, re.IGNORECASE)
    if bb2:
        matched = (bb2.group(1) or
                   bb2.group(2) or "")
        if matched.strip():
            picks["best_bet_2"] = \
                matched.strip()[:80]

    return picks
