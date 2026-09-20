import uuid
from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest
from delivery_service.application.use_cases.calculate_delivery_cost import (
    CalculateDeliveryCostsUseCase,
)
from delivery_service.domain.entities.parcel import ParcelType
from delivery_service.domain.value_objects.parcel_status import ParcelStatus
from delivery_service.infrastructure.db.repositories.sql_alc_parcel_repository import (
    SqlAlchemyParcelRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.fakes.repositories import FakeRateProvider

Auth = Callable[..., dict[str, str]]

NEW_PARCEL = {
    "name": "Laptop",
    "weight_kg": 2.0,
    "parcel_type_id": 2,
    "content_cost_cents": 1000,
}


async def create_parcel(
    client: httpx.AsyncClient, headers: dict[str, str], **overrides: object
) -> httpx.Response:
    return await client.post("/api/v1/parcels", json={**NEW_PARCEL, **overrides}, headers=headers)


class TestParcelTypes:
    async def test_types_are_public(
        self, client: httpx.AsyncClient, parcel_types: list[ParcelType]
    ) -> None:
        response = await client.get("/api/v1/parcels/types")

        assert response.status_code == 200
        assert sorted(response.json(), key=lambda t: t["id"]) == [
            {"id": 1, "name": "Одежда"},
            {"id": 2, "name": "Электроника"},
            {"id": 3, "name": "Разное"},
        ]

    async def test_types_route_is_not_shadowed_by_parcel_id(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/api/v1/parcels/types")

        assert response.status_code == 200  # not 422 "types is not a valid UUID"


class TestCreateParcel:
    async def test_create_201(
        self, client: httpx.AsyncClient, auth: Auth, parcel_types: list[ParcelType]
    ) -> None:
        response = await create_parcel(client, auth())

        assert response.status_code == 201
        body = response.json()
        assert uuid.UUID(body["id"])
        assert body["name"] == "Laptop"
        assert body["parcel_type"] == "Электроника"
        assert body["delivery_cost_rub"] == "Не рассчитано"

    async def test_parcel_belongs_to_the_token_owner(
        self, client: httpx.AsyncClient, auth: Auth, parcel_types: list[ParcelType]
    ) -> None:
        owner = uuid.uuid4()
        parcel_id = (await create_parcel(client, auth(owner))).json()["id"]

        mine = await client.get(f"/api/v1/parcels/{parcel_id}", headers=auth(owner))
        stranger = await client.get(f"/api/v1/parcels/{parcel_id}", headers=auth(uuid.uuid4()))

        assert mine.status_code == 200
        assert stranger.status_code == 404

    async def test_one_user_can_create_several_parcels(
        self, client: httpx.AsyncClient, auth: Auth, parcel_types: list[ParcelType]
    ) -> None:
        headers = auth()

        first = await create_parcel(client, headers, name="first")
        second = await create_parcel(client, headers, name="second")

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] != second.json()["id"]

    async def test_unknown_parcel_type_404(
        self, client: httpx.AsyncClient, auth: Auth, parcel_types: list[ParcelType]
    ) -> None:
        response = await create_parcel(client, auth(), parcel_type_id=999)

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "override",
        [
            {"name": ""},
            {"name": "x" * 101},
            {"weight_kg": 0},
            {"weight_kg": -3},
            {"weight_kg": 500},
            {"content_cost_cents": -1},
            {"parcel_type_id": "abc"},
        ],
    )
    async def test_invalid_payload_422(
        self,
        client: httpx.AsyncClient,
        auth: Auth,
        parcel_types: list[ParcelType],
        override: dict[str, object],
    ) -> None:
        response = await create_parcel(client, auth(), **override)

        assert response.status_code == 422

    async def test_whitespace_name_is_a_domain_error_400(
        self, client: httpx.AsyncClient, auth: Auth, parcel_types: list[ParcelType]
    ) -> None:
        response = await create_parcel(client, auth(), name="   ")

        assert response.status_code == 400


class TestAuthentication:
    @pytest.mark.parametrize(
        ("method", "url"),
        [
            ("POST", "/api/v1/parcels"),
            ("GET", "/api/v1/parcels"),
            ("GET", f"/api/v1/parcels/{uuid.uuid4()}"),
        ],
    )
    async def test_token_is_required(
        self, client: httpx.AsyncClient, method: str, url: str
    ) -> None:
        response = await client.request(method, url, json=NEW_PARCEL if method == "POST" else None)

        assert response.status_code in (401, 403)

    async def test_garbage_token_401(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/parcels", headers={"Authorization": "Bearer garbage"})

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    async def test_token_signed_with_a_foreign_key_401(
        self, client: httpx.AsyncClient, make_token: Callable[..., str]
    ) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa

        foreign = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        response = await client.get(
            "/api/v1/parcels", headers={"Authorization": f"Bearer {make_token(key=foreign)}"}
        )

        assert response.status_code == 401

    async def test_expired_token_401(
        self, client: httpx.AsyncClient, make_token: Callable[..., str]
    ) -> None:
        from datetime import timedelta

        token = make_token(expires_in=timedelta(seconds=-10))

        response = await client.get("/api/v1/parcels", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401


class TestListParcels:
    async def test_lists_only_my_parcels(
        self, client: httpx.AsyncClient, auth: Auth, parcel_types: list[ParcelType]
    ) -> None:
        me, other = uuid.uuid4(), uuid.uuid4()
        await create_parcel(client, auth(me), name="mine")
        await create_parcel(client, auth(other), name="theirs")

        response = await client.get("/api/v1/parcels", headers=auth(me))

        assert response.status_code == 200
        assert response.json() == [
            {"name": "mine", "parcel_type": "Электроника", "delivery_cost_rub": "Не рассчитано"}
        ]

    async def test_limit_and_name_filter(
        self, client: httpx.AsyncClient, auth: Auth, parcel_types: list[ParcelType]
    ) -> None:
        headers = auth()
        for name in ("Red book", "Blue BOOK", "Laptop", "Phone", "Cable", "Shoes"):
            await create_parcel(client, headers, name=name)

        default_page = await client.get("/api/v1/parcels", headers=headers)
        big_page = await client.get("/api/v1/parcels", params={"limit": 100}, headers=headers)
        filtered = await client.get(
            "/api/v1/parcels", params={"name_filter": "book"}, headers=headers
        )

        assert len(default_page.json()) == 5
        assert len(big_page.json()) == 6
        assert sorted(p["name"] for p in filtered.json()) == ["Blue BOOK", "Red book"]

    @pytest.mark.parametrize("limit", [0, -1, 101])
    async def test_limit_is_validated(
        self, client: httpx.AsyncClient, auth: Auth, limit: int
    ) -> None:
        response = await client.get("/api/v1/parcels", params={"limit": limit}, headers=auth())

        assert response.status_code == 422


class TestGetParcel:
    async def test_get_own_parcel(
        self, client: httpx.AsyncClient, auth: Auth, parcel_types: list[ParcelType]
    ) -> None:
        headers = auth()
        parcel_id = (await create_parcel(client, headers)).json()["id"]

        response = await client.get(f"/api/v1/parcels/{parcel_id}", headers=headers)

        assert response.status_code == 200
        assert response.json() == {
            "id": parcel_id,
            "name": "Laptop",
            "weight_kg": 2.0,
            "parcel_type": "Электроника",
            "content_cost_usd": 10.0,
            "delivery_cost_rub": "Не рассчитано",
            "status": "active",
        }

    async def test_unknown_parcel_404(self, client: httpx.AsyncClient, auth: Auth) -> None:
        response = await client.get(f"/api/v1/parcels/{uuid.uuid4()}", headers=auth())

        assert response.status_code == 404

    async def test_invalid_uuid_422(self, client: httpx.AsyncClient, auth: Auth) -> None:
        response = await client.get("/api/v1/parcels/not-a-uuid", headers=auth())

        assert response.status_code == 422


class TestDeliveryCostLifecycle:
    """Create -> the 5-minute job calculates -> the cost follows the rate -> paid = frozen."""

    async def run_job(self, session_factory: async_sessionmaker[AsyncSession], rate: str) -> int:
        async with session_factory() as session:
            return await CalculateDeliveryCostsUseCase(
                SqlAlchemyParcelRepository(session), FakeRateProvider(rate)
            ).execute()

    async def test_cost_appears_after_the_job_and_follows_the_rate(
        self,
        client: httpx.AsyncClient,
        auth: Auth,
        parcel_types: list[ParcelType],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        headers = auth()
        parcel_id = (await create_parcel(client, headers)).json()["id"]
        url = f"/api/v1/parcels/{parcel_id}"
        assert (await client.get(url, headers=headers)).json()[
            "delivery_cost_rub"
        ] == "Не рассчитано"

        assert await self.run_job(session_factory, "90") == 1
        assert (await client.get(url, headers=headers)).json()["delivery_cost_rub"] == "99.00"

        assert await self.run_job(session_factory, "100") == 1
        assert (await client.get(url, headers=headers)).json()["delivery_cost_rub"] == "110.00"
        listing = await client.get("/api/v1/parcels", headers=headers)
        assert listing.json()[0]["delivery_cost_rub"] == "110.00"

    async def test_cost_is_frozen_once_the_parcel_is_no_longer_active(
        self,
        client: httpx.AsyncClient,
        auth: Auth,
        parcel_types: list[ParcelType],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        headers = auth()
        parcel_id = (await create_parcel(client, headers)).json()["id"]
        await self.run_job(session_factory, "90")

        async with session_factory() as session:  # the user pays
            repo = SqlAlchemyParcelRepository(session)
            parcel = await repo.get_parcel_by_id(uuid.UUID(parcel_id))
            assert parcel is not None
            parcel.status = ParcelStatus.IN_DELIVERY
            await repo.save_parcel(parcel)

        assert await self.run_job(session_factory, "100") == 0

        body = (await client.get(f"/api/v1/parcels/{parcel_id}", headers=headers)).json()
        assert body["status"] == "in_delivery"
        assert Decimal(body["delivery_cost_rub"]) == Decimal("99.00")


class TestOperationalEndpoints:
    async def test_health(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_metrics(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/metrics")

        assert response.status_code == 200
        assert "delivery_calculation_runs_total" in response.text
