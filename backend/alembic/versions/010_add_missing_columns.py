"""Add all missing columns that were applied via manual SQL

Revision ID: 010_add_missing_columns
Revises: 009_create_admin_users
"""
from alembic import op

revision = '010_add_missing_columns'
down_revision = '009_create_admin_users'
branch_labels = None
depends_on = None

DEFAULT_TENANT = 'e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa'


def _add_col(table, col_name, col_type_sql, default=None):
    q = chr(39)
    default_clause = " DEFAULT " + default if default else ""
    sql = (
        "DO $$ BEGIN "
        "IF NOT EXISTS ("
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=" + q + table + q
        + " AND column_name=" + q + col_name + q
        + ") THEN "
        "ALTER TABLE " + table + " ADD COLUMN " + col_name
        + " " + col_type_sql + default_clause + "; "
        "END IF; "
        "END $$;"
    )
    op.execute(sql)


def _create_idx(idx_name, table, column):
    op.execute(
        "CREATE INDEX IF NOT EXISTS " + idx_name
        + " ON " + table + " (" + column + ")"
    )


def upgrade():
    q = chr(39)
    # 1. tenant_id on main tables
    for table in ['clients', 'vendors', 'campaigns', 'photos', 'subscriptions']:
        _add_col(table, 'tenant_id', 'UUID')
        op.execute(
            "UPDATE " + table + " SET tenant_id = "
            + q + DEFAULT_TENANT + q
            + " WHERE tenant_id IS NULL"
        )
        op.execute(
            "DO $$ BEGIN "
            "ALTER TABLE " + table + " ALTER COLUMN tenant_id SET NOT NULL; "
            "EXCEPTION WHEN others THEN NULL; "
            "END $$;"
        )
        _create_idx('idx_' + table + '_tenant', table, 'tenant_id')

    # 2. vendors.updated_at
    _add_col('vendors', 'updated_at', 'TIMESTAMP WITH TIME ZONE', 'now()')

    # 3. photos: enhanced verification
    _add_col('photos', 'verification_confidence', 'FLOAT')
    _add_col('photos', 'verification_flags', 'TEXT[]')

    # 4. location_profiles: magnetic field
    _add_col('location_profiles', 'expected_magnetic_min', 'FLOAT')
    _add_col('location_profiles', 'expected_magnetic_max', 'FLOAT')
    _add_col('location_profiles', 'updated_at', 'TIMESTAMP WITH TIME ZONE', 'now()')


def downgrade():
    for table in ['clients', 'vendors', 'campaigns', 'photos', 'subscriptions']:
        op.execute("DROP INDEX IF EXISTS idx_" + table + "_tenant")
        op.execute(
            "ALTER TABLE " + table + " DROP COLUMN IF EXISTS tenant_id"
        )

    drop_cols = {
        'vendors': ['updated_at'],
        'photos': ['verification_confidence', 'verification_flags'],
        'location_profiles': ['expected_magnetic_min', 'expected_magnetic_max', 'updated_at'],
    }
    for table, cols in drop_cols.items():
        for col in cols:
            op.execute(
                "ALTER TABLE " + table + " DROP COLUMN IF EXISTS " + col
            )
