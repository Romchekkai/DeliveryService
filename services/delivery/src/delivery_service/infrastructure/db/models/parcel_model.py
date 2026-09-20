import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from delivery_service.domain.entities.parcel import Parcel, ParcelType
from delivery_service.domain.value_objects.parcel_status import ParcelStatus
from delivery_service.infrastructure.db.models.base_model import Base
from delivery_service.infrastructure.db.models.parcel_type_model import ParcelTypeModel


class ParcelModel(Base):
    __tablename__ = "parcel"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    weight_kg: Mapped[float] = mapped_column(
        Float, CheckConstraint("weight_kg > 0 and weight_kg < 500"), nullable=False
    )
    type_id: Mapped[int] = mapped_column(
        ForeignKey("parcel_type.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    type: Mapped[ParcelTypeModel] = relationship(lazy="joined")

    content_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    delivery_cost_rub: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2), nullable=True
    )
    status: Mapped[ParcelStatus] = mapped_column(
        Enum(ParcelStatus), nullable=False, default=ParcelStatus.ACTIVE
    )

    def to_entity(self) -> Parcel:
        p_type = ParcelType(self.type_id, self.type.name)
        delivery_cost = (
            Decimal(str(self.delivery_cost_rub)) if self.delivery_cost_rub else Decimal("0")
        )
        return Parcel(
            id=self.id,
            user_id=self.user_id,
            name=self.name,
            weight_kg=self.weight_kg,
            type=p_type,
            content_cost_cents=self.content_cost_cents,
            delivery_cost_rub=delivery_cost,
            status=self.status,
        )

    @classmethod
    def from_entity(cls, parcel: Parcel) -> "ParcelModel":
        return cls(
            id=parcel.id,
            user_id=parcel.user_id,
            name=parcel.name,
            weight_kg=parcel.weight_kg,
            type_id=parcel.type.id,
            content_cost_cents=parcel.content_cost_cents,
            delivery_cost_rub=parcel.delivery_cost_rub or None,
            status=parcel.status,
        )
