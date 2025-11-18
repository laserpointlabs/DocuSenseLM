"""
Migration: Update status column size in nda_records table
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    # Update status column to VARCHAR(50) to support longer status values
    op.alter_column('nda_records', 'status',
                    existing_type=sa.String(length=20),
                    type_=sa.String(length=50),
                    existing_nullable=False)


def downgrade():
    # Revert to VARCHAR(20)
    op.alter_column('nda_records', 'status',
                    existing_type=sa.String(length=50),
                    type_=sa.String(length=20),
                    existing_nullable=False)







