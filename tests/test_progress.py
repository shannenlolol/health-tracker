"""Progress chart layout: readable date labels and an unobstructed goal line."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from app.services.progress import build_chart

END = datetime(2026, 10, 13, 4, tzinfo=timezone.utc)  # Ranges below cross the 1 October boundary.


def entries(days, kcal=1500):
    meals = [SimpleNamespace(recorded_at=END - timedelta(days=d), estimated_calories=kcal) for d in range(days)]
    weights = [SimpleNamespace(recorded_at=END - timedelta(days=d), weight_kg=70 + d * 0.05) for d in range(0, days, 2)]
    return meals, weights


def drawn(days, kcal=1500, target=2000):
    fig = build_chart(*entries(days, kcal), 'Asia/Singapore', target)
    FigureCanvasAgg(fig).draw()
    return fig.axes


@pytest.mark.parametrize('days', [1, 3, 10, 30])
def test_date_labels_are_unique_and_evenly_spaced(days):
    for axis in drawn(days):
        labels = [label.get_text() for label in axis.get_xticklabels() if label.get_text()]
        assert len(labels) == len(set(labels)), labels  # No repeated dates (hourly ticks).
        assert 1 <= len(labels) <= 7, labels
        ticks = axis.get_xticks()
        gaps = {round(b - a, 6) for a, b in zip(ticks, ticks[1:], strict=False)}
        assert len(gaps) <= 1, labels  # Even spacing: no "29 Sep" right before "01 Oct".


@pytest.mark.parametrize('kcal', [1500, 2400])
def test_goal_is_named_in_title_without_a_legend(kcal):
    _, calorie_axis = drawn(30, kcal, target=1800)
    assert '1,800 kcal goal' in calorie_axis.get_title(loc='left')
    assert calorie_axis.get_legend() is None


def test_empty_chart_still_renders():
    _, calorie_axis = drawn(0)
    assert '2,000 kcal goal' in calorie_axis.get_title(loc='left')
