from collections import defaultdict
from io import BytesIO
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from app.models import Meal, Weight


def local_time(value, tz):
    # SQLite returns timezone-aware columns without tzinfo; values are stored as UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(tz)


def make_chart(meals: list[Meal], weights: list[Weight], timezone_name: str, calorie_target: int) -> BytesIO:
    tz = ZoneInfo(timezone_name)
    fig, (weight_ax, calorie_ax) = plt.subplots(2, 1, figsize=(8, 8), constrained_layout=True)
    fig.patch.set_facecolor("#f7f5ef")

    if weights:
        dates = [local_time(w.recorded_at, tz) for w in weights]
        values = [w.weight_kg for w in weights]
        weight_ax.plot(dates, values, marker="o", linewidth=3, color="#287271")
        weight_ax.set_ylabel("kg")
    else:
        weight_ax.text(.5, .5, "No weight entries yet", ha="center", va="center", transform=weight_ax.transAxes)
    weight_ax.set_title("Weight — last 30 days", loc="left", fontweight="bold")

    calories: dict[object, int] = defaultdict(int)
    for meal in meals:
        calories[local_time(meal.recorded_at, tz).date()] += meal.estimated_calories
    if calories:
        days = sorted(calories)
        calorie_ax.bar(days, [calories[d] for d in days], color="#e07a5f")
        calorie_ax.axhline(calorie_target, color="#555", linestyle="--", label=f"Goal {calorie_target:,}")
        calorie_ax.legend(frameon=False)
    else:
        calorie_ax.text(.5, .5, "No meal entries yet", ha="center", va="center", transform=calorie_ax.transAxes)
    calorie_ax.set_title("Daily calories — last 30 days", loc="left", fontweight="bold")
    calorie_ax.set_ylabel("kcal")

    for axis in (weight_ax, calorie_ax):
        axis.set_facecolor("#f7f5ef")
        axis.grid(axis="y", alpha=.2)
        axis.spines[["top", "right"]].set_visible(False)
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d %b", tz=tz))

    output = BytesIO()
    fig.savefig(output, format="png", dpi=150)
    plt.close(fig)
    output.seek(0)
    output.name = "progress.png"
    return output
