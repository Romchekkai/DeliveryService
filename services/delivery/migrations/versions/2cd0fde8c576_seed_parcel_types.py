"""seed parcel types

Revision ID: 2cd0fde8c576
Revises: e155ba88af1e
Create Date: 2026-09-18 22:20:57.009718

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2cd0fde8c576"
down_revision: Union[str, Sequence[str], None] = "e155ba88af1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    parcel_type = sa.table("parcel_type", sa.column("name", sa.String))
    op.bulk_insert(
        parcel_type,
        [
            {"name": "Одежда"},
            {"name": "Электроника"},
            {"name": "Разное"},
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM parcel_type WHERE name IN ('Одежда', 'Электроника', 'Разное')")
