"""
Shared authorization predicate for legacy ``photos`` rows read by an authenticated CLIENT.

A Photo is visible to a client only if ALL of these hold:

  * the Photo's campaign is owned by the client   (Campaign.client_id == client.client_id)
  * that campaign is stamped with the client's tenant (Campaign.tenant_id == client.tenant_id)
  * the Photo row itself carries the client's tenant  (Photo.tenant_id    == client.tenant_id)

A missing scope (no client, or a client without client_id / tenant_id) FAILS CLOSED: the
predicate is FALSE and the owned-campaign subquery is empty. This matters because SQLAlchemy
renders ``column == None`` as ``IS NULL``, which would otherwise match NULL-tenant rows.

Only CLIENT-facing read paths use this. Vendor-authenticated endpoints are not affected.
Evidence-table (Quick Capture) visibility is intentionally NOT handled here.
"""
from __future__ import annotations

from sqlalchemy import and_, false, select

from app.models.campaign import Campaign
from app.models.photo import Photo


def _has_scope(client) -> bool:
    return (
        client is not None
        and getattr(client, "client_id", None) is not None
        and getattr(client, "tenant_id", None) is not None
    )


def owned_campaigns_subquery(client):
    """Campaign ids owned by this client AND stamped with this client's tenant (empty if no scope)."""
    if not _has_scope(client):
        return select(Campaign.campaign_id).where(false())
    return select(Campaign.campaign_id).where(
        Campaign.client_id == client.client_id,
        Campaign.tenant_id == client.tenant_id,
    )


def photo_visibility_clause(client):
    """SQL predicate selecting the Photo rows this client may see (FALSE if no scope)."""
    if not _has_scope(client):
        return false()
    return and_(
        Photo.campaign_id.in_(owned_campaigns_subquery(client)),
        Photo.tenant_id == client.tenant_id,
    )
