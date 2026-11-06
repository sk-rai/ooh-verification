"""P0 admin-endpoint-auth-hotfix - MANDATORY dependency-graph coverage guard
(reconstructed after worktree loss). RELEASE-BLOCKING.

Inspects the effective FastAPI route registrations and each route's resolved
dependency graph (NOT by sending requests) and asserts:

  * EXACTLY the ten expected admin (method, path) combinations exist under the
    two protected prefixes (5 tenant CRUD + 5 queue) - none missing, none extra.
  * Every one of those ten routes has get_current_admin in its effective
    dependency graph (route-level AND router-level dependencies are flattened).
  * GET /api/branding does NOT have get_current_admin in its dependency graph.

No DB access, no requests. conftest.py not modified.
"""
import os

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("USE_MOCK_STORAGE", "true")
# The guard only imports the app. Provide a dummy URL so engine creation at import
# time succeeds; NO connection is ever opened by this module.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://127.0.0.1:5432/trustcapture_test")

from fastapi.routing import APIRoute

from app.main import app
from app.core.admin_deps import get_current_admin


EXPECTED_ADMIN_ROUTES = {
    ("POST", "/api/admin/tenants"),
    ("GET", "/api/admin/tenants"),
    ("GET", "/api/admin/tenants/{tenant_id}"),
    ("PUT", "/api/admin/tenants/{tenant_id}"),
    ("DELETE", "/api/admin/tenants/{tenant_id}"),
    ("GET", "/api/admin/queue/depth"),
    ("GET", "/api/admin/queue/dead"),
    ("GET", "/api/admin/queue/dead/list"),
    ("POST", "/api/admin/queue/dead/{task_id}/retry"),
    ("DELETE", "/api/admin/queue/dead/{task_id}"),
}

PROTECTED_PREFIXES = ("/api/admin/tenants", "/api/admin/queue")
BRANDING_PATH = "/api/branding"


def _effective_dependency_callables(route: APIRoute):
    """All dependency callables in the route's resolved dependant graph. FastAPI
    flattens router-level and route-level dependencies into route.dependant."""
    found = set()
    stack = [route.dependant]
    while stack:
        dep = stack.pop()
        if getattr(dep, "call", None) is not None:
            found.add(dep.call)
        stack.extend(dep.dependencies)
    return found


def _admin_routes_in_app():
    found = {}
    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue
        if not r.path.startswith(PROTECTED_PREFIXES):
            continue
        for m in (r.methods or set()):
            if m in ("HEAD", "OPTIONS"):
                continue
            found[(m, r.path)] = r
    return found


def _branding_routes():
    return [r for r in app.routes
            if isinstance(r, APIRoute) and r.path == BRANDING_PATH and "GET" in (r.methods or set())]


def test_exactly_the_expected_admin_routes_exist_under_protected_prefixes():
    found = set(_admin_routes_in_app().keys())
    missing = EXPECTED_ADMIN_ROUTES - found
    unexpected = found - EXPECTED_ADMIN_ROUTES
    assert not missing, f"expected admin routes MISSING: {sorted(missing)}"
    assert not unexpected, f"UNEXPECTED admin route(s) under protected prefixes: {sorted(unexpected)}"


def test_all_ten_admin_routes_require_get_current_admin():
    routes = _admin_routes_in_app()
    for key in sorted(EXPECTED_ADMIN_ROUTES):
        assert key in routes, f"route not registered: {key}"
        assert get_current_admin in _effective_dependency_callables(routes[key]), \
            f"{key} is NOT protected by get_current_admin"


def test_public_branding_is_not_admin_protected():
    branding = _branding_routes()
    assert branding, f"{BRANDING_PATH} GET route not found"
    for r in branding:
        assert get_current_admin not in _effective_dependency_callables(r), \
            f"{BRANDING_PATH} must NOT be admin-protected"


def test_release_gate_summary():
    """Single release-blocking check combining all three conditions, printing
    a listing of each protected route."""
    routes = _admin_routes_in_app()
    assert set(routes.keys()) == EXPECTED_ADMIN_ROUTES, (
        f"admin route set mismatch: found={sorted(routes)} expected={sorted(EXPECTED_ADMIN_ROUTES)}")
    print("COVERAGE GUARD - protected admin routes:")
    for key in sorted(EXPECTED_ADMIN_ROUTES):
        protected = get_current_admin in _effective_dependency_callables(routes[key])
        print(f"  {'OK' if protected else 'XX'} {key[0]:6} {key[1]}")
        assert protected, f"{key} not protected"
    branding = _branding_routes()
    assert branding and all(get_current_admin not in _effective_dependency_callables(r) for r in branding)
    print(f"  PUBLIC {BRANDING_PATH} (no admin dep) - OK")
