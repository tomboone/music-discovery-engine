"""add release_type to taste_profile_albums

Revision ID: 905825959a79
Revises: 5820d3435290
Create Date: 2026-04-18 21:55:34.118757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '905825959a79'
down_revision: Union[str, Sequence[str], None] = '5820d3435290'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_UQ = "uq_taste_profile_albums_user_source_period_album_artist_type"
OLD_UQ = "taste_profile_albums_user_id_source_period_album_name_artis_key"


def upgrade() -> None:
    op.add_column(
        "taste_profile_albums",
        sa.Column(
            "release_type",
            sa.String(length=50),
            server_default="album",
            nullable=False,
        ),
    )
    op.drop_constraint(OLD_UQ, "taste_profile_albums", type_="unique")
    op.create_unique_constraint(
        NEW_UQ,
        "taste_profile_albums",
        ["user_id", "source", "period", "album_name", "artist_name", "release_type"],
    )


def downgrade() -> None:
    op.drop_constraint(NEW_UQ, "taste_profile_albums", type_="unique")
    op.create_unique_constraint(
        OLD_UQ,
        "taste_profile_albums",
        ["user_id", "source", "period", "album_name", "artist_name"],
    )
    op.drop_column("taste_profile_albums", "release_type")
