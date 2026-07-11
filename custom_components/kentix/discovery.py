"""Helpers for dynamically adding Kentix entities."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import KentixDataUpdateCoordinator


def async_setup_dynamic_entities[T](
    entry: ConfigEntry,
    coordinator: KentixDataUpdateCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    collection: Callable[[], Mapping[str, T]],
    factory: Callable[[T], list[Entity]],
) -> None:
    """Add entities now and whenever Kentix discovery finds new objects."""
    known_unique_ids: set[str] = set()

    @callback
    def async_discover() -> None:
        new_entities: list[Entity] = []
        for item in collection().values():
            for entity in factory(item):
                unique_id = entity.unique_id
                if unique_id is None or unique_id in known_unique_ids:
                    continue
                known_unique_ids.add(unique_id)
                new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    async_discover()
    entry.async_on_unload(coordinator.async_add_listener(async_discover))
