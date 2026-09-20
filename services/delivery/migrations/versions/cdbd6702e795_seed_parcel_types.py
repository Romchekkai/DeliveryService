"""seed parcel types

Revision ID: cdbd6702e795
Revises: 703b3dd74ffa
Create Date: 2026-09-20 17:10:00.980307

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cdbd6702e795"
down_revision: Union[str, Sequence[str], None] = "703b3dd74ffa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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
    """Downgrade schema."""
    op.execute("DELETE FROM parcel_type WHERE name IN ('Одежда', 'Электроника', 'Разное')")
