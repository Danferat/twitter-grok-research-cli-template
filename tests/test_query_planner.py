import unittest

from twitter_research.query_planner import plan_query


class QueryPlannerTests(unittest.TestCase):
    def test_plans_crypto_decline_question_for_month(self):
        plan = plan_query("почему PUMP токен падает последний месяц?")

        self.assertEqual(plan.days, 30)
        self.assertEqual(plan.limit, 100)
        self.assertIn("PUMP token", plan.query)
        self.assertIn("dump OR down OR bearish", plan.query)
        self.assertNotIn("pump OR rally", plan.query)

    def test_plans_recent_question_for_week(self):
        plan = plan_query("что пишут про SOL за неделю?")

        self.assertEqual(plan.days, 7)
        self.assertIn("SOL", plan.query)

    def test_preserves_english_topic_words(self):
        plan = plan_query("why is ETH ETF sentiment bearish today")

        self.assertEqual(plan.days, 1)
        self.assertIn("ETH ETF sentiment bearish today", plan.query)


if __name__ == "__main__":
    unittest.main()
