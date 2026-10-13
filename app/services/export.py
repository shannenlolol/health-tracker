"""Build a user's personal data export as a spreadsheet-friendly CSV file."""
import csv
from io import BytesIO, StringIO
from zoneinfo import ZoneInfo

from app.models import Meal, Weight
from app.services.progress import local_time

HEADER = ["Type", "Date and time", "Meal type", "Description", "Calories (kcal)",
          "Protein (g)", "Carbs (g)", "Fat (g)", "Weight (kg)"]


def safe_cell(value):
    # Spreadsheets run cells starting with these characters as formulas. Meal
    # descriptions come from free text, so prefix a quote to keep them as text.
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def export_csv(meals: list[Meal], weights: list[Weight], timezone_name: str) -> BytesIO:
    tz = ZoneInfo(timezone_name)
    rows = [
        (local_time(meal.recorded_at, tz), ["Meal", meal.meal_type.title(), meal.description, meal.estimated_calories,
                                            meal.protein_g, meal.carbs_g, meal.fat_g, ""])
        for meal in meals
    ] + [
        (local_time(weight.recorded_at, tz), ["Weight", "", "", "", "", "", "", weight.weight_kg])
        for weight in weights
    ]
    rows.sort(key=lambda row: row[0])

    text = StringIO()
    writer = csv.writer(text)
    writer.writerow(HEADER)
    for when, (kind, *values) in rows:
        writer.writerow([kind, when.strftime("%Y-%m-%d %H:%M"), *(safe_cell(value) for value in values)])
    # The byte-order mark makes Excel read the file as UTF-8 instead of guessing.
    output = BytesIO(text.getvalue().encode("utf-8-sig"))
    output.name = "health-tracker-export.csv"
    return output
