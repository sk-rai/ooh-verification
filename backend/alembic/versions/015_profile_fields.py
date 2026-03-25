"""Add profile fields to clients and vendors.

Revision ID: 015_profile_fields
Revises: 014_fix_tenant_name
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = '015_profile_fields'
down_revision = '014_fix_tenant_name'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Client profile fields
    op.add_column('clients', sa.Column('contact_person', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('contact_phone', sa.String(20), nullable=True))
    op.add_column('clients', sa.Column('designation', sa.String(100), nullable=True))
    op.add_column('clients', sa.Column('title', sa.String(10), nullable=True))
    op.add_column('clients', sa.Column('address', sa.String(500), nullable=True))
    op.add_column('clients', sa.Column('city', sa.String(100), nullable=True))
    op.add_column('clients', sa.Column('state', sa.String(100), nullable=True))
    op.add_column('clients', sa.Column('country', sa.String(100), nullable=True))
    op.add_column('clients', sa.Column('website', sa.String(500), nullable=True))
    op.add_column('clients', sa.Column('industry', sa.String(100), nullable=True))

    # Vendor location fields
    op.add_column('vendors', sa.Column('city', sa.String(100), nullable=True))
    op.add_column('vendors', sa.Column('state', sa.String(100), nullable=True))
    op.add_column('vendors', sa.Column('country', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('clients', 'contact_person')
    op.drop_column('clients', 'contact_phone')
    op.drop_column('clients', 'designation')
    op.drop_column('clients', 'title')
    op.drop_column('clients', 'address')
    op.drop_column('clients', 'city')
    op.drop_column('clients', 'state')
    op.drop_column('clients', 'country')
    op.drop_column('clients', 'website')
    op.drop_column('clients', 'industry')
    op.drop_column('vendors', 'city')
    op.drop_column('vendors', 'state')
    op.drop_column('vendors', 'country')
