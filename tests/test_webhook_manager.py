"""Tests for automatic KentixONE webhook management."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.kentix.webhook_manager import (
    KentixWebhookManager,
    _canonical_assignments,
    _desired_assignments,
)


def test_managed_webhook_assignments_use_validated_event_codes() -> None:
    assignments = _desired_assignments("3")
    assert [item["event"] for item in assignments] == [0, 5, 50]
    assert assignments[0]["trigger_on_alarm"] is True
    assert assignments[0]["trigger_on_warning"] is True
    assert assignments[2]["trigger_on_alarm"] is False
    assert assignments[2]["trigger_on_warning"] is False


def test_assignment_comparison_is_order_independent() -> None:
    desired = _desired_assignments("3")
    assert _canonical_assignments(desired) == _canonical_assignments(
        list(reversed(desired))
    )


class _FakeWebhookClient:
    def __init__(self) -> None:
        self.webhooks: list[dict] = []
        self.groups = {
            "1": {
                "webhooks": [
                    {
                        "webhook_id": 77,
                        "event": 4,
                        "trigger_on_alarm": True,
                        "trigger_on_warning": False,
                        "cycle_time": None,
                    }
                ]
            },
            "2": {"webhooks": []},
        }
        self.detail_reads: list[str] = []
        self.assignment_writes: list[tuple[str, list[dict]]] = []
        self.deleted: list[str] = []

    async def async_get_webhooks(self) -> list[dict]:
        return [dict(item) for item in self.webhooks]

    async def async_create_webhook(self, payload) -> dict:
        created = {"id": 9, **dict(payload)}
        self.webhooks.append(created)
        return dict(created)

    async def async_update_webhook(self, object_id: str, payload) -> dict:
        current = next(item for item in self.webhooks if str(item["id"]) == object_id)
        current.update(dict(payload))
        return dict(current)

    async def async_delete_webhook(self, object_id: str) -> None:
        self.deleted.append(object_id)
        self.webhooks = [item for item in self.webhooks if str(item["id"]) != object_id]

    async def async_get_alarm_group_inventory(self) -> dict:
        return {object_id: object() for object_id in self.groups}

    async def async_get_alarm_group_detail(self, object_id: str) -> dict:
        self.detail_reads.append(object_id)
        return {"webhooks": [dict(item) for item in self.groups[object_id]["webhooks"]]}

    async def async_set_alarm_group_webhooks(self, object_id: str, webhooks) -> dict:
        assignments = [dict(item) for item in webhooks]
        self.assignment_writes.append((object_id, assignments))
        self.groups[object_id]["webhooks"] = assignments
        return {"webhooks": assignments}


@pytest.mark.asyncio
async def test_manager_creates_active_webhook_and_preserves_foreign_assignments() -> (
    None
):
    client = _FakeWebhookClient()
    entry = SimpleNamespace(entry_id="entry-123")
    manager = KentixWebhookManager(
        None,
        entry,
        client,
        "http://homeassistant.local/api/webhook/secret",
        enabled=True,
    )

    await manager.async_ensure()

    assert manager.configured is True
    assert manager.webhook_id == "9"
    assert client.webhooks[0]["is_active"] is True
    assert client.webhooks[0]["request_type"] == 0
    assert client.webhooks[0]["content_type"] == 0
    assert client.webhooks[0]["url"].endswith("/api/webhook/secret")
    assert {item["event"] for item in client.groups["1"]["webhooks"]} == {
        0,
        4,
        5,
        50,
    }
    assert {item["event"] for item in client.groups["2"]["webhooks"]} == {
        0,
        5,
        50,
    }

    reads_after_first_sync = list(client.detail_reads)
    await manager.async_ensure()
    assert client.detail_reads == reads_after_first_sync


@pytest.mark.asyncio
async def test_manager_only_reconciles_new_alarm_groups_after_initial_sync() -> None:
    client = _FakeWebhookClient()
    entry = SimpleNamespace(entry_id="entry-123")
    manager = KentixWebhookManager(
        None,
        entry,
        client,
        "http://homeassistant.local/api/webhook/secret",
        enabled=True,
    )
    await manager.async_ensure()
    client.detail_reads.clear()
    client.groups["3"] = {"webhooks": []}

    await manager.async_ensure()

    assert client.detail_reads == ["3"]
    assert {item["event"] for item in client.groups["3"]["webhooks"]} == {
        0,
        5,
        50,
    }


@pytest.mark.asyncio
async def test_delete_managed_removes_only_owned_webhook_and_assignments() -> None:
    client = _FakeWebhookClient()
    entry = SimpleNamespace(entry_id="entry-123")
    manager = KentixWebhookManager(
        None,
        entry,
        client,
        "http://homeassistant.local/api/webhook/secret",
        enabled=True,
    )
    await manager.async_ensure()

    await manager.async_delete_managed()

    assert client.deleted == ["9"]
    assert client.webhooks == []
    assert client.groups["1"]["webhooks"] == [
        {
            "webhook_id": 77,
            "event": 4,
            "trigger_on_alarm": True,
            "trigger_on_warning": False,
            "cycle_time": None,
        }
    ]
    assert client.groups["2"]["webhooks"] == []
