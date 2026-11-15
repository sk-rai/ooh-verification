"""
Shared authorization predicate for campaign-free (Quick Capture) evidence.

Option A interim rule — a campaign-free Evidence row (``campaign_id IS NULL``) is
visible to an authenticated client iff:

  * an **ACTIVE** VendorClientAssociation links ``Evidence.vendor_id`` to the
    client, AND
  * the vendor, association, client and evidence tenants all agree.

No ``created_by_client_id`` union; no implicit ownership inference. Campaign-bound
evidence is keyed on the client's own campaigns AND requires the evidence tenant to
equal the client's tenant. "The client's own campaigns" uses the same rule as the
Hotfix 3 legacy-photo predicate (``app.core.photo_visibility.owned_campaigns_subquery``):
``Campaign.client_id == client.client_id`` AND ``Campaign.tenant_id == client.tenant_id``.

A missing scope (no client, or a client without client_id / tenant_id) FAILS CLOSED:
every clause is FALSE, rather than relying on ``== None`` rendering as ``IS NULL``.

This module centralizes the predicate so Gallery, Map, Statistics and report
detail apply IDENTICAL authorization logic (cross-surface parity).
"""
from __future__ import annotations

from sqlalchemy import select, and_, or_, false

from app.core.photo_visibility import owned_campaigns_subquery

from app.models.evidence import Evidence
from app.models.campaign import Campaign
from app.models.client import Client
from app.models.vendor import Vendor
from app.models.vendor_client_association import (
    VendorClientAssociation,
    AssociationStatus,
)


def _has_scope(client) -> bool:
    return (
        client is not None
        and getattr(client, "client_id", None) is not None
        and getattr(client, "tenant_id", None) is not None
    )


def client_campaign_ids_subquery(client: Client):
    """Campaign ids owned by this client within its own tenant (empty without scope).

    Delegates to the Hotfix 3 rule so legacy photos and Evidence share one definition.
    """
    return owned_campaigns_subquery(client)


def quick_capture_visibility_clause(client: Client):
    """
    SQLAlchemy boolean clause for campaign-free evidence visibility.

    Correlated EXISTS over an ACTIVE association joined to the client and vendor,
    enforcing four-way tenant agreement against the authenticated principal's
    tenant (``client.tenant_id``) and the evidence row's tenant.
    """
    if not _has_scope(client):
        return false()
    client_tenant = client.tenant_id
    assoc_exists = (
        select(VendorClientAssociation.association_id)
        .select_from(VendorClientAssociation)
        .join(Vendor, Vendor.vendor_id == VendorClientAssociation.vendor_id)
        .where(
            VendorClientAssociation.vendor_id == Evidence.vendor_id,
            VendorClientAssociation.client_id == client.client_id,
            VendorClientAssociation.status == AssociationStatus.ACTIVE,
            # four-way tenant agreement
            VendorClientAssociation.tenant_id == client_tenant,
            Vendor.tenant_id == client_tenant,
            Evidence.tenant_id == client_tenant,
        )
        .correlate(Evidence)
        .exists()
    )
    return and_(Evidence.campaign_id.is_(None), assoc_exists)


def campaign_bound_visibility_clause(client: Client):
    """
    Campaign-bound evidence visibility: the campaign belongs to the client AND the
    evidence row is stamped with the client's own tenant. The tenant equality is a
    guard against evidence that references this client's campaign but was written
    under a different tenant (e.g. via an unvalidated upload campaign reference).
    """
    if not _has_scope(client):
        return false()
    return and_(
        Evidence.campaign_id.in_(client_campaign_ids_subquery(client)),
        Evidence.tenant_id == client.tenant_id,
    )


def evidence_visibility_clause(client: Client):
    """
    Full visibility clause for an Evidence row for this client:
      * campaign-bound rows: campaign belongs to the client AND evidence tenant
        equals the client's tenant; OR
      * campaign-free rows: the Quick Capture ACTIVE-association + tenant rule.
    """
    if not _has_scope(client):
        return false()
    return or_(
        campaign_bound_visibility_clause(client),
        quick_capture_visibility_clause(client),
    )
