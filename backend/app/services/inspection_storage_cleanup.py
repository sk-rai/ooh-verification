"""Bounded maintenance pass for Gate 1 originals. Run under a separate identity."""
from uuid import UUID

from app.services.inspection_capture import clean_expired_inspection_original


async def sweep_inspection_originals(sessions, storage, *, after: UUID | None = None, limit: int = 100):
    """Return the next cursor and failures. Start at None again for late writes."""
    if not 1 <= limit <= 1000:
        raise ValueError("Invalid inspection cleanup batch size")
    reservations = await storage.staging.expired_unfinalized(after=after, limit=limit)

    failures = []
    for reservation_id in reservations:
        try:
            async with sessions() as db:
                await clean_expired_inspection_original(db, reservation_id=reservation_id, storage=storage)
        except Exception:
            # Report only synthetic/domain identifiers, never provider request details.
            failures.append(reservation_id)
    return (reservations[-1] if len(reservations) == limit else None), failures
