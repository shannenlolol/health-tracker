"""Persist only pending requests and current grants, never rejected-user history."""
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db.database import SessionLocal
from app.models.entities import AccessMigration, AccessRequest, AllowedUser, User


def is_admin(telegram_user_id: int) -> bool:
    return telegram_user_id in settings.admin_telegram_user_ids


def has_access(telegram_user_id: int) -> bool:
    # Admin authority comes from trusted configuration, never a signup request.
    if is_admin(telegram_user_id):
        return True
    with SessionLocal() as db:
        return db.get(AllowedUser, telegram_user_id) is not None


def initialize_access() -> None:
    """Import explicit legacy IDs once; later restarts must not undo revocations."""
    with SessionLocal.begin() as db:
        if db.get(AccessMigration, "legacy_allowlist_v1"):
            return
        # Allow /myid bootstrap without consuming the one-time import.
        if not settings.allowed_telegram_user_ids and not settings.admin_telegram_user_ids:
            return
        # Health records may include users from an earlier public installation.
        # Import only explicitly allowed IDs, not everyone in the users table.
        for uid in settings.allowed_telegram_user_ids:
            user = db.scalar(select(User).where(User.telegram_user_id == uid))
            if not db.get(AllowedUser, uid):
                db.add(AllowedUser(telegram_user_id=uid, name=user.name if user else "User", token=uuid4().hex))
        # Commit the marker with the grants so a partial import cannot be recorded.
        db.add(AccessMigration(name="legacy_allowlist_v1"))


def refresh_identity(uid: int, name: str, username: str | None) -> None:
    with SessionLocal.begin() as db:
        grant = db.get(AllowedUser, uid)
        if grant:
            grant.name = name[:120]
            grant.username = username


def request_access(uid: int, name: str, username: str | None) -> AccessRequest | None:
    if has_access(uid) or not settings.admin_telegram_user_ids:
        return None
    try:
        with SessionLocal.begin() as db:
            request = AccessRequest(token=uuid4().hex, telegram_user_id=uid, name=name[:120], username=username)
            db.add(request)
        return request
    except IntegrityError:
        # The unique user ID also protects against duplicate requests.
        return None


def pending_request(uid: int) -> AccessRequest | None:
    with SessionLocal() as db:
        return db.scalar(select(AccessRequest).where(AccessRequest.telegram_user_id == uid))


def pending_requests(offset: int = 0, limit: int = 8) -> list[AccessRequest]:
    with SessionLocal() as db:
        return list(db.scalars(select(AccessRequest).order_by(AccessRequest.telegram_user_id).offset(offset).limit(limit)))


def allowed_users(offset: int = 0, limit: int = 8) -> list[AllowedUser]:
    with SessionLocal() as db:
        return list(db.scalars(select(AllowedUser).order_by(AllowedUser.telegram_user_id).offset(offset).limit(limit)))


def decide_request(token: str, approve: bool) -> AccessRequest | None:
    """Consume a specific request and optionally grant access in one transaction.

    The token identifies this request, not just its user. An old Telegram button
    must not approve or reject a later request from the same account.
    """
    with SessionLocal.begin() as db:
        # Atomic consumption makes stale/double decisions harmless on both databases.
        request = db.scalar(delete(AccessRequest).where(AccessRequest.token == token).returning(AccessRequest))
        if request is None:
            return None
        if approve and not db.get(AllowedUser, request.telegram_user_id):
            db.add(AllowedUser(telegram_user_id=request.telegram_user_id, name=request.name,
                               username=request.username, token=uuid4().hex))
        return request


def add_user(uid: int) -> bool:
    if not 0 < uid < 2**63:
        raise ValueError("Enter a positive numeric Telegram user ID.")
    with SessionLocal.begin() as db:
        if is_admin(uid) or db.get(AllowedUser, uid):
            return False
        # Preapproval resolves any pending request too, invalidating its buttons.
        request = db.scalar(delete(AccessRequest).where(AccessRequest.telegram_user_id == uid).returning(AccessRequest))
        user = db.scalar(select(User).where(User.telegram_user_id == uid))
        db.add(AllowedUser(telegram_user_id=uid, name=request.name if request else user.name if user else "User",
                           username=request.username if request else None, token=uuid4().hex))
        return True


def find_grant(token: str) -> AllowedUser | None:
    with SessionLocal() as db:
        return db.scalar(select(AllowedUser).where(AllowedUser.token == token))


def remove_user(token: str) -> int | None:
    """Revoke only this grant; a later reapproval gets a different token.

    Access grants have no cascading relationship to health records. Deleting
    one deliberately preserves the user's meals, weights, and preferences.
    """
    with SessionLocal.begin() as db:
        grant = db.scalar(select(AllowedUser).where(AllowedUser.token == token))
        if grant is None or is_admin(grant.telegram_user_id):
            return None
        return db.scalar(delete(AllowedUser).where(AllowedUser.token == token).returning(AllowedUser.telegram_user_id))
