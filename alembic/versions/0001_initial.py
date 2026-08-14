"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2026-08-14 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # admin table
    op.create_table('admin',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_admin')),
    sa.UniqueConstraint('username', name=op.f('uq_admin_username'))
    )
    
    # etf table
    op.create_table('etf',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('logo_path', sa.String(length=255), nullable=True),
    sa.Column('current_value', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('previous_value', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('last_change_amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('last_change_percentage', sa.Numeric(precision=9, scale=2), nullable=False),
    sa.Column('trend', sa.Enum('UP', 'DOWN', 'FLAT', name='trend'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_etf'))
    )
    
    # etfvaluehistory table
    op.create_table('etfvaluehistory',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('etf_id', sa.Integer(), nullable=False),
    sa.Column('old_value', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('new_value', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('change_amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('change_percentage', sa.Numeric(precision=9, scale=2), nullable=False),
    sa.Column('change_type', sa.Enum('ABSOLUTE', 'PERCENTAGE', name='changetype'), nullable=False),
    sa.Column('input_value', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['etf_id'], ['etf.id'], name=op.f('fk_etfvaluehistory_etf_id_etf'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_etfvaluehistory'))
    )
    op.create_index(op.f('ix_etfvaluehistory_etf_id'), 'etfvaluehistory', ['etf_id'], unique=False)
    op.create_index('ix_etfvaluehistory_etf_id_created_at', 'etfvaluehistory', ['etf_id', 'created_at'], unique=False)
    
    # traderequest table
    op.create_table('traderequest',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('requester_name', sa.String(length=120), nullable=False),
    sa.Column('requester_image_path', sa.String(length=255), nullable=False),
    sa.Column('etf_id', sa.Integer(), nullable=False),
    sa.Column('request_type', sa.Enum('BUY', 'SELL', name='requesttype'), nullable=False),
    sa.Column('units', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('etf_value_snapshot', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('total_value_snapshot', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='requeststatus'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['etf_id'], ['etf.id'], name=op.f('fk_traderequest_etf_id_etf')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_traderequest'))
    )
    op.create_index(op.f('ix_traderequest_created_at'), 'traderequest', ['created_at'], unique=False)
    op.create_index(op.f('ix_traderequest_etf_id'), 'traderequest', ['etf_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_traderequest_etf_id'), table_name='traderequest')
    op.drop_index(op.f('ix_traderequest_created_at'), table_name='traderequest')
    op.drop_table('traderequest')
    op.drop_index('ix_etfvaluehistory_etf_id_created_at', table_name='etfvaluehistory')
    op.drop_index(op.f('ix_etfvaluehistory_etf_id'), table_name='etfvaluehistory')
    op.drop_table('etfvaluehistory')
    op.drop_table('etf')
    op.drop_table('admin')
