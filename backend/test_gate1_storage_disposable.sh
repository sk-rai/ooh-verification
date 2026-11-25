#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
: "${PGPORT:?missing disposable cluster}" "${PGUSER:?}" "${PGPASSWORD:?}"
[[ "$PGPORT" != 5432 ]]
export PGHOST=127.0.0.1
createdb trustcapture_gate1_test
test "$(psql -XAt -d trustcapture_gate1_test -c "select current_database() || ':' || host(inet_server_addr()) || ':' || inet_server_port()")" = "trustcapture_gate1_test:127.0.0.1:$PGPORT"
export DATABASE_URL=$(python3 -c 'import os; from urllib.parse import quote; print("postgresql+asyncpg://"+quote(os.environ["PGUSER"],safe="")+":"+quote(os.environ["PGPASSWORD"],safe="")+"@127.0.0.1:"+os.environ["PGPORT"]+"/trustcapture_gate1_test")')
export TEST_DATABASE_URL="$DATABASE_URL" RUN_GATE1_DB_TESTS=1 TESTING=true USE_MOCK_STORAGE=true PYTHONDONTWRITEBYTECODE=1
python3 -m alembic upgrade head
python3 -m alembic downgrade 028_inspection_storage_fence
python3 -m alembic upgrade head
if [[ "${GATE1_CLOUDINARY_ENDPOINT_STDIN:-}" == 1 ]]; then
    python3 -m unittest -v tests.test_gate1_inspection_authz.InspectionAuthorizationTests.test_pinned_package_and_exact_reservation_endpoint
else
    python3 -m unittest -v tests.test_gate1_inspection_authz
fi
