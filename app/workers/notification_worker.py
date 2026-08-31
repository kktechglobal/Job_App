"""Drains the notification queue.

Run it beside the API, not inside it:

    python -m app.workers.notification_worker

It is deliberately a plain loop rather than Celery or arq. There is one queue,
one job, and the table already carries the state -- adding a broker would be
another service to run for no behaviour this does not have. Swap it out when
there is a second kind of background work, not before.

`send` is a stub. Wire it to a real provider when one is chosen; everything
around it -- claiming, retrying, the attempt budget -- is already here.
"""

import asyncio
import logging

from app.database.db import AsyncSessionLocal
from app.notifications import service as notifications_service
from app.notifications.models import Notification

logger = logging.getLogger(__name__)

POLL_SECONDS = 5


async def send(notification: Notification) -> None:
    """Replace with a real provider call. Raising marks the row failed."""
    logger.info(
        "would send %s to user %s: %s",
        notification.channel.value, notification.user_id, notification.subject,
    )


async def drain_once() -> int:
    """One pass. Returns how many rows were handled, so a caller can decide
    whether to sleep or go straight round again."""
    handled = 0
    async with AsyncSessionLocal() as db:
        for notification in await notifications_service.claim_pending(db):
            try:
                await send(notification)
            except Exception as exc:                      # noqa: BLE001
                # One bad row must not stop the queue.
                logger.warning("notification %s failed: %s", notification.id, exc)
                await notifications_service.mark_failed(db, notification, str(exc))
            else:
                await notifications_service.mark_sent(db, notification)
            handled += 1
    return handled


async def run() -> None:
    logger.info("notification worker started")
    while True:
        try:
            if await drain_once() == 0:
                await asyncio.sleep(POLL_SECONDS)
        except Exception:                                  # noqa: BLE001
            logger.exception("drain failed; retrying")
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
