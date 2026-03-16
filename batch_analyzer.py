import os
import json
import time
import requests
from datetime import datetime, timezone
from analyzer import run_analysis
from report_generator import generate_pdf_report
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from confidence_utils import (
    get_confidence_tier, get_unit_size,
    format_unit_label, get_tier_label,
    HIGH_CONF_FLOOR, RECOMMENDED_FLOOR,
    RULE32_STAR_GAP, MODEL_PASS_FLOOR
)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

# ─────────────────────────────────────────────────────────────
# PASTE YOUR COMPLETE 32-RULE PROMPT BETWEEN THE TRIPLE QUOTES
# ─────────────────────────────────────────────────────────────
FULL_MODEL_PROMPT = """
You are a professional sports betting analyst specializing in data-driven game predictions. Before making any prediction, you must pull live data, verify box scores, and cross-reference all inputs against actual rosters.

═══════════════════════════════════════════
CONFIDENCE THRESHOLDS AND UNIT SIZING
═══════════════════════════════════════════
- Below 57%: state PASS — do not issue a pick
- 57-61%: RECOMMENDED — valid play, 1 unit
- 62%+: HIGH CONFIDENCE — strong play, 1.5 units
- Rule 20 active + 57%+: HIGH CONFIDENCE — 1 unit
- Rule 32 gap 3+ pts + 57%+: HIGH CONFIDENCE — 1.5 units
- Rule 20 AND Rule 32 both active: HIGH CONFIDENCE — 2 units
- Spread confidence below 57% after all adjustments: state PASS on spread
- Total confidence below 57% after all adjustments: state PASS on total
- Each market is evaluated INDEPENDENTLY — a PASS on one does not affect the other
- Issue a Best Bet for every market that independently clears 57%

═══════════════════════════════════════════
STEP 1 — DATA COLLECTION (Do this before any analysis)
═══════════════════════════════════════════
Pull and verify ALL of the following before writing a single word of analysis:

A. LIVE/CURRENT DATA

- Fetch today's live scores and game data from the sports data tool
- Fetch full standings for the relevant league
- Show what the opening lines were set at and document ALL movement to the current line. Apply Rule 20 (Sharp Line Override) BEFORE writing any other analysis — line movement direction must be established first and may override all downstream confidence outputs. NOTE v5: Rule 20 triggers on ANY confirmed closing-line compression below the opening at ANY major book (DraftKings, FanDuel, BetMGM, bet365). Cross-book unanimity is NOT required. In thin/low-handle markets, a single major book moving below the opening number is sufficient. There is no "partial" Rule 20 classification.
- Search for the latest injury reports (within 48 hours of tip-off)
- Search for each team's last 5 game results and box scores
- Search for any lineup changes, coach news, or locker room reports — emphasize the past three days

B. HEAD-TO-HEAD AUDIT (CRITICAL)

- Pull the actual box score from every H2H matchup cited
- Verify which players appeared in each H2H game
- Flag any H2H game where a key player was absent
- If a star player missed a prior H2H game, mark that result with an asterisk and reduce its weight by 70%
- RULE 10: Do NOT assume a neutral-court margin will be wider than a road H2H margin. Neutral projection = Road H2H margin + 2-3 pts only. Never multiply the existing H2H margin.
- RULE 23 HOME COURT H2H DISCOUNT: If a cited H2H result occurred at one team's true home court (not a neutral site), apply a 45% discount to the margin for neutral-court projection purposes. A 17-point home win projects to +5-7 neutral at most. Do NOT carry the full home-court margin forward as neutral-site evidence.

C. BOX SCORE VERIFICATION

- Do not use season averages alone — pull each team's last 3 box scores
- Extract first-half vs. second-half shooting splits for both teams
- Note bench scoring totals (not just starters) for both teams
- Record turnovers by player name, not just team totals
- RULE 8: Pull offensive rebounding rate and points-in-paint for both teams from last 3 box scores. Calculate the expected paint-point differential explicitly — produce a numeric estimate. RULE 29 BILATERAL OR PARITY CHECK (v5): If both teams rank in the top 3 of their conference in offensive rebounding, the OR differential credit defaults to +0 unless actual H2H OR box score data is available. Season rank vs. season rank in the same conference provides no net edge.
- RULE 9: For each team's 2nd, 3rd, and 4th scorers, calculate their scoring standard deviation across the last 5 games. If any non-primary scorer averages 12+ PPG with a std dev of 7+ pts, flag as HIGH VARIANCE and widen the spread confidence interval by +/-4 pts. v5 ADDITION: Also model the FLOOR case — if this player has a cold game at 50% or less of their average, what is the resulting team FG% and projected total? Include this floor scenario in the total range model.
- RULE 31 — STAR ABSORPTION CEILING (v6): When a team's primary scorer is confirmed absent AND a single remaining player is projected to absorb 35%+ of that team's scoring load in an elimination or must-win game, you MUST model an explicit ceiling scenario for that absorbing player. Pull their single-game scoring maximum from the last 10 games. Model their top-quartile output (75th percentile of recent games) as the ceiling input. Do NOT use their season average as the total projection anchor for that team. Widen the total range upward by +15 to +20 pts on the ceiling scenario. Do NOT recommend the Under unless the base case projected total is at least 10 pts BELOW the line. If the base case is within 10 pts of the line, the total recommendation must be PASS — not Under. NOTE: Rule 12 (FRAGILE flag) addresses spread risk from single-star dependency. Rule 31 addresses the OPPOSITE total risk — the absorbing star going supernova produces ceiling scoring, not average scoring. Both rules must be applied simultaneously when a primary scorer is absent.

D. 3-POINT VARIANCE AUDIT (required for every game)

- Record each team's 3PT% in their last 3 games individually
- Calculate the variance (range between high and low game)
- If variance exceeds 15 percentage points across last 3 games, flag the team as HIGH 3PT VARIANCE
- Apply the ceiling check BILATERALLY: check both teams' 3PT ceiling
- For teams shooting above 37% from 3 in recent play, model a realistic upside scenario (top-quartile game = ~47-50%) in the total range estimate

E. BENCH WILDCARD AUDIT — RULE 17 (required for every game)

- For EVERY bench player on both rosters, pull their single-game scoring MAX from the last 10 games
- If any bench player has scored 20+ points in ANY game in the last 10, flag them as a BENCH WILDCARD
- Apply the BENCH WILDCARD flag BILATERALLY — check both teams
- When a BENCH WILDCARD exists: widen spread confidence interval by +/-3 pts and reduce the opposing team's cover probability by 4%
- Do NOT classify any player as merely a "role player" without first checking their scoring ceiling

F. TURNOVER CEILING AUDIT — RULE 18 (required for every game)

- For each team, pull their single-game turnover MAX from the last 10 games
- If any team has committed 15+ turnovers in ANY game in their last 10, flag them as HIGH-TO-CEILING risk
- When HIGH-TO-CEILING is triggered: reduce that team's projected scoring by 8-10 pts in the high-TO scenario, widen spread CI +/-3 pts, and reduce that team's cover probability by 5%
- Cross-reference individual player TO history — any player with 5+ TOs in any recent game is a personal TO-ceiling flag

G. FREE THROW GENERATION AUDIT — RULE 19 (required for every game)

- Pull each team's FTA per game over their last 5 games
- Pull each team's national/conference rank in FT made or FTA
- Calculate the projected FTA differential for this matchup
- A team ranked top-30 nationally in FT made receives a +1.5 spread-pt credit
- A team with an FTA differential of +8 or more receives an additional +1.0 spread-point credit
- Flag any team that under-generates FTAs as FT-DISADVANTAGED
- RULE 30 CONTEXT CHECK (v5): Before applying any FT credit, check whether the opposing defense fouls infrequently (top-20 fewest fouls allowed). If YES, reduce the FT credit by 50% and state this explicitly.
- RULE 31 INTERACTION: When Rule 31 is active (star absent, absorbing player carrying 35%+ load), include the absorbing player's FTA rate under high-usage conditions in the total projection. A player taking 35%+ of shots in an elimination game will draw significantly more fouls than their season FTA average. Apply a 25% upward adjustment to that player's projected FTA in the total model.

H. SECOND-HALF FATIGUE AUDIT — RULE 25 (required for every game)

- Identify whether either team is playing their 3rd game in 3 days
- If YES: apply a mandatory 2nd-half scoring reduction of 5-8% to the team with the shallower depth chart
- If a 2nd-half scoring dip was observed in that team's prior (Game 2-of-3) game, treat it as a 60% probability of recurrence in Game 3
- Flag the affected team as BACK-TO-BACK-TO-BACK FATIGUE RISK
- v5 AMENDMENT: Apply this flag ASYMMETRICALLY ONLY. If both teams played the prior night, fatigue is roughly neutralized and must NOT be applied as a one-sided advantage for either team.

I. RECENT OFFENSIVE EFFICIENCY CONTEXT AUDIT — RULE 28 (v5, required every game)

- For each team's last 3 box scores, identify the defensive quality of opponents faced (KenPom/NET rank)
- If a team's recent offensive efficiency was generated against defenses ranked outside the top 40 nationally, apply a 15% discount to those efficiency figures when projecting against a top-40 defense
- State explicitly: "Team X's recent FG% of Y% was generated against defenses ranked [Z avg] — applying 15% discount vs. this opponent's [rank] defense. Revised projection: [Y x 0.85]%."
- Do NOT carry a hot-shooting semifinal or recent performance at face value into a game against a materially stronger defense

J. STRUCTURAL EDGE CONTEXT AUDIT — RULE 30 (v5, required every game)

- For every structural edge being credited (AST/TO ratio, FT generation, paint dominance, transition offense, steals rate), check whether the opposing team's defense specifically neutralizes that exact dimension
- If the opposing team ranks top-20 nationally in the defensive metric that directly counters the credited advantage, reduce that structural edge credit by 50%
- This check must be performed BEFORE applying any structural credit
- State explicitly for each credit: "Rule 30 check: Opponent ranks [X] nationally in [defensive metric]. Credit [reduced 50% / maintained]."

K. STAR ABSORPTION CEILING AUDIT — RULE 31 (v6, required when primary scorer is absent)

- Confirm whether the team's primary scorer (highest PPG) is absent
- Identify which player absorbs the largest share of the missing scorer's usage
- Pull that player's single-game scoring MAX from the last 10 games
- Pull their 75th-percentile scoring output across last 10 games
- Project their FTA under high-usage conditions (+25% above season average)
- State explicitly: "Rule 31 active — [Player] absorbing [X]% of scoring load. Season avg: [Y] PPG. Single-game max: [Z] pts. 75th pct: [W] pts. Ceiling scenario: [W] pts with [FTA projection] FTAs."
- Widen the total range ceiling by +15 to +20 pts
- If base case projected total is within 10 pts of the line: TOTAL = PASS
- Do NOT recommend Under when Rule 31 is active unless base case is 10+ pts below the line

L. MARKET PRICE EFFICIENCY CHECK — RULE 32 (v7, required every game)

- Calculate the model's projected margin (the number of points the favored team is expected to win by based on the weighted scoring model output)
- Compare the projected margin to the current spread
- Compute the GAP: GAP = current spread minus projected margin (positive gap = line is wider than model projects; negative gap = line is tighter than model projects)
- This check is BILATERAL — it must evaluate BOTH whether the favorite is overpriced AND whether the underdog has affirmative cover value

FAVORITE OVERPRICING CHECK:
- If GAP >= 2 pts (line exceeds model margin by 2+ pts): apply mandatory -5% confidence reduction to favorite and flag as LINE EXCEEDS MODEL
- If GAP >= 4 pts (line exceeds model margin by 4+ pts): favorite recommendation defaults to PASS regardless of composite score
- State explicitly: "Rule 32 check — Favorite side: Model margin = [X] pts. Line = [Y] pts. Gap = [Z] pts. [Maintained / -5% applied / PASS triggered]."

UNDERDOG COVER PROBABILITY CHECK (mandatory whenever GAP >= 2):
- GAP 2.0-2.9 pts: baseline underdog cover probability ~52-54%
- GAP 3.0-3.9 pts: baseline underdog cover probability ~55-57%
- GAP 4.0-5.9 pts: baseline underdog cover probability ~57-60%
- GAP 6.0+ pts: baseline underdog cover probability ~62%+
- Apply ALL standard confidence adjustments to the underdog cover probability
- If adjusted underdog cover probability reaches 62%+: HIGH CONFIDENCE UNDERDOG COVER — 1.5 units
- If adjusted underdog cover probability reaches 57-61%: UNDERDOG COVER — 1 unit
- If below 57%: PASS on both sides
- State explicitly: "Rule 32 check — Underdog side: GAP = [Z] pts. Baseline cover prob = [X]%. After rule modifiers: [Y]%. Recommendation: [High Conf Underdog / Underdog cover / PASS]."

IMPORTANT: Rule 32 does not override Rule 20. If Rule 20 is already active (sharp fade), state "Rule 20 active — Rule 32 underdog check subsumed." Rule 32 is most powerful in TYPE 1 movement games and static wide lines where public money has inflated the favorite.

═══════════════════════════════════════════
STEP 2 — LINE MOVEMENT ANALYSIS
(Complete this BEFORE the weighted scoring model)
═══════════════════════════════════════════
Document the full line movement history and apply Rule 20 before scoring any factors. Line movement direction may override model outputs.

LINE MOVEMENT FRAMEWORK (mandatory — apply to every game):

TYPE 1 — Line moves WITH public (favorite grows from open): Public money inflating the line. Square/public action. ACTION: Apply a mild discount (-2 to -3%) to favorite confidence. RULE 32 INTERACTION: TYPE 1 movement is the primary trigger for Rule 32 underdog value check. Always run Rule 32 bilateral check when TYPE 1 movement is confirmed.

TYPE 2 — Line retraces back to opening after peaking: Sharp bettors have faded the public move. Market returns to fair value. ACTION: Return to baseline model confidence.

TYPE 3 — Line drops BELOW the opening number: *** RULE 20 TRIGGERS *** Professional bettors have moved the line past where books set it — against the favorite. This is a DIRECTIONAL signal against the favorite. ACTION: Apply Rule 20 in full. v5 TRIGGER THRESHOLD: Triggers when the closing spread at ANY major book is below the opening number by more than 0.5 pts. No partial classifications. No "mild warnings."

TYPE 4 — Total drops 3+ points intraday: Sharps pricing in significant scoring suppression. ACTION: Validate the Under.

CRITICAL (v5 addition): When Rule 20 is active, ALL structural credits identified in the model (FT generation, AST/TO edge, OR advantage, etc.) are considered already priced by the sharp bettors who moved the line. Do NOT use structural credits to counteract or override a confirmed sharp fade. The sharps saw the same data.

═══════════════════════════════════════════
STEP 2B — PRE-SCORE PROJECTION ANCHOR
═══════════════════════════════════════════
BEFORE building the weighted scoring model, state the preliminary projected score range based solely on:
(a) Adjusted H2H margin (after Rules 10 and 23)
(b) Season scoring averages for both teams
(c) Any confirmed injury/style adjustments (Rules 16, 22, 24)
(d) Rule 31 check: if active, use the absorbing player's 75th-percentile output — NOT season average — as the anchor for the affected team's scoring projection

This preliminary projection is your ANCHOR. The weighted model may adjust it, but the final projected score must remain within +/-4 points of this anchor unless a specific rule explicitly justifies a larger adjustment with a stated numeric reason.

═══════════════════════════════════════════
STEP 3 — WEIGHTED SCORING MODEL
═══════════════════════════════════════════
Score each team 1-10 on every factor, then apply the weight. Eleven factors total. Weights sum to 100%.

NOTE ON ATS SEASON RECORDS: Do NOT include either team's ATS win-loss record as a scoring factor. Relegate to footnote only.

FACTOR                        | WEIGHT | NOTES
Adjusted season record        | 6%     | Lagging indicator. De-emphasize hot streaks vs weak opponents (Rule 11). Exclude games missing key injured players.
Lineup-verified H2H record    | 10%    | Only count if same core roster played. Apply Rule 10 for neutral-court margin projection. Apply Rule 23 — 45% discount on any true home-court H2H result.
Bench scoring margin          | 9%     | Use LOWER of H2H bench data and last-3-game bench average. Apply Rule 13 cap (+3 pts max). Apply Rule 17 BENCH WILDCARD check bilaterally before scoring.
Star player availability      | 13%    | Flag ALL injuries. Apply Rule 12 if star projects >35% of scoring. Apply Rule 16 style-shift, Rule 22 efficiency discount, Rule 24 role-shift as applicable. RULE 31 (v6): If primary scorer is absent, simultaneously flag the absorbing player's ceiling scenario for the TOTAL model. Rule 12 and Rule 31 must both fire when a star is absent and one player absorbs 35%+ of load.
Recent form (last 7-10 games) | 9%     | Wins, losses, margins, quality. Apply Rule 11 discount if hot streak built vs sub-50 KenPom/NET. Apply Rule 28 EFFICIENCY CONTEXT DISCOUNT: if recent efficiency was vs defenses outside top-40, apply 15% discount vs top-40 opp. State explicitly with numbers. Motivation cap: +0.5 pts max.
2nd-half shooting pattern     | 14%    | Calculate each team's 2H FG% drop vs 1H. Apply Rule 7 if pattern in 3 of last 5 games. Apply Rule 25 B2B2B FATIGUE flag ASYMMETRICALLY ONLY: if both teams played the prior night, fatigue is neutralized. Only apply when one team played and the other did not.
Neutral/away site factors     | 5%     | Hometown crowd, travel, rest days. Cap rest differential at +3 pts. REST PENALTY for 4+ day layoffs: -1.0 defensive rhythm penalty. MOTIVATION CAP: +0.5 pts max.
Turnover rate (per player)    | 15%    | Most underpriced factor in championship games. Top-30 AST/TO nationally vs mid-range opponent is worth 15-18 pts in a tight game. RULE 30 CONTEXT CHECK: Before applying AST/TO structural credit, check if opposing defense is top-20 in forcing TOs or limiting assists. If YES, reduce credit by 50%. Apply Rule 4 cascade when primary handler out. Apply Rule 18 check.
Interior / Paint Dominance    | 8%     | OR rate, 2nd-chance pts, paint pts. Rule 8: +0.5 pts/pct pt OR advantage. Cap at +6 pts max. RULE 29: If both teams top-3 conference OR, credit = +0 unless H2H OR data overrides. RULE 30: Check if opposing team top-20 defensive rebounding. If YES, reduce OR credit 50%.
Supporting cast variance      | 6%     | Std dev of 2nd/3rd/4th scorers. Apply Rule 9. Apply Rule 17. Model the FLOOR case. If HIGH VARIANCE scorer goes cold at <=50% of avg, what is team FG% and total? Include in total range model. RULE 31: When primary scorer is absent, the absorbing star is no longer supporting cast — they become the primary. Do NOT apply their season average as the scoring anchor. Use 75th-percentile output and model the ceiling.
Free throw generation         | 5%     | Top-30 FT nationally: +1.5 pt credit. FTA differential +8 or more: +1.0 additional credit. RULE 30: If opponent is top-20 fewest fouls, reduce FT credit 50%. Flag FT-DISADVANTAGED teams. RULE 31: Absorbing player under high usage draws +25% more FTAs than their season average. Include in total projection when Rule 31 active.

WEIGHT AUDIT: 6+10+9+13+9+14+5+15+8+6+5 = 100%

═══════════════════════════════════════════
STEP 4 — QUALITATIVE FLAGS (Must check all)
═══════════════════════════════════════════
Before finalizing prediction, explicitly answer each question:

[ ] Is there ANY player absent today who played in the cited H2H games?
[ ] Were any cited H2H results played at one team's TRUE HOME COURT? (Rule 23 — 45% margin discount. Do not carry full margins forward.)
[ ] Does either team have a player averaging 3+ TOs as primary handler?
[ ] Does either team shoot significantly worse in the 2nd half than 1st?
[ ] Is either team playing their 3rd game in 3 days? (Rule 25 — apply ASYMMETRICALLY. If both teams played prior night, fatigue is neutralized. Only flag when one team played and other did not.)
[ ] Is the bench scoring margin 10+ points for one team? (Cross-check H2H bench data vs last-3-game bench. Use lower figure.)
[ ] Are there hometown/region ties for either team at this venue?
[ ] How many games has each team played in the last 5 days?
[ ] Motivation from prior tournament game? (Cap at +0.5 pts max)
[ ] Is this a tournament/elimination game? (Reduce pace 5-8%, increase defensive efficiency, default to UNDER) (RULE 31 EXCEPTION: If Rule 31 is active, do NOT default to Under. Elimination game urgency increases star-absorption ceiling risk. A desperate undermanned team may generate MORE possessions and fouls, not fewer. Pace reduction assumption must be re-examined when Rule 31 is active.)
[ ] What is the projected paint-point differential? (Numeric estimate required) Apply Rule 29 bilateral OR parity check. If both teams top-3 conference OR, default to +0 unless H2H OR data is available.
[ ] Does any non-star scorer have HIGH VARIANCE (std dev 7+ in last 5 games)? (Widen CI +/-4 pts. Also model FLOOR scenario at <=50% of their average.)
[ ] Is any team's projected star share of scoring above 35%? (Rule 12 FRAGILE flag. Reduce spread confidence 5%, widen CI +/-3 pts.)
[ ] RULE 31 — Is the primary scorer absent AND a single player absorbing 35%+? (Pull absorbing player's max and 75th-pct output from last 10 games. Widen total ceiling +15 to +20 pts. If base case within 10 pts of line: TOTAL = PASS. Do NOT recommend Under unless base case is 10+ pts below line. Apply FTA +25% adjustment for high-usage conditions. Apply simultaneously with Rule 12. Both must fire together.)
[ ] Is either team's recent hot streak built vs weak opponents? (Rule 11 — 40% discount to Recent Form score if triggered.)
[ ] REST-RUSTINESS: Has the rested team played in the last 4+ days? (Flag defensive efficiency DEGRADED in first 8-10 minutes. +3 to +5 pts total.)
[ ] BILATERAL 3PT CEILING: Any team above 37% 3PT recently? (Model hot-game ceiling ~47-50%. State base AND hot-shooting range.)
[ ] RULE 28 — Was recent offensive efficiency generated vs top-40 defenses? (If not, apply 15% discount to efficiency figures vs top-40 opponent.)
[ ] RULE 29 — Are both teams top-3 conference in offensive rebounding? (If YES, OR credit = +0 unless H2H OR data overrides.)
[ ] RULE 30 — For each structural credit being applied, does the opponent rank top-20 nationally at neutralizing that exact dimension? (If YES, reduce that credit 50%. Check: AST/TO, FT gen, OR, transition.)
[ ] INJURY STYLE-SHIFT (Rule 16): Frontcourt injury — pace change — total direction?
[ ] INJURY ROLE-SHIFT (Rule 24): Injured guard/wing — distributor-first?
[ ] INJURY SHOOTING-EFFICIENCY (Rule 22): Lower-extremity injury — -15% FG%?
[ ] SECOND-CHANCE POSSESSION SURPLUS: Dominant OR edge (+5/game)? (+5-7 pts to total. Apply Rule 29 check first.)
[ ] BENCH WILDCARD (Rule 17): Any bench player 20+ pts in last 10 games? (Flag both teams. Widen CI +/-3 pts. Reduce opposing cover prob 4%.)
[ ] TURNOVER CEILING (Rule 18): Either team committed 15+ TOs in last 10? (Flag HIGH-TO-CEILING. Reduce cover prob 5%, widen CI +/-3 pts.)
[ ] STRUCTURAL TO EDGE: Is one team top-30 AST/TO and other mid-range? (Apply Rule 30 context check first. Reduce 50% if opponent top-20 in forcing TOs or limiting assists.)
[ ] FREE THROW GENERATION (Rule 19): Projected FTA differential? Top-30 FT? (Apply Rule 30 context check before applying credit.) (Apply Rule 31 FTA adjustment if absorbing player under high usage.)
[ ] SHARP LINE OVERRIDE (Rule 20): Has spread dropped below opening at ANY major book by more than 0.5 pts? If YES — Rule 20 fully active. No partial classification. Apply full -7% and reconciliation mandate. Structural credits do not counteract a confirmed sharp fade.
[ ] RULE 20 RECONCILIATION: If Rule 20 active, run Steps R1-R4 and show original margin vs reconciled margin side by side.
[ ] RULE 32 — MARKET PRICE EFFICIENCY CHECK (required every game, bilateral):
    FAVORITE SIDE: GAP = current spread minus model projected margin. If GAP >= 2 pts: apply -5% to favorite confidence and flag LINE EXCEEDS MODEL. If GAP >= 4 pts: PASS on favorite. State: "Rule 32 — Favorite: Model margin = [X]. Line = [Y]. Gap = [Z]. [Maintained / -5% / PASS]."
    UNDERDOG SIDE: If GAP >= 2 pts, calculate underdog implied cover probability. GAP 2 pts = ~52-54%; GAP 3 pts = ~55-57%; GAP 4 pts = ~57-60%; GAP 6+ pts = ~62%+. Apply all standard rule modifiers. If adjusted cover probability >= 62%: HIGH CONFIDENCE UNDERDOG COVER — 1.5 units. If 57-61%: UNDERDOG COVER — 1 unit. Below 57%: PASS both sides. State: "Rule 32 — Underdog: GAP = [Z]. Implied cover prob = [X]%. Adjusted = [Y]%. [High Conf Underdog / Underdog cover / PASS]."
    NOTE: Rule 32 does not override Rule 20. If Rule 20 is already active, state "Rule 20 active — Rule 32 underdog check subsumed."
[ ] TOURNAMENT FAVORITE ATS DISCOUNT (Rule 21): Favorite laying 4-8 pts with split season series? (-6% ATS confidence if triggered.)
[ ] HIGH-VARIANCE TOTAL FLAG (Rule 14): Check all four conditions. Two or more = cap at 60% UNDER confidence. Three or more = NO BET. RULE 31 INTERACTION: If Rule 14 condition (c) (leading scorer injured) fires alongside Rule 31, total recommendation defaults to PASS.
[ ] RULE 27 PRE-CHECK: Is the projected score consistent with BOTH spread and total picks BEFORE the Best Bets are named? Fix score first if not.
[ ] INTERNAL CONSISTENCY GATE (Rule 26): Score, spread pick, total pick, and Best Bets all pointing the same direction? State PASSED or FAILED.

═══════════════════════════════════════════
STEP 4B — RULE 27: PRE-BEST BET SCORE CONSISTENCY MANDATE
═══════════════════════════════════════════
BEFORE naming any Best Bet, complete this mandatory pre-check:

1. State the Step 2B anchor score projection
2. State the final projected score after all rule adjustments
3. Confirm the recommended spread side is consistent with the projected score
4. Confirm the recommended total side is consistent with the projected combined score
5. If either conflicts: REVISE THE SCORE FIRST, then name the Best Bets

State explicitly: "RULE 27 PRE-CHECK: Score = [X-Y]. Spread pick = [Team] [line]. Total pick = [Over/Under] [number]. [CONSISTENT] or [INCONSISTENT — score revised to [A-B] because [reason].]"

═══════════════════════════════════════════
STEP 5 — BETTING ANALYSIS
═══════════════════════════════════════════
For EACH available market, provide:

SPREAD:
- Recommended side + line
- Confidence % (must account for ALL variance flags and Rule 20/21/32 adjustments BEFORE stating final confidence)
- Key stat justifying the pick
- Projected margin range (low / mid / high scenario)
- Risk level: Low / Medium / High
- Unit size: 1 unit (57-61%), 1.5 units (62%+), 0 units (PASS)
- If Rule 20 is active, state: "SHARP FADE IN EFFECT — confidence adjusted -7% from model baseline. Structural credits already priced by sharp money and are not used to counteract the fade."
- If Rule 21 is active, state: "TOURNAMENT FAVORITE DISCOUNT APPLIED -6%"
- If Rule 32 is active, state: "MARKET PRICE EFFICIENCY CHECK APPLIED — Model margin = [X]. Line = [Y]. Gap = [Z]. Favorite confidence [adjusted / PASS]. Underdog cover probability = [Y]%. Recommendation: [Underdog cover / PASS both sides]."

MONEYLINE:
- ONLY recommend if confidence > 65% AND value is present
- If laying more than -150, explicitly state "POOR VALUE" unless confidence exceeds 70%
- State exact payout math: "Risk $X to win $Y"

TOTAL (Over/Under):
- Recommended side + number
- Pull last 5 game totals for both teams
- Flag tournament/elimination context (games typically go UNDER)
- Historical under/over rate for both teams in last 10 games
- Unit size: 1 unit (57-61%), 1.5 units (62%+), 0 units (PASS)

TOTAL RANGE MODEL (mandatory for every total pick — 6 scenarios):
— BASE CASE: season averages + tournament pace reduction applied
— HOT-SHOOTING SCENARIO: both teams hit top-quartile 3PT%
— COLD-SHOOTING SCENARIO: both teams hit bottom-quartile 3PT%
— FLOOR SCENARIO: HIGH VARIANCE scorer(s) cold at <=50% of avg
— INJURY-ADJUSTMENT SCENARIO: pace direction per Rules 16/22/24
— STAR ABSORPTION CEILING SCENARIO (Rule 31): Required whenever Rule 31 is active. Use absorbing player's 75th-pct output plus +25% FTA adjustment. State projected team total and combined total explicitly. If this scenario produces a combined total within 10 pts of the line on the OVER side, the total recommendation must be PASS, not Under.

Only recommend UNDER if BASE CASE and COLD scenario both support it AND Rule 31 Star Absorption Ceiling scenario does not produce a combined total within 10 pts of the line. If HOT scenario produces total 10+ points above the line, reduce UNDER confidence by 10 percentage points. Apply Rule 14 cap before issuing any UNDER recommendation.

PARLAY (if applicable):
- Only suggest if two independent high-confidence picks exist (both >= 61%)

BEST BETS (issue ALL plays that meet the confidence threshold):
- Complete Rule 27 PRE-CHECK before naming any Best Bet
- Do NOT limit to one pick. Issue a Best Bet for EVERY market that independently meets the confidence threshold after all rule adjustments are applied
- BEST BET 1 — SPREAD: Issue if spread confidence >= 57% after all adjustments. State pick, line, confidence, units. If below 57%: state SPREAD = PASS
- BEST BET 2 — TOTAL: Issue if total confidence >= 57% after all adjustments. State pick, line, confidence, units. If below 57%: state TOTAL = PASS
- Both picks are evaluated INDEPENDENTLY. A PASS on the spread does not affect the total recommendation and vice versa. A PASS on the total does not prevent a spread Best Bet.
- The headline prediction must be consistent with BOTH picks
- If Rule 20 drops spread confidence below 60%: spread Best Bet must be PASS or underdog — never the favorite
- If Rule 31 is active and base case total is within 10 pts of the line: total Best Bet must be PASS — not Under
- If Rule 32 identifies underdog cover probability >= 57%: the underdog cover IS a valid spread Best Bet
- State unit size with EVERY Best Bet: 1 unit (57-61%), 1.5 units (62%+), 2 units (Rule 20 + Rule 32 both active)
- Label picks clearly:
  BEST BET — SPREAD: [pick] [line] ([conf]% — [units])
  BEST BET — TOTAL: [pick] [line] ([conf]% — [units])

═══════════════════════════════════════════
STEP 6 — MANDATORY MODEL RULES (32 Total)
═══════════════════════════════════════════
These rules override all other assumptions.
Rules 1-7: original. Rules 8-13: post-mortem v1. Rules 14-16: post-mortem v2. Rules 17-22: post-mortem v3. Rules 23-26: post-mortem v4. Rules 27-30: post-mortem v5 (Hawaii 71, UCI 64 — Big West Championship 2026). Rule 31: post-mortem v6 (Penn 88, Yale 84 OT — Ivy League Championship 2026). Rule 32: structural bias correction v7 (favorite overpricing and underdog cover value identification).

RULE 1 — HEADLINE = BEST BET
The outright game winner predicted must be CONSISTENT with the bet recommendation. Never predict Team A wins but recommend betting Team B.

RULE 2 — BENCH DEPTH
Always compute bench points from actual box scores. Use BOTH H2H bench data AND last-3-game bench average. Apply the LOWER of the two figures. See Rule 13 for cap. Apply Rule 17 before scoring.

RULE 3 — NEVER TRUST RAW H2H WITHOUT ROSTER CHECK
If a team's star player was absent in a prior meeting, that result counts for 30% of normal weight, not 100%.

RULE 4 — INJURY CASCADE AWARENESS
When a starting PG/primary handler is out, flag every player who absorbs their usage. Check that player's TO rate under increased load.

RULE 5 — TOURNAMENT GAMES BEHAVE DIFFERENTLY
Reduce pace 5-8%, add 2-3 points to defensive efficiency, default to UNDER. AMENDMENT: Defensive efficiency boost applies ONLY to teams that have played at least one tournament game. For a team's FIRST tournament game after 4+ days off, apply a FIRST-GAME RUST PENALTY instead. RULE 31 EXCEPTION: When Rule 31 is active (star absent, single player absorbing 35%+ of scoring load), the pace reduction assumption must be re-examined. Elimination urgency for an undermanned underdog may produce MORE fouls, MORE possessions, and MORE free throws — not fewer. Do NOT apply the Under default when Rule 31 is active without first running the Star Absorption Ceiling scenario.

RULE 6 — MONEYLINE DISCIPLINE
Do not recommend moneyline at worse than -150 unless model shows 65%+ win probability. Always flag poor value.

RULE 7 — SECOND-HALF COLLAPSE TRACKING
If a team has dropped 10%+ in FG% in the 2nd half in 3 of their last 5 games, flag it as a PATTERN — structural weakness, not variance.

RULE 8 — PAINT SCORING AUDIT
Calculate expected paint-point differential based on OR rate and interior FG%. Credit +0.5 spread pts per percentage point of OR advantage. Cap at +6 pts. Produce a numeric estimate — no vague language. Apply Rule 29 Bilateral OR Parity check before assigning any credit. Apply Rule 30 defensive context check before assigning any credit. If dominant OR edge (+5/game), model additional possessions (+5-7 pts total).

RULE 9 — SUPPORTING CAST VARIANCE FLAG
Calculate scoring std dev for 2nd/3rd/4th scorers across last 5 games. If any non-primary scorer averages 12+ PPG with std dev 7+ pts, flag as HIGH VARIANCE. Widen spread CI by +/-4 pts. Apply Rule 17 alongside. Model the FLOOR case. If this player has a cold game at <=50% of their average, what is the resulting team FG% and projected total? Include this floor scenario in every total range model when triggered. RULE 31 INTERACTION: When Rule 31 is active, the absorbing player has graduated from supporting cast to de facto primary. Do NOT apply Rule 9 variance analysis using their season average as the anchor. Apply Rule 31 ceiling modeling instead.

RULE 10 — H2H MARGIN NEUTRALIZATION
Neutral Projection = Road H2H Margin + 2 to 3 points. Do NOT multiply or amplify the margin. See Rule 23 for home court discount.

RULE 11 — MOMENTUM QUALITY DISCOUNT
If recent hot streak (7-10 game window) built primarily against teams outside top-50 KenPom/NET, apply 40% discount to Recent Form factor score.

RULE 12 — SINGLE-STAR DEPENDENCY RISK
If one player accounts for more than 35% of projected total scoring, flag as FRAGILE OFFENSE. Reduce spread confidence 5%, widen CI +/-3 pts. RULE 31 INTERACTION: Rule 12 addresses SPREAD risk. Rule 31 addresses TOTAL risk in the opposite direction. Both must fire simultaneously when a primary scorer is absent and one player absorbs 35%+ of the load. Rule 12 does not replace Rule 31, and Rule 31 does not replace Rule 12.

RULE 13 — BENCH MAGNITUDE CAP
Bench scoring advantage capped at +3 spread points maximum regardless of calculated gap. Apply Rule 17 before invoking this cap.

RULE 14 — TOTAL CONFIDENCE CAP ON HIGH-VARIANCE GAMES
If ANY TWO of these conditions exist simultaneously, max UNDER confidence is capped at 60% (label HIGH VARIANCE):
(a) Both teams shooting above 37% from 3 in recent games
(b) One team playing first tournament game after 4+ days rest
(c) Either team's leading scorer injured or in foul trouble
(d) Combined team TO rate differential > 4 turnovers/game
If THREE OR MORE conditions present: UNDER is NO BET. State "NO BET — RULE 14 TRIGGERED" explicitly. RULE 31 INTERACTION: Condition (c) is precisely the trigger for Rule 31. When condition (c) fires Rule 14, check whether Rule 31 also fires. If both Rule 14(c) and Rule 31 are active simultaneously, the total recommendation defaults to PASS regardless of other conditions.

RULE 15 — BILATERAL 3PT VARIANCE
When both teams are above 37% 3PT in recent play, max UNDER confidence is 58% standalone. Regression on one side does not neutralize upside on other.

RULE 16 — INJURY STYLE-SHIFT MANDATE
Never model an injury as a simple point subtraction. Assess the replacement and resulting style change: Frontcourt star lost — smaller lineup — pace UP — total UP. Perimeter scorer lost — efficiency DOWN. Primary ball-handler lost — turnover risk UP — Rule 4 cascade. Apply Rule 22 simultaneously for lower-extremity injuries. Apply Rule 24 simultaneously for guard/wing lower-extremity injuries. RULE 31 INTERACTION: Rule 16 tells you HOW the offense changes. Rule 31 tells you HOW HIGH it can go when one player takes over. Apply both.

RULE 17 — BENCH WILDCARD CEILING
Pull single-game scoring MAX for every bench player from last 10 games. If any bench player has scored 20+ in ANY game in last 10, flag BENCH WILDCARD. Apply BILATERALLY. When triggered: widen CI +/-3 pts, reduce opposing team's cover probability by 4%. A 7 PPG average player who once scored 28 is a BENCH WILDCARD, not a role player.

RULE 18 — TURNOVER CEILING RULE
Pull single-game TO max for each team from last 10 games. If any team has committed 15+ TOs in ANY game in last 10, flag HIGH-TO-CEILING. When triggered: reduce projected scoring 8-10 pts in high-TO scenario, widen CI +/-3 pts, reduce cover probability by 5%. Any player with 5+ TOs in any recent game is a personal TO-ceiling flag.

RULE 19 — FREE THROW GENERATION FACTOR
Pull FTA per game (last 5 games) and national FT rank. Top-30 nationally in FT made: +1.5 spread-pt credit. FTA differential +8 or more: additional +1.0 credit. Flag FT-DISADVANTAGED teams. Apply Rule 30 before assigning credit: if opponent is top-20 fewest fouls, reduce FT credit by 50%. RULE 31 INTERACTION: When Rule 31 is active, apply a +25% upward adjustment to the absorbing player's projected FTA in the TOTAL model (not the spread model).

RULE 20 — SHARP LINE MOVEMENT OVERRIDE (AMENDED v5)
When a spread drops more than 0.5 pts below its opening line at ANY major book (DraftKings, FanDuel, BetMGM, bet365), a SHARP FADE is in effect. Cross-book unanimity is NOT required. In thin markets, one major book moving below opening is sufficient. There is no "partial" Rule 20. When triggered: (1) Reduce favorite spread confidence by 7 percentage points. (2) If post-adjustment confidence below 60%, recommendation MUST be PASS or FLIP to underdog — never recommend the favorite. (3) Label all outputs "SHARP FADE IN EFFECT." (4) State: "Sharp money is on the underdog. Structural credits identified in this model were already priced by the bettors who moved this line. They are not used to counteract the sharp fade." CRITICAL: A spread dropping below its opening is NEVER a value opportunity for the favorite. It is a directional signal AGAINST the favorite.

RULE 20 — PROJECTION RECONCILIATION MANDATE
When Rule 20 is active, reconcile the score projection with the pick: STEP R1: Recalculate projected margin using structural credits as point values. Apply sharp-money margin compression. STEP R2: State the revised projected margin explicitly in points. STEP R3: Align the outright prediction with the reconciled margin. STEP R4: Label — "PROJECTED MARGIN REVISED — Rule 20 Reconciliation Applied." Show original model margin and reconciled margin side by side.

RULE 21 — TOURNAMENT FAVORITE ATS DISCOUNT
When the favorite is laying 4-8 pts AND both teams have played twice AND the season series is split: apply mandatory 6% ATS confidence discount. State: "TOURNAMENT FAVORITE DISCOUNT APPLIED."

RULE 22 — INJURY SHOOTING-EFFICIENCY DISCOUNT
For any lower-extremity injury (foot, ankle, knee, hip), apply a mandatory -15% discount to that player's FG% projection. Never use healthy-season average for an injured player. Apply to both spread and total projections.

RULE 23 — HOME COURT H2H DISCOUNT
When a cited H2H result occurred at one team's true home court, apply a 45% discount to the winning margin before using in any neutral projection. A 17-point home win projects to +5-7 neutral at most. Stacks with Rule 10. Apply both sequentially.

RULE 24 — INJURED GUARD/WING ROLE-SHIFT
For guard/wing with lower-extremity injury, model the role shift: 3PT attempt rate decreases 30-40%. 2PT attempt rate increases 20-25%. Assist/distribution rate may increase. Apply Rule 22's -15% FG% discount simultaneously. State explicitly whether player projects as scorer-first or distributor-first.

RULE 25 — BACK-TO-BACK-TO-BACK FATIGUE FLAG (AMENDED v5)
When either team is playing their third game in three consecutive days: (1) Apply mandatory 2H scoring reduction of 5-8% to team with shallower depth chart. (2) If 2H scoring dip observed in prior (Game 2-of-3) game, treat as 60% probability of recurrence in Game 3. (3) Flag as BACK-TO-BACK-TO-BACK FATIGUE RISK. v5 AMENDMENT: Apply ASYMMETRICALLY ONLY. If both teams played the prior night, fatigue is roughly neutralized and must NOT be applied as a one-sided credit for either team.

RULE 26 — INTERNAL CONSISTENCY GATE
Before finalizing ANY prediction output, run all three checks explicitly: CHECK 1: Does predicted score imply margin consistent with spread pick? CHECK 2: Does spread pick align with outright winner prediction? CHECK 3: Do Best Bets align with headline prediction direction? If ANY check fails, output is INVALID. Revise score, spread pick, or both. State: "RULE 26 CONSISTENCY GATE: PASSED" or "RULE 26 CONSISTENCY GATE: FAILED — [state what was revised]"

RULE 27 — PRE-BEST BET SCORE CONSISTENCY MANDATE
Before naming any Best Bet, the analyst MUST complete a pre-check: (1) State the Step 2B anchor score projection. (2) State the final projected score after all rule adjustments. (3) Confirm the recommended spread side is consistent with the final score. (4) Confirm the recommended total side is consistent with the projected combined score. (5) If inconsistent: REVISE THE SCORE FIRST, then name the Best Bets. State: "RULE 27 PRE-CHECK: Score = [X-Y]. Spread pick = [Team][line]. Total pick = [Over/Under][number]. [CONSISTENT] or [INCONSISTENT — revised to [A-B] because [reason].]"

RULE 28 — OFFENSIVE EFFICIENCY CONTEXT DISCOUNT (v5)
Recent offensive efficiency (FG%, AST rate, pace, PPG) must be contextualized against the quality of defenses faced. If a team's last 3 game efficiency was generated against defenses ranked outside the top 40 nationally (KenPom/NET), apply a 15% discount to those efficiency figures when projecting against a top-40 defense. State explicitly: "Team X's recent FG% of Y% was generated vs defenses ranked [Z avg KenPom/NET] — applying 15% discount vs [opponent rank] defense. Revised projection: [Y x 0.85]%." Apply to both the spread projection and the total estimate.

RULE 29 — BILATERAL OR PARITY NULLIFICATION (v5)
When both teams rank in the top 3 of their conference in offensive rebounding rate, the Rule 8 OR differential credit defaults to +0 unless actual H2H OR data from box scores is available. Season rank vs. season rank within the same conference provides no net edge prediction. Use H2H box score OR totals to determine which team won the OR battle. If H2H OR data is unavailable, call it a push (+0).

RULE 30 — STRUCTURAL EDGE CONTEXT CHECK (v5)
Before applying ANY structural edge credit to the spread projection (AST/TO ratio, FT generation, OR dominance, transition offense, steals, etc.), the analyst must check whether the opposing team's defense specifically neutralizes that exact dimension. If the opposing team ranks top-20 nationally in the defensive metric that directly counters the credited advantage, reduce that structural edge credit by 50%. This check must be performed BEFORE assigning any structural credit. State explicitly for each credit: "Rule 30 check: Opponent ranks [X] nationally in [defensive metric]. Credit [reduced 50% / maintained]."

RULE 31 — STAR ABSORPTION CEILING (v6)
Root cause: Penn 88, Yale 84 OT — Ivy League Championship 2026. TJ Power scored 44 pts (season avg: 15.8) after Ethan Roberts (leading scorer) was ruled out. The model projected Penn scoring ~67 pts using Power's season average as the anchor. Actual Penn scoring: 88 pts. The model correctly applied Rule 12 (FRAGILE — spread risk) but failed to apply the inverse total risk: when a primary scorer is absent, the absorbing star does not produce average output. In an elimination game with full usage license, they produce ceiling output.

When a team's primary scorer (highest PPG) is confirmed absent AND a single remaining player is projected to absorb 35%+ of that team's scoring load: (1) Pull the absorbing player's single-game scoring maximum from last 10 games. (2) Calculate their 75th-percentile output across last 10 games. (3) Apply a +25% upward adjustment to their projected FTA (high usage = more fouls drawn). (4) Use the 75th-percentile output — NOT their season average — as the anchor for that team's scoring projection in the total model. (5) Widen the total range ceiling by +15 to +20 pts above the base case. (6) If the Star Absorption Ceiling scenario produces a combined total within 10 pts of the line on the Over side: total recommendation = PASS. (7) Do NOT recommend Under when Rule 31 is active unless the base case projected total is at least 10 pts BELOW the line. (8) State explicitly: "Rule 31 active — [Player] absorbing [X]% of load. Season avg [Y] PPG. Max last 10: [Z] pts. 75th pct: [W] pts. Ceiling scenario: [W] pts + [FTA adj] FTs. Total ceiling: [combined]. Base case within 10 pts of line: PASS."

Rule 31 fires SIMULTANEOUSLY with Rule 12. Rule 12 addresses spread risk (single-star dependency — FRAGILE). Rule 31 addresses total risk in the OPPOSITE direction (absorbing star — ceiling output — Over risk). They are not redundant. Both must be applied together whenever a primary scorer is absent and one player absorbs 35%+ of the load.

Rule 31 also interacts with Rule 5 (tournament pace). Elimination urgency for an undermanned underdog produces MORE fouls, MORE FTAs, and potentially MORE possessions — not fewer. Do not apply the Rule 5 Under default without first confirming that the Rule 31 ceiling scenario clears the line by 10+ pts.

RULE 32 — MARKET PRICE EFFICIENCY CHECK (v7)
Root cause: The model's 11-factor weighted scoring system naturally scores the better team higher, which is almost always the favorite. This creates a structural bias toward recommending favorites regardless of whether the line price reflects fair value. Rule 32 corrects this by requiring a bilateral market price check on every game.

STEP 1 — COMPUTE THE GAP: GAP = current spread minus projected margin. A positive GAP means the line is wider than the model projects.

STEP 2 — FAVORITE SIDE CHECK:
- GAP of 0-1.9 pts: No adjustment. Favorite recommendation maintained.
- GAP of 2-3.9 pts: Apply mandatory -5% confidence reduction to favorite. Flag as LINE EXCEEDS MODEL.
- GAP of 4+ pts: Favorite recommendation defaults to PASS regardless of composite score.
- State explicitly: "Rule 32 — Favorite side: Model margin = [X] pts. Line = [Y] pts. Gap = [Z] pts. [No adjustment / -5% applied / PASS triggered]."

STEP 3 — UNDERDOG SIDE CHECK (mandatory when GAP >= 2):
- GAP 2.0-2.9 pts: baseline ~52-54%
- GAP 3.0-3.9 pts: baseline ~55-57%
- GAP 4.0-5.9 pts: baseline ~57-60%
- GAP 6.0+ pts: baseline ~62%+
Apply ALL standard rule modifiers. Final thresholds:
- 62%+ adjusted: HIGH CONFIDENCE UNDERDOG COVER — 1.5 units. Valid Best Bet candidate.
- 57-61% adjusted: UNDERDOG COVER — 1 unit. Valid Best Bet candidate.
- Below 57% adjusted: PASS on both sides.
State explicitly: "Rule 32 — Underdog side: GAP = [Z] pts. Baseline = [X]%. After modifiers: [Y]%. Recommendation: [High Conf Underdog / Underdog cover / PASS]."

STEP 4 — RULE 32 INTERACTIONS:
- Rule 32 does NOT override Rule 20. If Rule 20 is active, state: "Rule 20 active — Rule 32 underdog check subsumed."
- Rule 32 is most powerful in TYPE 1 movement games and static wide lines where public money has inflated the favorite.
- Rule 32 stacks with Rule 21: if both fire simultaneously, apply Rule 21's -6% to the favorite AND run the Rule 32 underdog check.
- Rule 32 does NOT apply when the GAP is negative.

═══════════════════════════════════════════
STEP 7 — DELIVERABLE FORMAT
═══════════════════════════════════════════
Structure your response exactly as follows:

1. GAME CONTEXT (2-3 sentences max)
2. DATA VERIFIED (checklist of what was pulled and confirmed)
3. LINE MOVEMENT ANALYSIS (Rule 20 applied first — before model scores)
   — Document open, peak, current line and total
   — State movement type (Type 1/2/3/4)
   — State explicitly: Is Rule 20 Sharp Fade active?
   — State explicitly: Does Rule 21 Tournament Discount apply?
   — State explicitly: Rule 32 GAP calculation (model margin vs line)
4. KEY PLAYER STATUS
   — Rule 12 FRAGILE flag if star share >35%
   — Rule 31 STAR ABSORPTION CEILING if primary scorer absent (State: absorbing player, season avg, max last 10, 75th pct, FTA adjustment, ceiling scenario total, PASS trigger if within 10 pts)
   — Rule 9 HIGH VARIANCE flag + floor scenario for volatile scorers
   — Rule 17 BENCH WILDCARD flag (both teams checked)
   — Rule 16/22/24 injury notes with revised numeric projections
5. TEAM STATS COMPARISON TABLE (last 3 games + season)
   — Points in Paint
   — Offensive Rebound Rate (with Rule 29 bilateral parity note)
   — Supporting cast std dev + floor scenario (Rule 9)
   — 3PT% last 3 games individually (HIGH 3PT VARIANCE if >15 pt range)
   — FTA per game (last 5) and national FT rank
   — Rule 28: recent FG% vs defensive quality of opponents faced
   — Single-game TO maximum (last 10) — HIGH-TO-CEILING flag
   — AST/TO ratio and national rank — STRUCTURAL TO EDGE flag (with Rule 30 context check stated)
   — Bench player scoring ceilings (last 10) — BENCH WILDCARD flag
   — 2H vs 1H scoring (last 3 games) — flag dips
   — Rule 31: absorbing player scoring max + 75th pct (if applicable)
6. QUALITATIVE FLAGS (answered checklist — all items from Step 4)
7. WEIGHTED MODEL SCORES (table across all 11 factors)
   — Show Rule 20 Sharp Fade adjustment (full -7% if active; no partials)
   — Show Rule 20 Projection Reconciliation (original vs reconciled margin)
   — Show Rule 21 Tournament Discount if active
   — Show Rule 23 Home Court H2H Discount if applied
   — Show Rule 24 Role-Shift projection if applicable
   — Show Rule 25 B2B2B Fatigue flag (asymmetric application stated)
   — Show Rule 17 Bench Wildcard status
   — Show Rule 18 TO Ceiling status
   — Show Rule 19 FT Generation credit (with Rule 30 check result)
   — Show Rule 22 Shooting Efficiency adjustment if applicable
   — Show Rule 28 Offensive Efficiency Context Discount if applied
   — Show Rule 29 Bilateral OR Parity status
   — Show Rule 30 Structural Edge Context checks for each credit
   — Show Rule 31 Star Absorption Ceiling (absorbing player stats, ceiling scenario total, PASS trigger status)
   — Show Rule 32 Market Price Efficiency Check (GAP calculation, favorite adjustment, underdog cover probability and recommendation)
   — Show numeric paint differential (Rule 8, after Rules 29/30)
   — Show supporting cast variance + floor scenario (Rule 9)
   — Show recent form quality discount if applied (Rule 11)
   — Show REST-RUSTINESS adjustment if applicable
   — Show Rule 14 HIGH-VARIANCE flag status
   — Show STRUCTURAL TO EDGE flag and estimated point-swing value (after Rule 30 context reduction)
   — Show Step 2B anchor projection vs final projection
8. RULE 27 PRE-CHECK (required before Best Bets are named)
   — "RULE 27 PRE-CHECK: Score = [X-Y]. Spread pick = [Team][line]. Total pick = [Over/Under][number]. [CONSISTENT / INCONSISTENT — revised to [A-B] because [reason].]"
9. BETTING RECOMMENDATIONS
   — BEST BET — SPREAD: [pick] [line] ([conf]% — [units]) OR SPREAD = PASS
   — BEST BET — TOTAL: [pick] [line] ([conf]% — [units]) OR TOTAL = PASS
   — Rule 20 statement if active (full -7%, structural credits priced in)
   — Rule 20 Reconciliation if applied (revised margin stated explicitly)
   — Rule 21 statement if active (-6%)
   — Rule 32 statement (GAP, favorite adjustment, underdog cover probability, recommendation, unit size)
   — Moneyline assessment
   — Total Range: Base / Hot / Cold / Floor / Injury / Star Absorption Ceiling
   — Rule 31 PASS trigger stated explicitly if ceiling scenario within 10 pts of line
   — Rule 14/15 cap status stated explicitly
   — PASS stated explicitly if confidence below 57% after all adjustments on either market
   — NO BET on total stated if Rule 14 triggered (3+ conditions)
10. RISK ASSESSMENT TABLE
11. PREDICTION (must match Best Bet directions)
    — "RULE 27 PRE-CHECK: [result]"
    — "RULE 26 CONSISTENCY GATE: PASSED / FAILED — [revision if any]"
    — If Rule 20 Reconciliation applied: Original model margin: X pts / Reconciled margin: Y pts / Driver: [stated]
    — If Rule 31 active: Absorbing player season avg: X PPG / 75th-pct ceiling: Y pts / Total ceiling: Z / Total recommendation: PASS or Under
    — If Rule 32 active: Model margin: X pts / Line: Y pts / GAP: Z pts / Favorite: [stated] / Underdog cover prob: [Y]% / Units: [stated]
12. Generate the entire report as a PDF

═══════════════════════════════════════════
IMPORTANT REMINDERS (v7)
═══════════════════════════════════════════

- Apply Rule 20 FIRST, before any model scoring
- Rule 20 triggers at ANY major book closing below opening by >0.5 pts. No partial classifications. Apply the full -7% and the full Projection Reconciliation Mandate.
- When Rule 20 is active: structural credits are already priced. Do NOT use them to counteract the fade.
- Complete Rule 27 PRE-CHECK before naming any Best Bet. Fix the score first if score and picks are inconsistent.
- Apply Rule 28: discount recent offensive efficiency if generated against weak defenses. State explicitly with numbers.
- Apply Rule 29: if both teams are elite conference offensive rebounders, OR credit = +0 unless H2H OR data overrides.
- Apply Rule 30 to EVERY structural credit before assigning it. If the opponent is top-20 at neutralizing that exact dimension, reduce by 50%. State explicitly for each credit.
- RULE 31 — STAR ABSORPTION CEILING (v6): When a team's primary scorer is absent and one player absorbs 35%+ of the scoring load, you MUST model that player's ceiling output — NOT their season average — in the total projection. Use their 75th-percentile output from last 10 games. Apply +25% FTA adjustment. Widen total ceiling +15 to +20 pts. If Star Absorption Ceiling scenario produces a combined total within 10 pts of the line: TOTAL = PASS. Do NOT recommend Under unless base case is 10+ pts below the line. Rule 31 fires simultaneously with Rule 12. Root cause: Penn 88, Yale 84 OT. TJ Power scored 44 pts (avg 15.8) after Roberts was ruled out. The model used Power's season average as the anchor. That was the error.
- RULE 32 — MARKET PRICE EFFICIENCY CHECK (v7): Run on EVERY game. Compute GAP = current spread minus model projected margin. If GAP >= 2 pts: apply -5% to favorite confidence and flag LINE EXCEEDS MODEL. If GAP >= 4 pts: PASS on favorite. Then run the bilateral underdog check. GAP 2-3 pts = ~52-57% baseline. GAP 4-6 pts = ~57-62%. GAP 6+ pts = ~62%+. Apply all standard rule modifiers. If adjusted underdog cover probability reaches 62%+: HIGH CONFIDENCE UNDERDOG COVER — 1.5 units. If 57-61%: UNDERDOG COVER — 1 unit. Below 57%: PASS both sides. Rule 32 does NOT override Rule 20.
- CONFIDENCE AND UNIT SIZING: Below 57% = PASS (0 units). 57-61% = RECOMMENDED (1 unit). 62%+ = HIGH CONFIDENCE (1.5 units). Rule 20 active + 57%+ = HIGH CONFIDENCE (1 unit). Rule 32 gap 3+ + 57%+ = HIGH CONFIDENCE (1.5 units). Rule 20 AND Rule 32 both active = HIGH CONFIDENCE (2 units). Always state unit size with every pick.
- DUAL BEST BETS: Issue a Best Bet for EVERY market that independently clears 57%. Do NOT limit to one pick. Spread and total are evaluated independently. Label clearly as BEST BET — SPREAD and BEST BET — TOTAL.
- Model the FLOOR scenario (Rule 9) for volatile scorers.
- Apply Rule 25 ASYMMETRICALLY: neutralize fatigue if both teams played prior night.
- Pull actual box scores, not just game summaries.
- Check BENCH WILDCARD ceilings (Rule 17) for every player on both rosters.
- Check TURNOVER CEILINGS (Rule 18).
- Check FREE THROW GENERATION (Rule 19) with Rule 30 context check. Apply Rule 31 FTA adjustment when absorbing player is under high usage.
- Apply SHOOTING EFFICIENCY DISCOUNT (Rule 22) for all lower-extremity injuries.
- Apply ROLE-SHIFT MODELING (Rule 24) for injured guards and wings.
- Apply TOURNAMENT FAVORITE ATS DISCOUNT (Rule 21) for split-series favorites laying 4-8 pts in tournament games.
- Apply HOME COURT H2H DISCOUNT (Rule 23) — 45% margin discount.
- Do NOT use ATS season records as a scoring factor.
- Do NOT use desperation/motivation as primary pick driver — cap at +0.5 pts.
- Explicitly calculate paint-point differential — do not skip Rule 8.
- Always run the Total Range Model (6 scenarios) before any over/under pick.
- Run Rule 26 Consistency Gate before every final output.
- Run Rule 27 Pre-Check BEFORE naming any Best Bet — not after.
- The model has a structural favorite bias built into the 11-factor scoring system. Rule 32 exists specifically to correct this. Always run it. Always state the GAP. Always evaluate the underdog side affirmatively.

"""

# ─────────────────────────────────────────────────────────────
# BATCH PROMPT — same as full prompt
# ─────────────────────────────────────────────────────────────
BATCH_MODEL_PROMPT = FULL_MODEL_PROMPT

# ─────────────────────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────────────────────
DELAY_BETWEEN_GAMES       = 45
MIN_CONFIDENCE_TO_FLAG    = 57
HIGH_CONFIDENCE_THRESHOLD = 62
SPORT                     = "NCAAMB"
SPORT_KEY                 = "basketball_ncaab"


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────
def _is_high_confidence(result):
    """
    A play qualifies as high confidence if:
    - Primary best bet confidence >= 62%
    - OR secondary best bet confidence >= 62%
    - OR Rule 32 gap >= 3 pts with either confidence >= 57%
    - OR Rule 20 active with either confidence >= 57%
    """
    picks = result.get("picks", {})
    conf  = picks.get("best_bet_confidence", 0)
    conf2 = picks.get("best_bet_2_confidence", 0)

    if isinstance(conf, int) and conf >= HIGH_CONFIDENCE_THRESHOLD:
        return True
    if isinstance(conf2, int) and conf2 >= HIGH_CONFIDENCE_THRESHOLD:
        return True

    try:
        gap = float(
            str(picks.get("rule32_gap", 0)).replace("—","0") or 0)
        if gap >= RULE32_STAR_GAP:
            if isinstance(conf, int) and conf >= 57:
                return True
            if isinstance(conf2, int) and conf2 >= 57:
                return True
    except (ValueError, TypeError):
        pass

    if picks.get("rule20_active"):
        if isinstance(conf, int) and conf >= 57:
            return True
        if isinstance(conf2, int) and conf2 >= 57:
            return True

    return False


def _is_recommended(result):
    """
    A play is recommended (57-61%) but not high confidence.
    """
    picks = result.get("picks", {})
    conf  = picks.get("best_bet_confidence", 0)
    conf2 = picks.get("best_bet_2_confidence", 0)

    has_recommended = (
        (isinstance(conf, int) and
         MIN_CONFIDENCE_TO_FLAG <= conf < HIGH_CONFIDENCE_THRESHOLD) or
        (isinstance(conf2, int) and
         MIN_CONFIDENCE_TO_FLAG <= conf2 < HIGH_CONFIDENCE_THRESHOLD)
    )

    return has_recommended and not _is_high_confidence(result)


def get_todays_games(target_date_str=None):
    """
    Fetch all college basketball games from The Odds API.
    target_date_str format: 'March 15, 2026'
    If None, uses today's date.
    """
    url = (f"https://api.the-odds-api.com/v4/sports/"
           f"{SPORT_KEY}/odds")
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "us",
        "markets":    "spreads,totals,h2h",
        "oddsFormat": "american",
        "bookmakers": "draftkings,fanduel,betmgm"
    }

    print("Fetching today's games from The Odds API...")

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()

        if isinstance(data, dict) and "message" in data:
            print(f"API error: {data['message']}")
            return []

        games = []
        for game in data:
            commence = game.get("commence_time", "")

            if target_date_str:
                try:
                    game_dt = datetime.fromisoformat(
                        commence.replace("Z", "+00:00"))
                    game_date_str = game_dt.strftime("%B %d, %Y")
                    game_date_clean = game_date_str.replace(
                        " 0", " ").strip()
                    target_clean = target_date_str.replace(
                        " 0", " ").strip()
                    if game_date_clean != target_clean:
                        continue
                except Exception:
                    pass

            home = game.get("home_team", "Unknown")
            away = game.get("away_team", "Unknown")

            spread_info = "No line available"
            total_info  = "No total available"
            ml_info     = "No ML available"

            for bookmaker in game.get("bookmakers", []):
                if bookmaker.get("title") == "DraftKings":
                    for market in bookmaker.get("markets", []):
                        if market["key"] == "spreads":
                            for outcome in market.get("outcomes", []):
                                if outcome["name"] == home:
                                    spread_info = (
                                        f"{home} "
                                        f"{outcome['point']:+.1f} "
                                        f"({outcome['price']:+d})"
                                    )
                        elif market["key"] == "totals":
                            for outcome in market.get("outcomes", []):
                                if outcome["name"] == "Over":
                                    total_info = (
                                        f"O/U {outcome['point']} "
                                        f"(O{outcome['price']:+d})"
                                    )
                        elif market["key"] == "h2h":
                            for outcome in market.get("outcomes", []):
                                if outcome["name"] == home:
                                    ml_info = (
                                        f"{home} ML "
                                        f"{outcome['price']:+d}"
                                    )

            games.append({
                "home_team":     home,
                "away_team":     away,
                "commence_time": commence,
                "spread":        spread_info,
                "total":         total_info,
                "moneyline":     ml_info,
                "raw":           game
            })

        print(f"Found {len(games)} games.")
        return games

    except Exception as e:
        print(f"Error fetching games: {e}")
        return []


def format_game_data_for_analysis(game, target_date):
    return {
        "team1":          game["away_team"],
        "team2":          game["home_team"],
        "sport":          SPORT,
        "game_date":      target_date,
        "context":        "NCAA Men's Basketball",
        "betting_lines": (
            f"Game: {game['away_team']} @ {game['home_team']}\n"
            f"Commence: {game['commence_time']}\n"
            f"  DraftKings Spread: {game['spread']}\n"
            f"  DraftKings Total: {game['total']}\n"
            f"  DraftKings ML: {game['moneyline']}"
        ),
        "data_timestamp": datetime.now().isoformat()
    }


def generate_master_summary_pdf(all_results, target_date,
                                 output_dir="reports"):
    os.makedirs(output_dir, exist_ok=True)
    date_str = target_date.replace("/","-").replace(" ","_")
    filename = f"{output_dir}/MASTER_SUMMARY_{date_str}.pdf"

    doc = SimpleDocTemplate(
        filename, pagesize=letter,
        rightMargin=0.5*inch, leftMargin=0.5*inch,
        topMargin=0.5*inch,  bottomMargin=0.5*inch
    )

    NAVY   = colors.HexColor("#0D2240")
    GOLD   = colors.HexColor("#C8A951")
    GREEN  = colors.HexColor("#1A7A3E")
    RED    = colors.HexColor("#CC0000")
    LGRAY  = colors.HexColor("#F5F5F5")
    MGRAY  = colors.HexColor("#888888")
    DGRAY  = colors.HexColor("#333333")
    LGREEN = colors.HexColor("#E8F8E8")
    YELLOW = colors.HexColor("#FFFBE6")
    ORANGE = colors.HexColor("#E07000")

    def PS(name, **kw):
        s = ParagraphStyle(name)
        d = dict(fontSize=9, fontName="Helvetica",
                 textColor=DGRAY, spaceAfter=3, leading=13)
        d.update(kw)
        for k, v in d.items():
            setattr(s, k, v)
        return s

    def safe(text):
        return (str(text or "—")
                .replace('&','&amp;')
                .replace('<','&lt;')
                .replace('>','&gt;'))

    story = []

    # ── HEADER ──
    story.append(Paragraph(
        "KAPERNICUS PICKS — MASTER SUMMARY",
        PS("H", fontSize=18, fontName="Helvetica-Bold",
           textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph(
        f"NCAA Men's Basketball | {target_date}",
        PS("ST", fontSize=11, textColor=MGRAY,
           alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph(
        f"Generated: "
        f"{datetime.now().strftime('%B %d, %Y %I:%M %p')} | "
        f"Games analyzed: {len(all_results)}",
        PS("DT", fontSize=9, textColor=MGRAY,
           alignment=TA_CENTER, spaceAfter=10)))
    story.append(HRFlowable(
        width="100%", thickness=2,
        color=NAVY, spaceAfter=12))

    # ── HIGH CONFIDENCE PLAYS ──
    high_conf_results = [r for r in all_results
                         if _is_high_confidence(r)]
    rec_results       = [r for r in all_results
                         if _is_recommended(r)]

    if high_conf_results:
        story.append(Paragraph(
            f"★★  HIGH CONFIDENCE PLAYS  "
            f"({len(high_conf_results)} found)",
            PS("BBH", fontSize=13, fontName="Helvetica-Bold",
               textColor=colors.white, backColor=GREEN,
               alignment=TA_CENTER, borderPad=6,
               spaceAfter=8, leading=20)))

        # Table now has Best Bet 1 AND Best Bet 2 columns
        bb_data = [["GAME", "BEST BET 1",
                    "BEST BET 2",
                    "SPREAD", "TOTAL", "FLAGS"]]

        for result in sorted(
            high_conf_results,
            key=lambda x: x.get("picks", {}).get(
                "best_bet_confidence", 0),
            reverse=True
        ):
            picks = result.get("picks", {})
            game  = result.get("game_label", "Unknown")

            flags = []
            if picks.get("rule20_active"):
                flags.append("R20")
            if picks.get("rule31_active"):
                flags.append("R31")
            try:
                gap = float(str(
                    picks.get("rule32_gap", 0)
                ).replace("—","0") or 0)
                if gap >= 2:
                    flags.append(f"R32({gap})")
            except (ValueError, TypeError):
                pass

            conf1  = picks.get("best_bet_confidence", 0)
            units1 = format_unit_label(
                conf1 if isinstance(conf1, int) else 0, picks)
            bb1    = (f"{safe(str(picks.get('best_bet','—'))[:28])}"
                      f" ({conf1}% {units1})")

            bb2    = picks.get("best_bet_2", "PASS")
            conf2  = picks.get("best_bet_2_confidence", 0)
            bm2    = picks.get("best_bet_2_market", "")
            units2 = format_unit_label(
                conf2 if isinstance(conf2, int) else 0, picks)

            if (str(bb2).upper() != "PASS" and bb2 != "—"
                    and isinstance(conf2, int) and conf2 >= 57):
                bb2_str = (f"{safe(str(bb2)[:22])}"
                           f" ({conf2}% {units2})")
            else:
                bb2_str = "—"

            bb_data.append([
                safe(game),
                bb1,
                bb2_str,
                safe(f"{picks.get('spread_pick','—')} "
                     f"{picks.get('spread_line','—')}"),
                safe(f"{picks.get('total_pick','—')} "
                     f"{picks.get('total_line','—')}"),
                safe(", ".join(flags) if flags else "—")
            ])

        bb_table = Table(
            bb_data,
            colWidths=[1.1*inch, 1.5*inch, 1.5*inch,
                       0.95*inch, 0.9*inch, 0.85*inch]
        )
        bb_table.setStyle(TableStyle([
            ('FONTNAME',  (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',  (0,0), (-1,-1), 8),
            ('BACKGROUND',(0,0), (-1,0), NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID',      (0,0), (-1,-1), 0.4, MGRAY),
            ('VALIGN',    (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING',   (0,0), (-1,-1), 4),
            ('ROWBACKGROUNDS',(0,1), (-1,-1),
             [LGREEN, colors.HexColor("#D4EDDA")]),
        ]))
        story.append(bb_table)
        story.append(Spacer(1, 12))

    # ── RECOMMENDED PLAYS ──
    if rec_results:
        story.append(Paragraph(
            f"★  RECOMMENDED PLAYS  ({len(rec_results)} found)",
            PS("RH", fontSize=12, fontName="Helvetica-Bold",
               textColor=colors.white,
               backColor=colors.HexColor("#856404"),
               alignment=TA_CENTER, borderPad=5,
               spaceAfter=6, leading=18)))

        rec_data = [["GAME", "BEST BET 1",
                     "BEST BET 2", "SPREAD", "TOTAL"]]

        for result in sorted(
            rec_results,
            key=lambda x: x.get("picks", {}).get(
                "best_bet_confidence", 0),
            reverse=True
        ):
            picks = result.get("picks", {})
            game  = result.get("game_label", "Unknown")

            conf1  = picks.get("best_bet_confidence", 0)
            units1 = format_unit_label(
                conf1 if isinstance(conf1, int) else 0, picks)
            bb1    = (f"{safe(str(picks.get('best_bet','—'))[:28])}"
                      f" ({conf1}% {units1})")

            bb2   = picks.get("best_bet_2", "PASS")
            conf2 = picks.get("best_bet_2_confidence", 0)
            units2= format_unit_label(
                conf2 if isinstance(conf2, int) else 0, picks)

            if (str(bb2).upper() != "PASS" and bb2 != "—"
                    and isinstance(conf2, int) and conf2 >= 57):
                bb2_str = (f"{safe(str(bb2)[:22])}"
                           f" ({conf2}% {units2})")
            else:
                bb2_str = "—"

            rec_data.append([
                safe(game),
                bb1,
                bb2_str,
                safe(f"{picks.get('spread_pick','—')} "
                     f"{picks.get('spread_line','—')}"),
                safe(f"{picks.get('total_pick','—')} "
                     f"{picks.get('total_line','—')}"),
            ])

        rec_table = Table(
            rec_data,
            colWidths=[1.1*inch, 1.6*inch, 1.6*inch,
                       1.0*inch, 0.95*inch]
        )
        rec_table.setStyle(TableStyle([
            ('FONTNAME',  (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',  (0,0), (-1,-1), 8),
            ('BACKGROUND',(0,0), (-1,0), NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID',      (0,0), (-1,-1), 0.4, MGRAY),
            ('VALIGN',    (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING',   (0,0), (-1,-1), 4),
            ('ROWBACKGROUNDS',(0,1), (-1,-1),
             [YELLOW, colors.HexColor("#FFF3CD")]),
        ]))
        story.append(rec_table)
        story.append(Spacer(1, 12))

    # ── ACTIVE RULE FLAGS ──
    r20_games = [r for r in all_results
                 if r.get("picks", {}).get("rule20_active")]
    r31_games = [r for r in all_results
                 if r.get("picks", {}).get("rule31_active")]

    if r20_games or r31_games:
        story.append(Paragraph(
            "ACTIVE RULE FLAGS",
            PS("RFH", fontSize=11, fontName="Helvetica-Bold",
               textColor=colors.white, backColor=RED,
               alignment=TA_CENTER, borderPad=5,
               spaceAfter=6, leading=18)))

        for r in r20_games:
            story.append(Paragraph(
                f"⚑  RULE 20 SHARP FADE — "
                f"{safe(r.get('game_label','Unknown'))}",
                PS(f"R20g{id(r)}",
                   fontSize=9, fontName="Helvetica-Bold",
                   textColor=colors.white, backColor=RED,
                   borderPad=4, spaceAfter=3, leading=14)))

        for r in r31_games:
            story.append(Paragraph(
                f"⚑  RULE 31 STAR ABSORPTION — "
                f"{safe(r.get('game_label','Unknown'))}",
                PS(f"R31g{id(r)}",
                   fontSize=9, fontName="Helvetica-Bold",
                   textColor=colors.white, backColor=ORANGE,
                   borderPad=4, spaceAfter=3, leading=14)))

        story.append(Spacer(1, 12))

    # ── ALL GAMES TABLE ──
    story.append(Paragraph(
        "ALL GAMES",
        PS("AGH", fontSize=11, fontName="Helvetica-Bold",
           textColor=colors.white, backColor=NAVY,
           alignment=TA_CENTER, borderPad=5,
           spaceAfter=6, leading=18)))

    table_data = [
        ["GAME", "SPREAD", "CONF",
         "TOTAL", "CONF", "BEST BET 1", "BEST BET 2"]
    ]

    for result in all_results:
        picks = result.get("picks", {})
        game  = result.get("game_label", "Unknown")
        sc    = picks.get("spread_confidence", "—")
        tc    = picks.get("total_confidence", "—")

        bb2     = picks.get("best_bet_2", "PASS")
        conf2   = picks.get("best_bet_2_confidence", 0)
        units2  = format_unit_label(
            conf2 if isinstance(conf2, int) else 0, picks)
        bb2_disp = "—"
        if (str(bb2).upper() != "PASS" and bb2 != "—"
                and isinstance(conf2, int) and conf2 >= 57):
            bb2_disp = f"{safe(str(bb2)[:20])} ({conf2}%)"

        table_data.append([
            safe(game),
            safe(f"{picks.get('spread_pick','—')} "
                 f"{picks.get('spread_line','—')}"),
            f"{sc}%" if isinstance(sc, int) else "—",
            safe(f"{picks.get('total_pick','—')} "
                 f"{picks.get('total_line','—')}"),
            f"{tc}%" if isinstance(tc, int) else "—",
            safe(str(picks.get("best_bet","—"))[:25]),
            bb2_disp
        ])

    row_styles = [
        ('FONTNAME',  (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',  (0,0), (-1,-1), 7.5),
        ('BACKGROUND',(0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID',      (0,0), (-1,-1), 0.3, MGRAY),
        ('VALIGN',    (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING',   (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS',(0,1), (-1,-1),
         [colors.white, LGRAY]),
    ]

    for i, result in enumerate(all_results, start=1):
        picks   = result.get("picks", {})
        bb_conf = picks.get("best_bet_confidence", 0)
        if _is_high_confidence(result):
            row_styles.append(
                ('BACKGROUND', (0,i), (-1,i), LGREEN))
            row_styles.append(
                ('FONTNAME', (0,i), (-1,i), 'Helvetica-Bold'))
        elif _is_recommended(result):
            row_styles.append(
                ('BACKGROUND', (0,i), (-1,i), YELLOW))

    full_table = Table(
        table_data,
        colWidths=[1.1*inch, 1.0*inch, 0.4*inch,
                   0.95*inch, 0.4*inch, 1.1*inch, 1.1*inch]
    )
    full_table.setStyle(TableStyle(row_styles))
    story.append(full_table)
    story.append(Spacer(1, 20))

    # ── STATISTICS ──
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=MGRAY, spaceAfter=8))

    total_games = len(all_results)
    r20_count   = len(r20_games)
    r31_count   = len(r31_games)
    pass_count  = sum(
        1 for r in all_results
        if "PASS" in str(
            r.get("picks",{}).get(
                "spread_recommendation","")).upper()
    )
    r32_count = sum(
        1 for r in all_results
        if float(str(r.get("picks",{}).get(
            "rule32_gap",0)).replace("—","0") or 0) >= 2
    )

    stats_data = [
        ["BATCH STATISTICS", "", "", ""],
        ["Total Games Analyzed", str(total_games),
         "Sharp Fade (Rule 20)", str(r20_count)],
        [f"High Confidence ({HIGH_CONFIDENCE_THRESHOLD}%+)",
         str(len(high_conf_results)),
         "Star Absorption (Rule 31)", str(r31_count)],
        [f"Recommended ({MIN_CONFIDENCE_TO_FLAG}-"
         f"{HIGH_CONFIDENCE_THRESHOLD-1}%)",
         str(len(rec_results)),
         "Line Exceeds Model (Rule 32)", str(r32_count)],
        ["Spread PASS Count", str(pass_count), "", ""],
    ]

    stats_table = Table(
        stats_data,
        colWidths=[2.2*inch, 0.8*inch, 2.2*inch, 0.8*inch]
    )
    stats_table.setStyle(TableStyle([
        ('FONTNAME',  (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',  (0,0), (-1,-1), 9),
        ('BACKGROUND',(0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('SPAN',      (0,0), (-1,0)),
        ('ALIGN',     (0,0), (-1,0), 'CENTER'),
        ('GRID',      (0,0), (-1,-1), 0.3, MGRAY),
        ('ROWBACKGROUNDS',(0,1), (-1,-1),
         [colors.white, LGRAY]),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 10))

    # ── FOOTER ──
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=MGRAY, spaceAfter=4))
    story.append(Paragraph(
        f"32-Rule Model v7 | Batch Run | "
        f"{datetime.now().strftime('%B %d, %Y %I:%M %p')}",
        PS("FT", fontSize=7, textColor=MGRAY,
           alignment=TA_CENTER)))
    story.append(Paragraph(
        "FOR ENTERTAINMENT AND INFORMATIONAL PURPOSES ONLY. "
        "Gambling involves risk. Helpline: 1-800-GAMBLER.",
        PS("DS", fontSize=7, textColor=RED,
           alignment=TA_CENTER)))

    doc.build(story)
    print(f"\nMaster summary saved: {filename}")
    return filename


def save_batch_log(all_results, target_date):
    log_file = "picks_log.json"
    existing = []

    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                existing = json.load(f)
        except Exception:
            existing = []

    for result in all_results:
        picks = result.get("picks", {})
        conf  = picks.get("best_bet_confidence", 0)
        conf2 = picks.get("best_bet_2_confidence", 0)

        entry = {
            "date":                  target_date,
            "game":                  result.get("game_label","Unknown"),
            "sport":                 SPORT,
            "context":               "NCAA Men's Basketball",
            "spread_pick":           picks.get("spread_pick"),
            "spread_line":           picks.get("spread_line"),
            "spread_confidence":     picks.get("spread_confidence"),
            "spread_recommendation": picks.get("spread_recommendation"),
            "total_pick":            picks.get("total_pick"),
            "total_line":            picks.get("total_line"),
            "total_confidence":      picks.get("total_confidence"),
            "best_bet":              picks.get("best_bet"),
            "best_bet_confidence":   conf,
            "best_bet_units":        get_unit_size(
                conf if isinstance(conf,int) else 0, picks),
            "best_bet_tier":         get_tier_label(
                conf if isinstance(conf,int) else 0, picks),
            "best_bet_2":            picks.get("best_bet_2","PASS"),
            "best_bet_2_confidence": conf2,
            "best_bet_2_market":     picks.get("best_bet_2_market",""),
            "best_bet_2_units":      get_unit_size(
                conf2 if isinstance(conf2,int) else 0, picks),
            "predicted_score":       picks.get("predicted_score"),
            "rule20_active":         picks.get("rule20_active"),
            "rule31_active":         picks.get("rule31_active"),
            "rule32_gap":            picks.get("rule32_gap"),
            "rule32_recommendation": picks.get("rule32_recommendation"),
            "pdf_report":            result.get("pdf_path",""),
            "result":                "PENDING",
            "batch_run":             True
        }
        existing.append(entry)

    with open(log_file, 'w') as f:
        json.dump(existing, f, indent=2)

    print(f"All {len(all_results)} picks logged to {log_file}")


def run_batch(target_date=None):
    # ── SETUP CHECKS ──
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nERROR: ANTHROPIC_API_KEY not set in Replit Secrets")
        return

    # ── DATE SETUP ──
    if target_date is None:
        target_date = datetime.now().strftime("%B %-d, %Y")

    print("\n" + "="*60)
    print("   BATCH ANALYZER — 32-RULE MODEL v7")
    print(f"   Date: {target_date}")
    print("="*60)

    # ── FETCH GAMES ──
    games = get_todays_games(target_date)

    if not games:
        print(f"\nNo games found for {target_date}.")
        print("  1. No games scheduled for that date")
        print("  2. Lines not yet posted")
        print("  3. Check Odds API key")
        return

    print(f"\nFound {len(games)} games to analyze.")
    print("="*60)

    print("\nGames queued for analysis:")
    for i, game in enumerate(games, 1):
        print(f"  {i}. {game['away_team']} @ {game['home_team']}")
        print(f"     Spread: {game['spread']}")
        print(f"     Total:  {game['total']}")

    est_minutes = (len(games) * (90 + DELAY_BETWEEN_GAMES)) / 60
    print(f"\nEstimated time: "
          f"{est_minutes:.0f}-{est_minutes*1.3:.0f} minutes")
    print("Keep this tab open and your iPad plugged in.")
    print("\nStarting analysis in 5 seconds...")
    time.sleep(5)

    # ── ANALYZE EACH GAME ──
    all_results = []

    for i, game in enumerate(games, 1):
        game_label = (f"{game['away_team']} "
                      f"@ {game['home_team']}")

        print(f"\n{'='*60}")
        print(f"[{i}/{len(games)}] {game_label}")
        print(f"{'='*60}")

        game_data = format_game_data_for_analysis(
            game, target_date)

        try:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(
                    "Analysis exceeded 5 minute limit")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(300)

            print("  [0:00] Sending to Claude...")
            analysis_result = run_analysis(
                game_data, BATCH_MODEL_PROMPT)

            signal.alarm(0)

            if ("error" in analysis_result and
                    not analysis_result.get("full_analysis")):
                print(f"  ERROR: {analysis_result['error']}")
                all_results.append({
                    "game_label": game_label,
                    "picks":      {},
                    "error":      analysis_result["error"],
                    "pdf_path":   ""
                })
                continue

            try:
                pdf_path = generate_pdf_report(
                    game_data, analysis_result)
            except Exception as e:
                print(f"  PDF error: {e}")
                pdf_path = ""

            picks = analysis_result.get("picks", {})
            conf  = picks.get("best_bet_confidence","—")
            conf2 = picks.get("best_bet_2_confidence", 0)

            print(f"  SPREAD:     "
                  f"{picks.get('spread_pick','—')} "
                  f"{picks.get('spread_line','—')} | "
                  f"{picks.get('spread_confidence','—')}% | "
                  f"{picks.get('spread_recommendation','—')}")
            print(f"  TOTAL:      "
                  f"{picks.get('total_pick','—')} "
                  f"{picks.get('total_line','—')} | "
                  f"{picks.get('total_confidence','—')}%")
            print(f"  BEST BET 1: "
                  f"{picks.get('best_bet','—')} ({conf}%)")

            if (picks.get("best_bet_2") and
                    str(picks.get("best_bet_2")).upper() != "PASS"
                    and isinstance(conf2, int) and conf2 >= 57):
                u2 = format_unit_label(conf2, picks)
                bm2 = picks.get("best_bet_2_market","")
                print(f"  BEST BET 2: "
                      f"{picks.get('best_bet_2','—')} "
                      f"({conf2}% — {u2}) [{bm2}]")

            if picks.get("rule20_active"):
                print("  ⚑ RULE 20 SHARP FADE ACTIVE")
            if picks.get("rule31_active"):
                print("  ⚑ RULE 31 STAR ABSORPTION ACTIVE")

            all_results.append({
                "game_label": game_label,
                "game_data":  game_data,
                "picks":      picks,
                "pdf_path":   pdf_path
            })

        except Exception as e:
            print(f"  Unexpected error: {e}")
            all_results.append({
                "game_label": game_label,
                "picks":      {},
                "error":      str(e),
                "pdf_path":   ""
            })

        if i < len(games):
            print(f"\n  Waiting {DELAY_BETWEEN_GAMES}s "
                  f"before next game...")
            time.sleep(DELAY_BETWEEN_GAMES)

    # ── GENERATE MASTER SUMMARY ──
    print(f"\n{'='*60}")
    print("All games analyzed. Generating master summary...")
    master_pdf = generate_master_summary_pdf(
        all_results, target_date)

    # ── SAVE TO LOG ──
    print("Saving all picks to log...")
    save_batch_log(all_results, target_date)

    # ── SEND BATCH SUMMARY EMAIL ──
    print("\nSending batch summary email...")
    from emailer import send_batch_summary
    send_batch_summary(all_results, target_date, master_pdf)

    # ── POST TO X ──
    from twitter_poster import post_picks_from_batch
    posted_picks = post_picks_from_batch(
        all_results, target_date)

    # ── UPDATE TRACKER ──
    if posted_picks:
        from tracker import add_posted_picks
        add_posted_picks(posted_picks)


    # ── FINAL CONSOLE SUMMARY ──
    print(f"\n{'='*60}")
    print("   BATCH COMPLETE")
    print(f"{'='*60}")
    print(f"  Games analyzed: {len(all_results)}")
    print(f"  Successful:     "
          f"{sum(1 for r in all_results if r.get('picks'))}")
    print(f"  Errors:         "
          f"{sum(1 for r in all_results if r.get('error'))}")

    hc = [r for r in all_results if _is_high_confidence(r)]
    rc = [r for r in all_results if _is_recommended(r)]

    print(f"\n  High confidence plays "
          f"({HIGH_CONFIDENCE_THRESHOLD}%+): {len(hc)}")
    for r in sorted(
        hc,
        key=lambda x: x["picks"].get(
            "best_bet_confidence", 0),
        reverse=True
    ):
        p     = r["picks"]
        conf  = p.get("best_bet_confidence", 0)
        units = format_unit_label(conf, p)
        tier  = get_tier_label(conf, p)
        print(f"    ★★ {r['game_label']}")
        print(f"       BB1: {p.get('best_bet','—')} "
              f"({conf}% — {tier} — {units})")
        bb2  = p.get("best_bet_2","PASS")
        bc2  = p.get("best_bet_2_confidence", 0)
        bm2  = p.get("best_bet_2_market","")
        if (str(bb2).upper() != "PASS" and
                isinstance(bc2, int) and bc2 >= 57):
            u2 = format_unit_label(bc2, p)
            t2 = get_tier_label(bc2, p)
            print(f"       BB2: {bb2} "
                  f"({bc2}% — {t2} — {u2}) [{bm2}]")

    print(f"\n  Recommended plays "
          f"({MIN_CONFIDENCE_TO_FLAG}-"
          f"{HIGH_CONFIDENCE_THRESHOLD-1}%): {len(rc)}")
    for r in sorted(
        rc,
        key=lambda x: x["picks"].get(
            "best_bet_confidence", 0),
        reverse=True
    ):
        p     = r["picks"]
        conf  = p.get("best_bet_confidence", 0)
        units = format_unit_label(conf, p)
        print(f"    ★  {r['game_label']}")
        print(f"       BB1: {p.get('best_bet','—')} "
              f"({conf}% — {units})")

    print(f"\n  Master summary PDF: {master_pdf}")
    print("  Download from reports/ folder.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # Option 1: Analyze today's games
    run_batch()

    # Option 2: Analyze a specific date — uncomment and edit:
    # run_batch("March 17, 2026")
