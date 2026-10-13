from datetime import date

import pytest

from app.models.entities import Meal
from app.services.summary import calorie_progress, macro_line, saved_text, today_text


def meal(meal_type, description, calories, protein, carbs, fat):
    return Meal(meal_type=meal_type, description=description, estimated_calories=calories,
                protein_g=protein, carbs_g=carbs, fat_g=fat)


@pytest.mark.parametrize(("calories", "expected"), [
    (0, "░░░░░░░░░░ 0% · 1,200 kcal left"),
    (540, "▓▓▓▓░░░░░░ 45% · 660 kcal left"),
    (1_100, "▓▓▓▓▓▓▓▓▓░ 92% · 100 kcal left"),
    # 99.9% must not show a full bar.
    (1_199, "▓▓▓▓▓▓▓▓▓░ 100% · 1 kcal left"),
    (1_200, "▓▓▓▓▓▓▓▓▓▓ 100% · on target"),
    (1_220, "▓▓▓▓▓▓▓▓▓▓ 102% · 20 kcal over"),
    (3_000, "▓▓▓▓▓▓▓▓▓▓ 250% · 1,800 kcal over"),
])
def test_calorie_progress(calories, expected):
    assert calorie_progress(calories, 1_200) == expected


def test_macro_line_drops_needless_decimals():
    assert macro_line(30.0, 50.5, 15) == "Protein 30 g · Carbs 50.5 g · Fat 15 g"


def test_today_lists_each_meal_with_macros_and_totals():
    meals = [
        meal("breakfast", "Ramen with 2 pieces of chashu pork", 650, 30, 80, 22),
        meal("lunch", "Iced houjicha latte, medium", 120, 4, 18, 3),
        meal("dinner", "Rice with minced meat basil and fried egg", 450, 30, 50, 15),
    ]
    assert today_text(meals, 1_200, date(2026, 10, 13)) == "\n".join([
        "📋 Today · Tue 13 Oct",
        "",
        "🌅 Breakfast · 650 kcal",
        "Ramen with 2 pieces of chashu pork",
        "Protein 30 g · Carbs 80 g · Fat 22 g",
        "",
        "☀️ Lunch · 120 kcal",
        "Iced houjicha latte, medium",
        "Protein 4 g · Carbs 18 g · Fat 3 g",
        "",
        "🌙 Dinner · 450 kcal",
        "Rice with minced meat basil and fried egg",
        "Protein 30 g · Carbs 50 g · Fat 15 g",
        "",
        "━━━━━━━━━━",
        "🔥 1,220 / 1,200 kcal",
        "▓▓▓▓▓▓▓▓▓▓ 102% · 20 kcal over",
        "Protein 64 g · Carbs 148 g · Fat 40 g",
    ])


def test_today_handles_unknown_meal_type_and_float_totals():
    meals = [meal("meal", "Toast", 100, 0.1, 10, 1), meal("snack", "Apple", 80, 0.2, 20, 0)]
    text = today_text(meals, 2_000, date(2026, 1, 5))
    assert "🍽️ Meal · 100 kcal" in text
    assert "🍪 Snack · 80 kcal" in text
    assert "Protein 0.3 g · Carbs 30 g · Fat 1 g" in text


@pytest.mark.parametrize(("updated", "heading"), [(False, "✅ Dinner saved"), (True, "✅ Dinner updated")])
def test_saved_text_shows_macros_and_running_total(updated, heading):
    saved = meal("dinner", "Rice with minced meat, fried egg and lettuce", 480, 30, 50, 15)
    assert saved_text(saved, updated, 1_220, 1_200) == "\n".join([
        heading,
        "",
        "Rice with minced meat, fried egg and lettuce",
        "🔥 480 kcal",
        "Protein 30 g · Carbs 50 g · Fat 15 g",
        "",
        "📋 Today: 1,220 / 1,200 kcal",
        "▓▓▓▓▓▓▓▓▓▓ 102% · 20 kcal over",
    ])


def test_saved_text_names_an_earlier_day():
    saved = meal("lunch", "Chicken rice", 450, 30, 40, 18)
    assert "📋 Mon 12 Oct: 1,000 / 1,200 kcal" in saved_text(saved, True, 1_000, 1_200, "Mon 12 Oct")
