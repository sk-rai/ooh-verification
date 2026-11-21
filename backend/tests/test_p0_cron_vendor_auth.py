"""Cron authorization and upload-only vendor status enforcement."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api import photos
from app.main import app
from app.models.client import SubscriptionStatus
from app.models.evidence import Evidence
from app.models.page_view import DailyAnalyticsSummary, PageView
from app.models.photo import Photo
from app.models.subscription import Subscription
from app.models.task_queue import TaskQueue
from app.models.vendor import Vendor, VendorStatus
from tests.hotfix_support import hotfix_runtime_env  # noqa: F401
from tests.test_quick_capture_visibility import (  # noqa: F401
    _Sessions, _ensure_other_tenant, seed,
)
from tests.test_upload_campaign_authz import (  # noqa: F401
    _Recorder, _assert_no_side_effects, _count, _vhdr, api, post_legacy, world,
)

EXPIRY = "/api/subscriptions/cron/check-expiring"
RESET = "/api/subscriptions/cron/auto-reset-quotas"
ANALYTICS = "/api/analytics/cron/summarize"
SECRET = "test-cron-secret-value"
DISABLED = (
    "Analytics summarization endpoint is not configured. "
    "Contact the platform administrator."
)


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


@pytest.fixture
async def billing(seed):
    now = datetime.now(timezone.utc)
    async with _Sessions() as session:
        reminder_owner = await seed.client(session)
        reset_owner = await seed.client(session)
        await session.flush()
        reminder = await add_subscription(session, reminder_owner, now + timedelta(days=7))
        expired = await add_subscription(session, reset_owner, now - timedelta(days=1))
        await session.commit()
    yield SimpleNamespace(owner=reminder_owner, reminder=reminder, expired=expired)
    async with _Sessions() as session:
        await session.execute(delete(TaskQueue).where(
            TaskQueue.payload["to_email"].astext == reminder_owner.email,
        ))
        await session.commit()


@pytest.fixture
async def analytics_view():
    async with _Sessions() as session:
        view = PageView(
            visitor_hash="p0-test-visitor",
            page="/p0-test",
            created_at=datetime.now(timezone.utc) - timedelta(days=45),
        )
        session.add(view)
        await session.commit()
    yield
    async with _Sessions() as session:
        await session.execute(delete(PageView).where(PageView.id == view.id))
        await session.commit()


async def analytics_state():
    async with _Sessions() as session:
        views = (await session.execute(select(PageView.__table__).order_by(PageView.id))).all()
        summaries = (await session.execute(select(
            DailyAnalyticsSummary.__table__,
        ).order_by(DailyAnalyticsSummary.id))).all()
    return views, summaries


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


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("path", [EXPIRY, RESET, ANALYTICS])
@pytest.mark.parametrize(("configured", "header", "code", "detail"), [
    (False, SECRET, 503, "Cron endpoint unavailable: CRON_SECRET is not configured on this server."),
    (True, None, 401, "X-Cron-Secret header is required."),
    (True, "wrong-secret", 401, "Invalid cron secret."),
])
async def test_cron_rejected_without_database_changes(
    cron_client, billing, analytics_view, monkeypatch, method, path, configured, header, code, detail,
):
    if configured:
        monkeypatch.setenv("CRON_SECRET", SECRET)
    else:
        monkeypatch.delenv("CRON_SECRET", raising=False)
    before = await billing_state(), await analytics_state()
    headers = {"X-Cron-Secret": header} if header is not None else {}
    response = await cron_client.request(method, path, headers=headers)
    assert response.status_code == code, response.text
    assert response.json() == {"detail": detail}
    assert (await billing_state(), await analytics_state()) == before


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_authorized_expiry_job_persists_reminder(cron_client, billing, monkeypatch, method):
    monkeypatch.setenv("CRON_SECRET", SECRET)
    subscriptions, tasks = await billing_state()
    response = await cron_client.request(method, EXPIRY, headers={"X-Cron-Secret": SECRET})
    assert response.status_code == 200, response.text
    assert response.json() == {"checked": 1, "emails_sent": 1}
    after_subscriptions, after_tasks = await billing_state()
    assert after_subscriptions == subscriptions
    old_ids = {task.id for task in tasks}
    task, = [task for task in after_tasks if task.id not in old_ids]
    assert task.task_type == "send_email"
    assert task.tenant_id == billing.owner.tenant_id
    assert task.payload["template_name"] == "subscription_expiring"
    assert task.payload["to_email"] == billing.owner.email


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_authorized_quota_job_persists_reset(cron_client, billing, monkeypatch, method):
    monkeypatch.setenv("CRON_SECRET", SECRET)
    response = await cron_client.request(method, RESET, headers={"X-Cron-Secret": SECRET})
    assert response.status_code == 200, response.text
    assert response.json() == {"checked": 1, "reset": 1}
    async with _Sessions() as session:
        expired = await session.get(Subscription, billing.expired.subscription_id)
        reminder = await session.get(Subscription, billing.reminder.subscription_id)
    assert expired.photos_used == 0
    assert expired.current_period_start == billing.expired.current_period_end
    assert expired.current_period_end == billing.expired.current_period_end + timedelta(days=30)
    assert reminder.photos_used == billing.reminder.photos_used
    assert reminder.current_period_end == billing.reminder.current_period_end


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_authorized_analytics_stays_disabled(
    cron_client, billing, analytics_view, monkeypatch, method,
):
    monkeypatch.setenv("CRON_SECRET", SECRET)
    before = await billing_state(), await analytics_state()
    response = await cron_client.request(method, ANALYTICS, headers={"X-Cron-Secret": SECRET})
    assert response.status_code == 503, response.text
    assert response.json() == {"detail": DISABLED}
    assert (await billing_state(), await analytics_state()) == before


@pytest.mark.parametrize("vendor_status", [VendorStatus.ACTIVE, VendorStatus.INACTIVE])
async def test_legacy_upload_requires_active_assigned_vendor(api, world, monkeypatch, vendor_status):
    async with _Sessions() as session:
        vendor = await session.get(Vendor, world.V.vendor_id)
        vendor.status = vendor_status
        vendor.public_key = "test-key"
        await session.commit()
    monkeypatch.setattr(photos.SignatureVerificationService, "verify_signature", lambda **kwargs: True)
    response = await post_legacy(api, world.V, world.active_assigned.code)

    if vendor_status == VendorStatus.INACTIVE:
        assert response.status_code == 403, response.text
        assert response.json() == {"detail": "Vendor status is inactive"}
        await _assert_no_side_effects(world, "inactive assigned vendor")
    else:
        assert response.status_code == 201, response.text
        assert _Recorder.photo_calls == 1
        assert await _count(Photo, vendor_id=world.V.vendor_id) == 1
        assert await _count(Evidence, vendor_id=world.V.vendor_id) == 0
        async with _Sessions() as session:
            vendor = await session.get(Vendor, world.V.vendor_id)
            vendor.status = VendorStatus.INACTIVE
            await session.commit()
        detail = await api.get(f"/api/photos/{response.json()['photo_id']}", headers=_vhdr(world.V))
        assert detail.status_code == 200, detail.text
