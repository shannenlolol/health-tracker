from collections import defaultdict
from math import ceil
from io import BytesIO
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
from matplotlib.figure import Figure

from app.models import Meal, Weight


def local_time(value, tz):
    # SQLite returns timezone-aware columns without tzinfo; values are stored as UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(tz)


def date_axis(days: list, tz) -> tuple[mdates.DateLocator, mdates.DateFormatter]:
    """Tick at most seven whole days, evenly spaced from the first day, or whole months for long ranges.

    Matplotlib's automatic choice restarts at each month's 1st (so "29 Sep" and
    "01 Oct" can collide) and uses hourly ticks for short ranges, which repeats
    the same date label.
    """
    span = (max(days) - min(days)).days + 1 if days else 1
    interval = next((step for step in (1, 2, 7, 14) if span / step <= 7), None)
    if interval:
        return mdates.DayLocator(interval=interval, tz=tz), mdates.DateFormatter("%d %b", tz=tz)
    # Past 14 weeks (e.g. "All time"), label month starts with the year instead.
    return mdates.MonthLocator(interval=ceil(span / 30.4 / 6), tz=tz), mdates.DateFormatter("%b %Y", tz=tz)


def build_chart(meals: list[Meal], weights: list[Weight], timezone_name: str, calorie_target: int,
                period: str = "last 30 days") -> Figure:
    tz = ZoneInfo(timezone_name)
    # A standalone Figure avoids pyplot's global state, which is not thread-safe
    # when two users' charts render at once.
    fig = Figure(figsize=(8, 8), layout="constrained")
    weight_ax, calorie_ax = fig.subplots(2, 1)
    fig.patch.set_facecolor("#f7f5ef")

    dates: list = []
    if weights:
        dates = [local_time(w.recorded_at, tz) for w in weights]
        values = [w.weight_kg for w in weights]
        weight_ax.plot(dates, values, marker="o", linewidth=3, color="#287271")
        weight_ax.set_ylabel("kg")
    else:
        weight_ax.text(.5, .5, "No weight entries yet", ha="center", va="center", transform=weight_ax.transAxes)
    weight_ax.set_title(f"Weight — {period}", loc="left", fontweight="bold")

    calories: dict[object, int] = defaultdict(int)
    for meal in meals:
        calories[local_time(meal.recorded_at, tz).date()] += meal.estimated_calories
    days: list = []
    if calories:
        days = sorted(calories)
        calorie_ax.bar(days, [calories[d] for d in days], color="#e07a5f")
        calorie_ax.axhline(calorie_target, color="#555", linestyle="--")
    else:
        calorie_ax.text(.5, .5, "No meal entries yet", ha="center", va="center", transform=calorie_ax.transAxes)
    # The goal is named in the title rather than a legend, which could cover the
    # line or the bars whichever corner it was placed in.
    calorie_ax.set_title(f"Daily calories — {period} · dashed line = {calorie_target:,} kcal goal",
                         loc="left", fontweight="bold")
    calorie_ax.set_ylabel("kcal")

    for axis, axis_days in ((weight_ax, [d.date() for d in dates]), (calorie_ax, days)):
        axis.set_facecolor("#f7f5ef")
        axis.grid(axis="y", alpha=.2)
        axis.spines[["top", "right"]].set_visible(False)
        locator, formatter = date_axis(axis_days, tz)
        axis.xaxis.set_major_locator(locator)
        axis.xaxis.set_major_formatter(formatter)
    return fig


def make_chart(meals: list[Meal], weights: list[Weight], timezone_name: str, calorie_target: int,
               period: str = "last 30 days") -> BytesIO:
    output = BytesIO()
    build_chart(meals, weights, timezone_name, calorie_target, period).savefig(output, format="png", dpi=150)
    output.seek(0)
    output.name = "progress.png"
    return output
