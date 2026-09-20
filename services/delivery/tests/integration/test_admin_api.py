import importlib
from collections.abc import Callable

import httpx
import pytest
from delivery_service.domain.exceptions import CurrencyRateUnavailableError

# `routers/__init__` re-exports the APIRouter under the same name, so import the module itself.
admin_module = importlib.import_module("delivery_service.presentation.api.routers.admin_router")

Auth = Callable[..., dict[str, str]]


class TestListJobs:
    async def test_admin_can_list_jobs(self, client: httpx.AsyncClient, auth: Auth) -> None:
        response = await client.get("/api/v1/admin/tasks", headers=auth(role="admin"))

        assert response.status_code == 200
        body = response.json()
        assert "running" in body and isinstance(body["jobs"], list)

    async def test_regular_user_is_forbidden(self, client: httpx.AsyncClient, auth: Auth) -> None:
        response = await client.get("/api/v1/admin/tasks", headers=auth(role="user"))

        assert response.status_code == 403

    async def test_anonymous_is_rejected(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/admin/tasks")

        assert response.status_code in (401, 403)


class TestRunCalculateCosts:
    async def test_admin_triggers_a_manual_run(
        self, client: httpx.AsyncClient, auth: Auth, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        triggers: list[str] = []

        async def fake_run(trigger: str = "scheduler") -> int:
            triggers.append(trigger)
            return 3

        monkeypatch.setattr(admin_module, "run_calculate_delivery_costs", fake_run)

        response = await client.post(
            "/api/v1/admin/tasks/calculate-costs", headers=auth(role="admin")
        )

        assert response.status_code == 200
        assert response.json()["processed"] == 3
        assert response.json()["task"] == "calculate_delivery_costs"
        assert triggers == ["manual"]

    async def test_failed_run_is_reported_as_503(
        self, client: httpx.AsyncClient, auth: Auth, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def failing_run(trigger: str = "scheduler") -> int:
            raise CurrencyRateUnavailableError("CBR is down")

        monkeypatch.setattr(admin_module, "run_calculate_delivery_costs", failing_run)

        response = await client.post(
            "/api/v1/admin/tasks/calculate-costs", headers=auth(role="admin")
        )

        assert response.status_code == 503
        assert "CBR is down" in response.json()["detail"]

    async def test_regular_user_is_forbidden(
        self, client: httpx.AsyncClient, auth: Auth, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def must_not_run(trigger: str = "scheduler") -> int:
            raise AssertionError("the job must not run for a non-admin")

        monkeypatch.setattr(admin_module, "run_calculate_delivery_costs", must_not_run)

        response = await client.post(
            "/api/v1/admin/tasks/calculate-costs", headers=auth(role="user")
        )

        assert response.status_code == 403
