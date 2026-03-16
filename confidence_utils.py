# ─────────────────────────────────────────────────────────────
# CONFIDENCE THRESHOLDS — SINGLE SOURCE OF TRUTH
# Change values here and they update everywhere automatically
# ─────────────────────────────────────────────────────────────

MODEL_PASS_FLOOR          = 57
RECOMMENDED_FLOOR         = 57
RECOMMENDED_CEILING       = 61
HIGH_CONF_FLOOR           = 62
RULE32_STAR_GAP           = 3.0

UNIT_SIZE = {
    "pass":           0,
    "recommended":    1.0,
    "high_confidence":1.5,
    "rule32_boosted": 1.5,
    "rule20_fade":    1.0,
    "rule20_and_r32": 2.0,
}


def get_confidence_tier(conf, picks=None):
    if not isinstance(conf, int):
        return "pass"
    picks = picks or {}
    r20 = picks.get("rule20_active", False)
    try:
        r32_gap = float(
            str(picks.get("rule32_gap", 0)).replace("—", "0") or 0)
    except (ValueError, TypeError):
        r32_gap = 0

    if r20 and conf >= MODEL_PASS_FLOOR:
        return "high_confidence"
    if r32_gap >= RULE32_STAR_GAP and conf >= 57:
        return "high_confidence"
    if conf >= HIGH_CONF_FLOOR:
        return "high_confidence"
    if conf >= RECOMMENDED_FLOOR:
        return "recommended"
    return "pass"


def get_unit_size(conf, picks=None):
    picks = picks or {}
    tier  = get_confidence_tier(conf, picks)
    if tier == "pass":
        return 0
    r20 = picks.get("rule20_active", False)
    try:
        r32_gap = float(
            str(picks.get("rule32_gap", 0)).replace("—", "0") or 0)
    except (ValueError, TypeError):
        r32_gap = 0

    if r20 and r32_gap >= RULE32_STAR_GAP:
        return UNIT_SIZE["rule20_and_r32"]
    if r20:
        return UNIT_SIZE["rule20_fade"]
    if r32_gap >= RULE32_STAR_GAP and conf >= 57:
        return UNIT_SIZE["rule32_boosted"]
    return UNIT_SIZE.get(tier, 0)


def get_row_color(conf, picks=None):
    tier = get_confidence_tier(conf, picks)
    if tier == "high_confidence":
        return "#D4EDDA"
    if tier == "recommended":
        return "#FFF9E6"
    return "white"


def get_star(conf, picks=None):
    tier = get_confidence_tier(conf, picks)
    if tier == "high_confidence":
        return "★★ "
    if tier == "recommended":
        return "★ "
    return ""


def get_conf_text_color(conf):
    if not isinstance(conf, int):
        return "#6C757D"
    if conf >= HIGH_CONF_FLOOR:
        return "#1A7A3E"
    if conf >= RECOMMENDED_FLOOR:
        return "#856404"
    return "#721C24"


def format_unit_label(conf, picks=None):
    units = get_unit_size(conf, picks)
    if units == 0:
        return "PASS"
    return f"{units} units"


def get_tier_label(conf, picks=None):
    tier = get_confidence_tier(conf, picks)
    return tier.upper().replace("_", " ")
