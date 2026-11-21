"""Regression coverage for retirement of the customer quota-reset endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.client import SubscriptionStatus

from app.models.subscription import Subscription
from app.models.task_queue import TaskQueue
from tests.hotfix_support import hotfix_runtime_env  # noqa: F401
from tests.test_quick_capture_visibility import (  # noqa: F401
    OTHER_TENANT_ID, _Sessions, _ensure_other_tenant, _headers, seed,
)


RESET = "/api/subscriptions/cron/auto-reset-quotas"
SECRET = "test-cron-secret-value"


@pytest.fixture
async def cron_client():
    # Use the production get_db dependency, including its commit after the route.
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client


async def add_subscription(session, owner, period_end, *, status=SubscriptionStatus.ACTIVE):
    period_start = period_end - timedelta(days=30)
    subscription = Subscription(
        client_id=owner.client_id, tenant_id=owner.tenant_id, status=status,
        current_period_start=period_start, current_period_end=period_end,
        photos_quota=50, photos_used=13, vendors_quota=5,
        campaigns_quota=3, storage_quota_mb=100, auto_renew=0,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def billing_state():
    async with _Sessions() as session:
        subscriptions = (await session.execute(select(
            Subscription.subscription_id, Subscription.photos_used,
            Subscription.current_period_start, Subscription.current_period_end,
            Subscription.updated_at,
        ).order_by(Subscription.subscription_id))).all()
        tasks = (await session.execute(select(
            TaskQueue.id, TaskQueue.task_type, TaskQueue.tenant_id, TaskQueue.payload,
        ).order_by(TaskQueue.id))).all()
    return subscriptions, tasks


@pytest.mark.parametrize("authenticated", [True, False])
async def test_customer_reset_cannot_modify_quota(cron_client, seed, authenticated):
    async with _Sessions() as session:
        owner = await seed.client(session)
        other = await seed.client(session, tenant=OTHER_TENANT_ID)
        await session.flush()
        for client in (owner, other):
            await add_subscription(session, client, datetime.now(timezone.utc) + timedelta(days=7))
        await session.commit()
    before = await billing_state()
    response = await cron_client.post(
        "/api/subscriptions/reset-monthly-quotas",
        headers=_headers(owner) if authenticated else {},
    )
    assert response.status_code == 404, response.text
    assert await billing_state() == before


async def test_scheduler_resets_only_eligible_rows_across_tenants(cron_client, seed, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", SECRET)
    now = datetime.now(timezone.utc)
    async with _Sessions() as session:
        owner = await seed.client(session)
        eligible_other = await seed.client(session, tenant=OTHER_TENANT_ID)
        ineligible_other = await seed.client(session, tenant=OTHER_TENANT_ID)
        await session.flush()
        due = await add_subscription(session, owner, now - timedelta(days=1))
        other_due = await add_subscription(session, eligible_other, now - timedelta(days=1))
        other_current = await add_subscription(session, ineligible_other, now + timedelta(days=7))
        await session.commit()

    before = await billing_state()
    headers = _headers(owner)
    rejected = await cron_client.post(RESET, headers=headers)
    assert rejected.status_code == 401, rejected.text
    assert await billing_state() == before

    response = await cron_client.post(RESET, headers={"X-Cron-Secret": SECRET})
    assert response.status_code == 200, response.text
    assert response.json() == {"checked": 2, "reset": 2}
    async with _Sessions() as session:
        for subscription in (due, other_due):
            row = await session.get(Subscription, subscription.subscription_id)
            assert row.photos_used == 0
            assert row.tenant_id == subscription.tenant_id
            assert row.current_period_start == subscription.current_period_end
            assert row.current_period_end == subscription.current_period_end + timedelta(days=30)
        current = await session.get(Subscription, other_current.subscription_id)
        assert current.photos_used == other_current.photos_used
        assert current.current_period_end == other_current.current_period_end
