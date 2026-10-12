"""Offline tests for the shared OpenAI client; no request reaches OpenAI."""
import asyncio
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', '123:test')
os.environ.setdefault('OPENAI_API_KEY', 'test-key')

from app.config import non_negative_setting
from app.services import meal_analyzer
from app.services.meal_analyzer import MealAnalyzer, MealEstimate


def fake_response(usage):
    estimate = MealEstimate(description='Chicken rice', estimated_calories=600, protein_g=30, carbs_g=70, fat_g=20)
    return SimpleNamespace(usage=usage, output_parsed=estimate)


class SharedClientTests(unittest.TestCase):
    def setUp(self):
        meal_analyzer.shared_client.cache_clear()
        self.addCleanup(meal_analyzer.shared_client.cache_clear)

    def test_one_client_with_timeout_and_retries(self):
        first, second = MealAnalyzer(), MealAnalyzer()
        self.assertIs(first.client, second.client)
        self.assertEqual(first.client.timeout, meal_analyzer.settings.openai_timeout_seconds)
        self.assertEqual(first.client.max_retries, meal_analyzer.settings.openai_max_retries)

    def test_usage_is_logged_for_text_and_photo(self):
        analyser = MealAnalyzer()
        usage = SimpleNamespace(input_tokens=120, output_tokens=40, total_tokens=160)
        analyser.client = SimpleNamespace(responses=SimpleNamespace(parse=AsyncMock(return_value=fake_response(usage))))
        with self.assertLogs(meal_analyzer.log, 'INFO') as logs:
            text = asyncio.run(analyser.from_text('chicken rice'))
            photo = asyncio.run(analyser.from_image(b'jpeg', 'image/jpeg'))
        self.assertEqual(text.description, 'Chicken rice')
        self.assertEqual(photo.estimated_calories, 600)
        self.assertIn('text estimate used 120 input + 40 output = 160 tokens', logs.output[0])
        self.assertIn('photo estimate', logs.output[1])

    def test_missing_usage_does_not_fail(self):
        analyser = MealAnalyzer()
        analyser.client = SimpleNamespace(responses=SimpleNamespace(parse=AsyncMock(return_value=fake_response(None))))
        with self.assertNoLogs(meal_analyzer.log, 'INFO'):
            estimate = asyncio.run(analyser.from_text('chicken rice'))
        self.assertEqual(estimate.description, 'Chicken rice')


class SettingTests(unittest.TestCase):
    def test_retries_accept_zero_but_not_negative(self):
        with patch.dict(os.environ, {'TEST_RETRIES': '0'}):
            self.assertEqual(non_negative_setting('TEST_RETRIES', 2), 0)
        for value in ['-1', 'invalid']:
            with patch.dict(os.environ, {'TEST_RETRIES': value}), self.assertRaises(ValueError):
                non_negative_setting('TEST_RETRIES', 2)


if __name__ == '__main__':
    unittest.main()
