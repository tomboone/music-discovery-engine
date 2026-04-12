"""seed development user

Revision ID: fc62dbcac6a8
Revises: 48724afaf4c2
Create Date: 2026-04-12 19:05:40.668869

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fc62dbcac6a8'
down_revision: str | Sequence[str] | None = '48724afaf4c2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Well-known seed user ID for single-user development mode
SEED_USER_ID = "d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8"


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, display_name) "
            "VALUES (CAST(:user_id AS uuid), :email, :name) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            user_id=SEED_USER_ID,
            email="dev@music-discovery.local",
            name="Dev User",
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM users WHERE id = CAST(:user_id AS uuid)"
        ).bindparams(user_id=SEED_USER_ID)
    )
