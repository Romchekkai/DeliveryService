from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from delivery_service.domain.entities.parcel import ParcelType
from delivery_service.infrastructure.db.models.base_model import Base


class ParcelTypeModel(Base):
    __tablename__ = "parcel_type"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)

    def to_entity(self) -> ParcelType:
        return ParcelType(
            id=self.id,
            name=self.name,
        )

    @classmethod
    def from_entity(cls, parcel_type: ParcelType) -> "ParcelTypeModel":
        return cls(
            id=parcel_type.id,
            name=parcel_type.name,
        )
