from confidence_utils import (
    get_confidence_tier, get_unit_size,
    get_row_color, get_star,
    format_unit_label, get_tier_label
)

print("\n" + "="*55)
print("   THRESHOLD VERIFICATION TEST")
print("="*55)

test_cases = [
    # (conf, picks_dict, expected_tier, expected_units)
    (54, {},                                    "pass",            0),
    (56, {},                                    "pass",            0),
    (57, {},                                    "recommended",     1.0),
    (59, {},                                    "recommended",     1.0),
    (61, {},                                    "recommended",     1.0),
    (62, {},                                    "high_confidence", 1.5),
    (66, {},                                    "high_confidence", 1.5),
    (57, {"rule20_active": True},               "high_confidence", 1.0),
    (59, {"rule20_active": True},               "high_confidence", 1.0),
    (57, {"rule32_gap": 3.5},                   "high_confidence", 1.5),
    (57, {"rule20_active": True,
          "rule32_gap": 3.5},                   "high_confidence", 2.0),
]

all_passed = True

print(f"\n{'Conf':<6} {'Tier':<20} {'Units':<10} "
      f"{'Star':<6} {'Color':<12} {'Status'}")
print("-"*65)

for conf, picks, exp_tier, exp_units in test_cases:
    tier  = get_confidence_tier(conf, picks)
    units = get_unit_size(conf, picks)
    star  = get_star(conf, picks).strip()
    color = get_row_color(conf, picks)
    label = format_unit_label(conf, picks)

    passed = (tier == exp_tier and units == exp_units)
    status = "PASS" if passed else "FAIL"

    if not passed:
        all_passed = False
        print(f"{conf:<6} {tier:<20} {label:<10} "
              f"{star:<6} {color:<12} {status}"
              f"  (expected tier={exp_tier}, "
              f"units={exp_units})")
    else:
        print(f"{conf:<6} {tier:<20} {label:<10} "
              f"{star:<6} {color:<12} {status}")

print("-"*65)

if all_passed:
    print("\nAll thresholds verified correctly.")
    print("\nSUMMARY:")
    print("  Below 57%          PASS            0 units")
    print("  57-61%             RECOMMENDED     1.0 units")
    print("  62%+               HIGH CONFIDENCE 1.5 units")
    print("  Rule 20 + 57%+     HIGH CONFIDENCE 1.0 units")
    print("  Rule 32 gap 3+     HIGH CONFIDENCE 1.5 units")
    print("  Rule 20 + Rule 32  HIGH CONFIDENCE 2.0 units")
else:
    print("\nSome tests FAILED — check confidence_utils.py")

print("="*55 + "\n")
