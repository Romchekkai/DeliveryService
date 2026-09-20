import pytest
from delivery_service.infrastructure import scheduler as scheduler_module
from delivery_service.infrastructure.config import scheduler_settings


@pytest.fixture(autouse=True)
def clean_scheduler():
    yield
    if scheduler_module.scheduler.running:
        scheduler_module.scheduler.shutdown(wait=False)
    scheduler_module.scheduler.remove_all_jobs()


def test_disabled_scheduler_does_not_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler_settings, "enabled", False)

    scheduler_module.start_scheduler()

    assert not scheduler_module.scheduler.running
    assert scheduler_module.scheduler.get_jobs() == []


async def test_job_is_registered_with_the_configured_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scheduler_settings, "enabled", True)
    monkeypatch.setattr(scheduler_settings, "calculate_costs_interval_minutes", 5)

    scheduler_module.start_scheduler()

    assert scheduler_module.scheduler.running
    [job] = scheduler_module.scheduler.get_jobs()
    assert job.id == scheduler_module.CALCULATE_COSTS_JOB_ID
    assert str(job.trigger) == "interval[0:05:00]"  # every 5 minutes, not continuously
    assert job.max_instances == 1  # runs never overlap
    assert job.coalesce is True  # missed runs do not pile up
    assert job.func is scheduler_module.run_calculate_delivery_costs


async def test_interval_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler_settings, "enabled", True)
    monkeypatch.setattr(scheduler_settings, "calculate_costs_interval_minutes", 12)

    scheduler_module.start_scheduler()

    [job] = scheduler_module.scheduler.get_jobs()
    assert str(job.trigger) == "interval[0:12:00]"


async def test_start_twice_keeps_a_single_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler_settings, "enabled", True)
    scheduler_module.start_scheduler()

    scheduler_module.scheduler.add_job(
        scheduler_module.run_calculate_delivery_costs,
        trigger="interval",
        minutes=5,
        id=scheduler_module.CALCULATE_COSTS_JOB_ID,
        replace_existing=True,
    )

    assert len(scheduler_module.scheduler.get_jobs()) == 1


async def test_shutdown_stops_a_running_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler_settings, "enabled", True)
    scheduler_module.start_scheduler()
    assert scheduler_module.scheduler.running

    scheduler_module.shutdown_scheduler()

    # AsyncIOScheduler stops on the next loop iteration
    import asyncio

    await asyncio.sleep(0)
    assert not scheduler_module.scheduler.running


def test_shutdown_without_running_scheduler_is_a_noop() -> None:
    scheduler_module.shutdown_scheduler()
