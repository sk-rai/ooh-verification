#!/bin/bash
set -e

echo "=== TrustCapture Backend Starting ==="

# Wait for DB to be reachable (retry DNS + connection)
echo "Waiting for database..."
for i in $(seq 1 30); do
    if python -c "
import socket
try:
    addr = socket.getaddrinfo('db', 5432)
    print(f'Resolved db to {addr[0][4]}')
except Exception as e:
    print(f'Attempt $i: {e}')
    exit(1)
" 2>&1; then
        echo "Database DNS resolved!"
        break
    fi
    sleep 2
done

# Wait for actual connection
for i in $(seq 1 30); do
    if python -c "
import asyncio, asyncpg, os
async def check():
    url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(url, timeout=5, ssl='prefer')
    await conn.close()
    print('Database connection OK!')
asyncio.run(check())
" 2>&1; then
        break
    fi
    echo "Waiting for DB connection... attempt $i"
    sleep 2
done

# Run database migrations
echo "Running database migrations..."
python -m alembic upgrade head
echo "Migrations complete."

# Start uvicorn
echo "Starting uvicorn server..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers ${WORKERS:-2} \
    --log-level info
