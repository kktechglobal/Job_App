"""Queueing and draining notifications.

`queue` only writes a row. Nothing is delivered inside a request -- an HTTP
handler that waits on an email provider is one that times out when the
provider does.

`claim_pending` is what a worker calls. It uses SELECT ... FOR UPDATE SKIP
LOCKED so two workers can drain the same table without handing the same row to
both, and without either waiting on the other. SQLite ignores the locking
clause, which is fine for tests: there is only one worker there.
"""

from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.enums import NotificationStatus
from app.notifications.models import Notification
from app.notifications.schemas import NotificationCreate
from app.users.models import AccountSetting, User

MAX_ATTEMPTS = 5


async def queue(db: AsyncSession, data: NotificationCreate) -> Optional[Notification]:
    """Returns None when the recipient has switched these off.

    Checked at queue time rather than at send time so an opted-out user
    leaves no trail of unsent rows behind them.
    """
    settings = (await db.execute(
        select(AccountSetting).where(AccountSetting.user_id == data.user_id)
    )).scalars().first()

    # No settings row means defaults, and the default is opted in.
    if settings is not None and not settings.email_notifications:
        return None

    row = Notification(**data.model_dump())
    db.add(row)
    await db.flush()
    return row


async def claim_pending(db: AsyncSession, limit: int = 20) -> Sequence[Notification]:
    result = await db.execute(
        select(Notification)
        .where(
            Notification.status == NotificationStatus.PENDING,
            Notification.attempts < MAX_ATTEMPTS,
        )
        .order_by(Notification.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return result.scalars().all()


async def mark_sent(db: AsyncSession, notification: Notification) -> None:
    notification.status = NotificationStatus.SENT
    notification.attempts += 1
    notification.sent_at = datetime.now(timezone.utc)
    await db.commit()


async def mark_failed(db: AsyncSession, notification: Notification, error: str) -> None:
    notification.attempts += 1
    # Stays PENDING until the attempt budget runs out, so a provider
    # blip is retried rather than written off.
    if notification.attempts >= MAX_ATTEMPTS:
        notification.status = NotificationStatus.FAILED
    notification.error = error[:500]
    await db.commit()
