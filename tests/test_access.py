from datetime import datetime, timedelta, timezone

from app.models import Meal
from app.services import access, tracker

ALL_TIME = (datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2100, 1, 1, tzinfo=timezone.utc))


def request(uid=1):
    return access.request_access(uid, 'Ann', 'ann')


def test_approve_grants_access_and_reject_does_not(sessions):
    approved, rejected = request(1), request(2)
    assert not access.has_access(1)
    assert access.decide_request(approved.token, True).telegram_user_id == 1
    assert access.decide_request(rejected.token, False).telegram_user_id == 2
    assert access.has_access(1)
    assert not access.has_access(2)
    assert access.pending_requests() == []


def test_admin_always_has_access_and_needs_no_grant(sessions):
    assert access.has_access(999)
    assert access.request_access(999, 'Admin', None) is None
    assert access.add_user(999) is False


def test_stale_buttons_do_nothing(sessions):
    first = request()
    assert access.decide_request(first.token, False)
    # Double tap or an old message: the token is already consumed.
    assert access.decide_request(first.token, True) is None
    assert not access.has_access(1)


def test_remove_keeps_records_and_user_can_request_again(sessions, monkeypatch):
    access.decide_request(request().token, True)
    user = tracker.get_user(1, 'Ann')
    with sessions() as db:
        db.add(Meal(user_id=user.id, description='Toast', estimated_calories=200, protein_g=5, carbs_g=30, fat_g=5))
        db.commit()
    grant_token = next(grant.token for grant in access.allowed_users() if grant.telegram_user_id == 1)

    assert access.remove_user(grant_token) == 1
    assert access.remove_user(grant_token) is None  # The old "Remove" button is now stale.
    assert not access.has_access(1)
    assert len(tracker.today_entries(user.id, *ALL_TIME)[0]) == 1

    # Move past the five-minute cooldown; the same person can then ask again.
    later = access.limiter.utcnow() + timedelta(minutes=6)
    monkeypatch.setattr(access.limiter, 'utcnow', lambda: later)
    again = request()
    assert again is not None
    assert access.decide_request(again.token, True)
    assert access.has_access(1)


def test_add_user_resolves_pending_request(sessions):
    pending = request(5)
    assert access.add_user(5) is True
    assert access.has_access(5)
    assert access.decide_request(pending.token, True) is None  # Its buttons are stale.
