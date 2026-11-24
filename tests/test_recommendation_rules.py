import unittest
from types import SimpleNamespace

from recommendation_engine import choose_balanced_option


def condition(budget=30000, time="토 18:00-20:00", pref="", avoid=""):
    return SimpleNamespace(
        max_budget=budget,
        available_time=time,
        preferences=pref,
        avoidances=avoid,
    )


def option(title, cost=18000, time="토 18:00-20:00", tags=None):
    return SimpleNamespace(
        title=title,
        estimated_total_cost_krw=cost,
        time_slot=time,
        tags=tags or [],
    )


class RecommendationRulesTests(unittest.TestCase):
    def test_both_ceilings_apply_to_total_not_sum(self):
        a, b = condition(30000), condition(20000)
        selected = choose_balanced_option(
            [option("over B", 25000), option("within both", 19000)], [a, b]
        )
        self.assertEqual(selected.title, "within both")

    def test_minimum_satisfaction_beats_one_sided_preference(self):
        a = condition(pref="한식, 조용한 곳")
        b = condition(pref="조용한 곳")
        selected = choose_balanced_option(
            [option("A only", 12000, tags=["한식"]),
             option("both", 18000, tags=["조용한 곳"])],
            [a, b],
        )
        self.assertEqual(selected.title, "both")

    def test_avoidance_is_hard_filter(self):
        a = condition(avoid="매운 음식")
        b = condition()
        self.assertIsNone(choose_balanced_option(
            [option("spicy", tags=["매운 음식"])], [a, b]))

    def test_time_exact_slot_not_language_guess(self):
        a = condition(time="토 18:00-20:00, 일 14:00-16:00")
        b = condition(time="토 18:00-20:00")
        result = choose_balanced_option(
            [option("other time", time="일 14:00-16:00"),
             option("same time", time=" 토 18:00-20:00 ")], [a, b])
        self.assertEqual(result.title, "same time")

    def test_stable_tie_break_not_request_order(self):
        a = condition()
        b = condition()
        options = [option("Z", 10000), option("A", 10000)]
        self.assertEqual(choose_balanced_option(options, [a, b]).title, "A")
        self.assertEqual(choose_balanced_option(options[::-1], [b, a]).title, "A")

    def test_casefold_and_semicolon_separated_tags(self):
        a = condition(pref="Board Games; Quiet")
        b = condition(pref="quiet")
        chosen = choose_balanced_option(
            [option("both", tags=[" QUIET "]), option("other", tags=[])], [a, b])
        self.assertEqual(chosen.title, "both")

    def test_requires_exactly_two_conditions(self):
        with self.assertRaises(ValueError):
            choose_balanced_option([option("x")], [condition()])


if __name__ == "__main__":
    unittest.main()
