"""Add delivery verification columns to location_profiles

Revision ID: 011_delivery_verification
Revises: 010_add_missing_columns
"""
from alembic import op

revision = '011_delivery_verification'
down_revision = '010_add_missing_columns'
branch_labels = None
depends_on = None


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


def upgrade():
    _add_col('location_profiles', 'delivery_window_start', 'TIMESTAMP WITH TIME ZONE')
    _add_col('location_profiles', 'delivery_window_end', 'TIMESTAMP WITH TIME ZONE')
    _add_col('location_profiles', 'resolved_address', 'VARCHAR(500)')


def downgrade():
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS delivery_window_start")
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS delivery_window_end")
    op.execute("ALTER TABLE location_profiles DROP COLUMN IF EXISTS resolved_address")
