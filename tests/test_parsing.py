import pytest

from app.bot.bot import parse_calorie_target, parse_reminder_time, parse_weight


@pytest.mark.parametrize('raw, expected', [('82.4', 82.4), ('82.4kg', 82.4), (' 60 KG ', 60), ('30', 30), ('300', 300)])
def test_weight_accepted(raw, expected):
    assert parse_weight(raw) == expected


@pytest.mark.parametrize('raw', ['29.9', '300.1', 'abc', '', 'nan', 'inf'])
def test_weight_rejected(raw):
    with pytest.raises(ValueError):
        parse_weight(raw)


@pytest.mark.parametrize('raw, expected', [('1800', 1800), ('1,800', 1800), ('1800 kcal', 1800), ('500', 500), ('10000', 10_000)])
def test_calorie_target_accepted(raw, expected):
    assert parse_calorie_target(raw) == expected


@pytest.mark.parametrize('raw', ['499', '10001', '1800.5', 'lots', ''])
def test_calorie_target_rejected(raw):
    with pytest.raises(ValueError):
        parse_calorie_target(raw)


@pytest.mark.parametrize('raw, expected', [
    ('8am', '08:00'), ('8 AM', '08:00'), ('08:00', '08:00'), ('13:30', '13:30'),
    ('1:30pm', '13:30'), ('12am', '00:00'), ('12pm', '12:00'),
    ('none', None), (' Off ', None), ('disable', None),
])
def test_reminder_time_accepted(raw, expected):
    assert parse_reminder_time(raw) == expected


@pytest.mark.parametrize('raw', ['25:00', '8', '13pm', 'noon', ''])
def test_reminder_time_rejected(raw):
    with pytest.raises(ValueError):
        parse_reminder_time(raw)
