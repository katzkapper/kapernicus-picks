import anthropic
import os
import json
import re

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """You are a professional sports betting analyst specializing in data-driven game predictions. Before making any prediction, you must pull live data, verify box scores, and cross-reference all inputs against actual rosters.

Follow the complete 32-rule analytical framework provided in each user message. Apply every rule explicitly and thoroughly.

At the very end of your full report, output a structured JSON summary enclosed in <PICKS> tags exactly like this — no other text inside the tags, valid JSON only:

<PICKS>
{
  "spread_pick": "Team Name or PASS",
  "spread_line": "-9.5",
  "spread_confidence": 65,
  "spread_recommendation": "BET or PASS or UNDERDOG COVER or VALUE LEAN",
  "total_pick": "Under or Over or PASS",
  "total_line": 141.5,
  "total_confidence": 70,
  "total_recommendation": "BET or PASS",
  "best_bet": "Under 141.5 or PASS",
  "best_bet_confidence": 70,
  "predicted_score": "Team1 75 - Team2 67",
  "rule20_active": false,
  "rule31_active": false,
  "rule32_gap": 2.5,
  "rule32_underdog_prob": 54,
  "rule32_recommendation": "VALUE LEAN or UNDERDOG COVER or PASS"
}
</PICKS>"""

def build_user_prompt(game_data, full_model_prompt):
    """Combine live game data with the full analytical prompt"""
    return f"""{full_model_prompt}

═══════════════════════════════════════════
LIVE DATA FOR THIS GAME
═══════════════════════════════════════════

GAME: {game_data['team1']} (Away) vs {game_data['team2']} (Home)
DATE: {game_data['game_date']}
SPORT: {game_data['sport']}
CONTEXT: {game_data['context']}
DATA PULLED AT: {game_data['data_timestamp']}

CURRENT BETTING LINES (from The Odds API):
{game_data['betting_lines']}

INSTRUCTIONS:
1. Use the betting lines above as your starting point
2. Use your web search capability to find and verify:
   - Current injury reports for both teams (within 48 hours)
   - Last 5 game results and box scores for both teams
   - H2H history with verified box scores
   - KenPom/NET rankings for both teams
   - Any lineup changes or roster news in the last 3 days
3. Apply all 32 rules explicitly in sequence
4. Generate the complete report following the Step 7 deliverable format
5. Output the structured PICKS JSON at the end inside <PICKS> tags
"""

def run_analysis(game_data, full_model_prompt):
    """Send data to Claude and get the full analysis"""
    print("Sending to Claude for analysis (this takes 60-120 seconds)...")

    user_message = build_user_prompt(game_data, full_model_prompt)

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        full_response = response.content[0].text
        print("Analysis complete.")

        picks = extract_picks(full_response)

        return {
            "full_analysis": full_response,
            "picks": picks,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }

    except Exception as e:
        return {
            "error": str(e),
            "full_analysis": f"Analysis failed: {str(e)}",
            "picks": {}
        }

def extract_picks(response_text):
    """Pull the structured picks JSON out of the response"""
    try:
        match = re.search(r'<PICKS>(.*?)</PICKS>', response_text, re.DOTALL)
        if match:
            picks_json = match.group(1).strip()
            return json.loads(picks_json)
    except Exception:
        pass
    return {
        "spread_pick": "See analysis",
        "total_pick": "See analysis",
        "best_bet": "See full analysis — JSON parse failed",
        "spread_confidence": 0,
        "total_confidence": 0,
        "best_bet_confidence": 0,
        "predicted_score": "See analysis",
        "rule20_active": False,
        "rule31_active": False,
        "rule32_gap": 0,
        "rule32_underdog_prob": 0,
        "rule32_recommendation": "See analysis"
    }
