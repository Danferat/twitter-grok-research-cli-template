import tempfile
import unittest
from pathlib import Path

from twitter_research.content_filter import (
    find_similar_summary,
    load_content_index,
    load_content_index_from_text,
    summary_similarity,
)


INDEX_TEXT = """| Дата добавления | Тема | Категория | Краткое содержание | Ссылка на источник | Файл с заметкой | Статус |
| --------------- | ---- | --------- | ------------------ | ------------------ | --------------- | ------ |
| 30/05/26 | Гигиена криптокошелька | Безопасность | Практические привычки для защиты кошелька: разделение кошельков, осторожность с подписями, offline-хранение seed phrase и проверка approvals. | https://x.com/source/status/1 | content_research/wallet.md | accepted |
| 30/05/26 | L1, L2 и gas | База крипты | Объяснение сетей и комиссий: почему для swap, bridge и dApp нужен нативный токен для gas в правильной сети. | https://x.com/source/status/2 | content_research/gas.md | accepted |
"""


class ContentFilterTests(unittest.TestCase):
    def test_summary_similarity_scores_close_summaries_above_threshold(self):
        existing = (
            "Практические привычки для защиты кошелька: разделение кошельков, "
            "осторожность с подписями, offline-хранение seed phrase и проверка approvals."
        )
        candidate = (
            "Практические привычки для защиты криптокошелька: разделение кошельков, "
            "аккуратность с подписями, offline хранение seed phrase и регулярная проверка approvals."
        )

        self.assertGreaterEqual(summary_similarity(candidate, existing), 0.8)

    def test_find_similar_summary_returns_match_when_index_summary_is_semantically_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "content_research_index.md"
            index_path.write_text(INDEX_TEXT, encoding="utf-8")

            entries = load_content_index(index_path)
            match = find_similar_summary(
                "Практические привычки для защиты криптокошелька: разделение кошельков, "
                "осторожность с подписями, хранение seed phrase офлайн и проверка approvals.",
                entries,
                threshold=0.8,
            )

            self.assertIsNotNone(match)
            self.assertEqual(match.entry.topic, "Гигиена криптокошелька")
            self.assertGreaterEqual(match.score, 0.8)

    def test_find_similar_summary_allows_material_below_threshold(self):
        entries = load_content_index_from_text(INDEX_TEXT)

        match = find_similar_summary(
            "Подборка полезных кошельков и сервисов для учета комиссий в разных сетях.",
            entries,
            threshold=0.8,
        )

        self.assertIsNone(match)

    def test_find_similar_summary_detects_close_summary_with_different_wording(self):
        entries = load_content_index_from_text(
            "| Дата добавления | Тема | Категория | Краткое содержание | Ссылка на источник | Файл с заметкой | Статус |\n"
            "| --------------- | ---- | --------- | ------------------ | ------------------ | --------------- | ------ |\n"
            "| 30/05/26 | Фейковые криптоплатформы | Безопасность | Разбор признаков фейковых платформ: красивый баланс, блокировка вывода, требования новых платежей и давление через поддержку. | https://x.com/source/status/3 | content_research/fake.md | needs_fact_check |\n"
        )

        match = find_similar_summary(
            "Разбор фейковых платформ: красивый баланс, невозможность вывода, "
            "требования оплатить дополнительные комиссии и давление через поддержку.",
            entries,
            threshold=0.8,
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.entry.topic, "Фейковые криптоплатформы")
