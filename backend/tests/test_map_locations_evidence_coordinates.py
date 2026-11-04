"""Phase B check: invalid evidence coordinates are excluded from the map response.

Spec: .kiro/specs/map-tracking-isolation-fix  (Phase B, Task 4; owner-mandated)

The new evidence map query must safely EXCLUDE rows whose coordinates are NULL,
out of range, or non-finite, and must never crash the endpoint or place a marker
off the globe. Valid rows must still appear. The legacy path is not touched.

Task 7 (Phase C) will extend this with full property-mapping coverage; this module
only pins the coordinate-safety behavior implemented in Phase B.

Reuses the isolated NullPool seeding harness from test_map_locations_isolation.py
(conftest.py is not modified).
"""
import uuid

import pytest

from tests.hotfix_support import hotfix_runtime_env  # noqa: F401  (autouse runtime env)
from tests.test_map_locations_isolation import (  # noqa: F401  (fixtures + helpers)
    api_client, seeder, _headers, TestSessionLocal,
)


@pytest.mark.asyncio
async def test_invalid_evidence_coordinates_are_excluded(api_client, seeder):
    async with TestSessionLocal() as s:
        c = await seeder.client(s, f"co_{uuid.uuid4().hex[:8]}@x.com", "Coord Co")
        cam = await seeder.campaign(s, c)
        v = await seeder.vendor(s, c)

        valid = await seeder.evidence(s, cam, v, 19.07, 72.87, "verified")
        valid_edge = await seeder.evidence(s, cam, v, -90.0, 180.0, "flagged")  # inclusive bounds

        await seeder.evidence(s, cam, v, 95.0, 72.87, "rejected")        # lat > 90
        await seeder.evidence(s, cam, v, -90.5, 72.87, "rejected")       # lat < -90
        await seeder.evidence(s, cam, v, 19.07, 200.0, "rejected")       # lon > 180
        await seeder.evidence(s, cam, v, 19.07, -181.0, "rejected")      # lon < -180
        await seeder.evidence(s, cam, v, float("nan"), 72.87, "rejected")   # non-finite lat
        await seeder.evidence(s, cam, v, 19.07, float("inf"), "rejected")   # non-finite lon
        await seeder.evidence(s, cam, v, float("-inf"), 72.87, "rejected")  # non-finite lat
        await seeder.evidence(s, cam, v, None, 72.87, "rejected")        # NULL lat
        await seeder.evidence(s, cam, v, 19.07, None, "rejected")        # NULL lon
        await s.commit()

    resp = await api_client.get("/api/photos/locations", headers=_headers(c))
    assert resp.status_code == 200, resp.text  # must not crash on bad rows
    feats = resp.json()["features"]

    returned = {f["properties"]["photo_id"] for f in feats}
    assert returned == {str(valid.evidence_id), str(valid_edge.evidence_id)}, (
        f"only valid-coordinate evidence may appear, got {len(returned)} features"
    )
    for f in feats:
        lon, lat = f["geometry"]["coordinates"]
        assert -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
