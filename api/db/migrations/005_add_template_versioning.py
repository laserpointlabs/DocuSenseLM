"""
Migration: Add template versioning support
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    # Add versioning columns to nda_templates
    op.add_column('nda_templates', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('nda_templates', sa.Column('template_key', sa.String(length=255), nullable=False, server_default='default'))
    op.add_column('nda_templates', sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('nda_templates', sa.Column('change_notes', sa.Text(), nullable=True))
    
    # Create template_key from name (for existing templates)
    op.execute("""
        UPDATE nda_templates 
        SET template_key = LOWER(REGEXP_REPLACE(name, '[^a-zA-Z0-9]+', '-', 'g'))
        WHERE template_key = 'default'
    """)
    
    # Create unique constraint on template_key + version
    op.create_unique_constraint('uq_template_key_version', 'nda_templates', ['template_key', 'version'])
    
    # Create indexes
    op.create_index('idx_templates_key', 'nda_templates', ['template_key'])
    op.create_index('idx_templates_current', 'nda_templates', ['is_current'])
    
    # Add template tracking to nda_records
    op.add_column('nda_records', sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('nda_records', sa.Column('template_version', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_nda_records_template', 'nda_records', 'nda_templates', ['template_id'], ['id'])


def downgrade():
    # Remove template tracking from nda_records
    op.drop_constraint('fk_nda_records_template', 'nda_records', type_='foreignkey')
    op.drop_column('nda_records', 'template_version')
    op.drop_column('nda_records', 'template_id')
    
    # Remove versioning from nda_templates
    op.drop_index('idx_templates_current', 'nda_templates')
    op.drop_index('idx_templates_key', 'nda_templates')
    op.drop_constraint('uq_template_key_version', 'nda_templates', type_='unique')
    op.drop_column('nda_templates', 'change_notes')
    op.drop_column('nda_templates', 'is_current')
    op.drop_column('nda_templates', 'template_key')
    op.drop_column('nda_templates', 'version')







