"""Create admin_users table.

Revision ID: 009_create_admin_users
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '009_create_admin_users'
down_revision = '008_add_timezone_to_all_datetimes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'admin_users',
        sa.Column('admin_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )


def downgrade() -> None:
    op.drop_table('admin_users')
