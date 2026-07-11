"""Kentix alarm control panel entities."""

from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_LAST_CHANGED_BY, ATTR_RAW_STATE
from .discovery import async_setup_dynamic_entities
from .entity import KentixEntity
from .models import KentixAlarmGroup

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kentix alarm groups."""
    coordinator = entry.runtime_data.coordinator
    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda: coordinator.data.alarm_groups,
        lambda group: [KentixAlarmControlPanel(coordinator, entry, group)],
    )


class KentixAlarmControlPanel(KentixEntity, AlarmControlPanelEntity):
    """Alarm panel representing one Kentix alarm group."""

    _attr_name = None
    _attr_code_arm_required = False
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY

    def __init__(
        self, coordinator, entry: ConfigEntry, group: KentixAlarmGroup
    ) -> None:
        super().__init__(coordinator, entry, "alarm_group", group.id, group.name)

    @property
    def _group(self) -> KentixAlarmGroup | None:
        return self.coordinator.data.alarm_groups.get(self._object_id)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.alarm_groups_available
            and self._group is not None
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        group = self._group
        if group is None:
            return None
        if group.triggered:
            return AlarmControlPanelState.TRIGGERED
        if group.arming:
            return AlarmControlPanelState.ARMING
        if group.disarming:
            return AlarmControlPanelState.DISARMING
        if group.partially_armed:
            return AlarmControlPanelState.ARMED_CUSTOM_BYPASS
        if group.armed is True:
            return AlarmControlPanelState.ARMED_AWAY
        if group.armed is False:
            return AlarmControlPanelState.DISARMED
        return None

    @property
    def changed_by(self) -> str | None:
        group = self._group
        return group.last_changed_by if group else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        group = self._group
        if group is None:
            return {}
        return {
            ATTR_RAW_STATE: group.raw_state,
            ATTR_LAST_CHANGED_BY: group.last_changed_by,
        }

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self.coordinator.async_execute_command(
            lambda: self.coordinator.client.async_arm_alarm_group(self._object_id)
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self.coordinator.async_execute_command(
            lambda: self.coordinator.client.async_disarm_alarm_group(self._object_id)
        )
