"""Plain-text layouts for the Today summary and the saved-meal message."""
from collections.abc import Sequence
from datetime import date

from app.models.entities import Meal

BAR_BLOCKS = 10
MEAL_ICONS = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙", "snack": "🍪"}


def short_date(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b}"


def macro_line(protein_g: float, carbs_g: float, fat_g: float) -> str:
    return f"Protein {protein_g:g} g · Carbs {carbs_g:g} g · Fat {fat_g:g} g"


def calorie_progress(calories: int, target: int) -> str:
    """A 10-block bar plus the percentage and what is left or over, e.g. "▓▓▓▓░░░░░░ 45% · 660 kcal left"."""
    # Round the blocks down so the bar only fills once the target is reached;
    # anything past the target stays a full bar and the text says how far over.
    filled = min(calories * BAR_BLOCKS // target, BAR_BLOCKS)
    bar = "▓" * filled + "░" * (BAR_BLOCKS - filled)
    if calories < target:
        status = f"{target - calories:,} kcal left"
    elif calories > target:
        status = f"{calories - target:,} kcal over"
    else:
        status = "on target"
    return f"{bar} {round(calories * 100 / target)}% · {status}"


def today_text(meals: Sequence[Meal], target: int, day: date) -> str:
    lines = [f"📋 Today · {short_date(day)}"]
    for meal in meals:
        lines += [
            "",
            f"{MEAL_ICONS.get(meal.meal_type, '🍽️')} {meal.meal_type.title()} · {meal.estimated_calories:,} kcal",
            meal.description,
            macro_line(meal.protein_g, meal.carbs_g, meal.fat_g),
        ]
    calories = sum(m.estimated_calories for m in meals)
    lines += [
        "",
        "━━━━━━━━━━",
        f"🔥 {calories:,} / {target:,} kcal",
        calorie_progress(calories, target),
        macro_line(sum(m.protein_g for m in meals), sum(m.carbs_g for m in meals), sum(m.fat_g for m in meals)),
    ]
    return "\n".join(lines)


def saved_text(meal: Meal, updated: bool, day_calories: int, target: int, day_label: str = "Today") -> str:
    """Confirm a saved meal; `day_label` names the meal's own day, since an edited meal may be from an earlier one."""
    return "\n".join([
        f"✅ {meal.meal_type.title()} {'updated' if updated else 'saved'}",
        "",
        meal.description,
        f"🔥 {meal.estimated_calories:,} kcal",
        macro_line(meal.protein_g, meal.carbs_g, meal.fat_g),
        "",
        f"📋 {day_label}: {day_calories:,} / {target:,} kcal",
        calorie_progress(day_calories, target),
    ])
