"""track motorcycles removed from immobilization

Revision ID: b4d5e6f7a8b9
Revises: 90a6bbff7325
Create Date: 2026-09-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b4d5e6f7a8b9"
down_revision = "90a6bbff7325"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("immobilized_motorcycles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("removed_at", sa.DateTime(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_immobilized_motorcycles_removed_at"),
            ["removed_at"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("immobilized_motorcycles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_immobilized_motorcycles_removed_at"))
        batch_op.drop_column("removed_at")