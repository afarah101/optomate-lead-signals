"""Calibration: pick the hot and cold test groups at random with a seed fixed in docs/decisions/calibration-plan.md."""

import random


class NotEnoughEligibleLeads(ValueError):
    pass


def _draw(rng: random.Random, licence_numbers: list[str], size: int) -> list[str]:
    # Only Random.random() is promised stable across Python versions (sample() is not), so draw one key per candidate.
    keys = {licence: rng.random() for licence in licence_numbers}
    return sorted(sorted(licence_numbers, key=keys.__getitem__)[:size])


def select_calibration_groups(ranked_rows: list[dict], seed: int, group_size: int = 15) -> dict:
    eligible = {"hot": set(), "cold": set()}
    for row in ranked_rows:
        if row.get("eligible") == "yes" and row.get("band") in eligible:  # middle leads never enter a group
            eligible[row["band"]].add(row["licence_number"])

    if len(eligible["hot"]) < group_size or len(eligible["cold"]) < group_size:
        raise NotEnoughEligibleLeads(
            f"need {group_size} eligible hot and {group_size} eligible cold leads; "
            f"have {len(eligible['hot'])} hot and {len(eligible['cold'])} cold"
        )

    rng = random.Random(seed)
    return {
        "seed": seed,
        "hot": _draw(rng, sorted(eligible["hot"]), group_size),
        "cold": _draw(rng, sorted(eligible["cold"]), group_size),
    }
