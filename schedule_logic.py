"""Calendar recurrence anchored to the originally entered local date."""

import calendar
from datetime import date, timedelta


def occurrence_on_or_after(anchor: date, repeat_rule: str, target: date) -> date | None:
    if repeat_rule == "none":
        return anchor if anchor >= target else None
    if target <= anchor:
        return anchor
    if repeat_rule == "weekly":
        weeks = (target - anchor).days // 7
        result = anchor + timedelta(weeks=weeks)
        return result if result >= target else result + timedelta(days=7)

    def clamped(year: int, month: int) -> date:
        return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))

    if repeat_rule == "monthly":
        months = (target.year - anchor.year) * 12 + target.month - anchor.month
        index = anchor.year * 12 + anchor.month - 1 + months
        result = clamped(index // 12, index % 12 + 1)
        if result < target:
            index += 1
            result = clamped(index // 12, index % 12 + 1)
        return result
    if repeat_rule == "yearly":
        result = clamped(target.year, anchor.month)
        return result if result >= target else clamped(target.year + 1, anchor.month)
    raise ValueError("Unsupported repeat rule")
