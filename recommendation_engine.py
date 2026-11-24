"""Deterministic, private two-person balance scoring for P0 TWO-PICK.

This is a rules-based DEMO option selector, not a real-price or booking verifier.
It never returns individual member scores or conditions to API callers.
"""

import re
from typing import Sequence


def _tokens(raw: str) -> set[str]:
    """Split structured comma/semicolon/newline tags; no semantic inference."""
    return {part.strip().casefold() for part in re.split(r"[,;\n]", raw) if part.strip()}


def _normalize(value: str) -> str:
    return value.strip().casefold()


def choose_balanced_option(options: Sequence, conditions: Sequence):
    """Return the most balanced *eligible* public option, or None.

    - Per-member max_budget is the individual's ceiling on the TWO-PERSON
      TOTAL, never a per-person price. We enforce both ceilings independently.
    - Time slots and tags use exact normalized matching, not NLP.
    - Any budget/time/avoidance conflict disqualifies an option.
    - Eligible options prioritize max(min satisfaction), then lower imbalance,
      then more total preference matches, then lower total estimated cost.
    - Scores remain server-side only. Stable tie-breaks ignore input order.
    """
    if len(conditions) != 2:
        raise ValueError("Exactly two private condition rows are required")

    ranked = []
    for option in options:
        tags = {_normalize(tag) for tag in option.tags}
        slot = _normalize(option.time_slot)
        scores = []
        for condition in conditions:
            if option.estimated_total_cost_krw > condition.max_budget:
                break
            if slot not in _tokens(condition.available_time):
                break
            if tags & _tokens(condition.avoidances):
                break
            hits = len(tags & _tokens(condition.preferences))
            scores.append(min(100, 50 + hits * 10))

        if len(scores) != 2:
            continue
        priority = (
            -min(scores),
            abs(scores[0] - scores[1]),
            -sum(scores),
            option.estimated_total_cost_krw,
            _normalize(option.title),
            slot,
            tuple(sorted(tags)),
        )
        ranked.append((priority, option))

    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]
