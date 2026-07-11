"""Async client for the KentixONE SmartAPI."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar
from urllib.parse import urlparse

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .models import KentixAlarmGroup, KentixData, KentixDoorLock


class KentixApiError(Exception):
    """Base Kentix SmartAPI error."""


class KentixAuthenticationError(KentixApiError):
    """Raised when the API token is invalid or lacks access."""


class KentixPermissionError(KentixApiError):
    """Raised when the API user lacks a required permission."""


class KentixConnectionError(KentixApiError):
    """Raised when the Kentix host cannot be reached."""


class KentixUnsupportedError(KentixApiError):
    """Raised when an endpoint is unavailable on the installed firmware."""


@dataclass(frozen=True, slots=True)
class KentixRoutes:
    """KentixONE SmartAPI routes used by this integration."""

    alarm_groups: tuple[str, ...] = (
        "/api/alarmgroups",
        "/api/alarmgroups/names",
    )
    alarm_group_details: str = "/api/alarmgroups/{object_id}"
    system_values: str = "/api/systemvalues"
    alarm_group_arm: str = "/api/alarmgroups/{object_id}/arm"
    alarm_group_disarm: str = "/api/alarmgroups/{object_id}/disarm"
    door_locks: tuple[str, ...] = (
        "/api/doorlocks",
        "/api/doorlocks/names",
    )
    door_lock_details: str = "/api/doorlocks/{object_id}"
    # Deprecated in KentixONE 8.6.3 but still documented. The method is kept
    # behind this adapter so a future replacement route is a one-line change.
    door_lock_open: str = "/api/doorlocks/{object_id}/open"


T = TypeVar("T", KentixAlarmGroup, KentixDoorLock)


class KentixApiClient:
    """Home-Assistant-friendly KentixONE API client."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        api_token: str,
        *,
        verify_ssl: bool = True,
        routes: KentixRoutes | None = None,
    ) -> None:
        self._session = session
        self._base_url = normalize_host(host)
        self._api_token = api_token.strip()
        self._verify_ssl = verify_ssl
        self._routes = routes or KentixRoutes()
        self._timeout = ClientTimeout(total=20)
        self._request_semaphore = asyncio.Semaphore(4)

    @property
    def base_url(self) -> str:
        """Return the normalized Kentix base URL."""
        return self._base_url

    async def async_validate_connection(self) -> None:
        """Validate host and token using non-mutating endpoints."""
        results = await asyncio.gather(
            self._request_candidates("GET", self._routes.alarm_groups),
            self._request_candidates("GET", self._routes.door_locks),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, KentixAuthenticationError):
                raise result
        if any(not isinstance(result, Exception) for result in results):
            return
        if all(isinstance(result, KentixPermissionError) for result in results):
            raise KentixPermissionError(
                "The Kentix API user cannot access alarm groups or DoorLocks"
            )
        first_error = next(
            result for result in results if isinstance(result, Exception)
        )
        raise first_error

    async def async_get_data(self) -> KentixData:
        """Fetch alarm groups and DoorLocks independently."""
        alarm_result, door_result = await asyncio.gather(
            self.async_get_alarm_groups(),
            self.async_get_door_locks(),
            return_exceptions=True,
        )

        if isinstance(alarm_result, KentixAuthenticationError):
            raise alarm_result
        if isinstance(door_result, KentixAuthenticationError):
            raise door_result

        if isinstance(alarm_result, Exception) and isinstance(door_result, Exception):
            raise KentixConnectionError(
                f"All Kentix data endpoints failed: {alarm_result}; {door_result}"
            )

        return KentixData(
            alarm_groups={} if isinstance(alarm_result, Exception) else alarm_result,
            door_locks={} if isinstance(door_result, Exception) else door_result,
            alarm_groups_available=not isinstance(alarm_result, Exception),
            door_locks_available=not isinstance(door_result, Exception),
        )

    async def async_get_alarm_groups(self) -> dict[str, KentixAlarmGroup]:
        """Fetch alarm-group inventory and merge live states from systemvalues."""
        groups = await self._async_get_collection(
            routes=self._routes.alarm_groups,
            details_route=self._routes.alarm_group_details,
            normalizer=KentixAlarmGroup.from_payload,
            state_keys={
                "armed",
                "is_armed",
                "switching_status",
                "switch_state",
                "alarm_state",
                "alarm_active",
                "alarm_count",
            },
        )

        try:
            system_values = await self._request("GET", self._routes.system_values)
        except KentixAuthenticationError:
            raise
        except KentixApiError:
            # Inventory/configuration remains useful when runtime values are not
            # permitted or unavailable. The alarm entities stay in unknown state.
            return groups

        return merge_alarm_group_runtime(groups, system_values)

    async def async_get_door_locks(self) -> dict[str, KentixDoorLock]:
        """Fetch and normalize all DoorLocks."""
        return await self._async_get_collection(
            routes=self._routes.door_locks,
            details_route=self._routes.door_lock_details,
            normalizer=KentixDoorLock.from_payload,
            state_keys={
                "open",
                "is_open",
                "door_open",
                "locked",
                "is_locked",
                "lock_state",
                "door_state",
                "online",
            },
        )

    async def _async_get_collection(
        self,
        *,
        routes: Sequence[str],
        details_route: str,
        normalizer: Callable[[Mapping[str, Any]], T],
        state_keys: set[str],
    ) -> dict[str, T]:
        payload = await self._request_collection_candidates(routes)
        items = extract_items(payload)
        items = await self._enrich_sparse_items(items, details_route, state_keys)
        normalized: dict[str, T] = {}
        for item in items:
            try:
                obj = normalizer(item)
            except (TypeError, ValueError):
                continue
            normalized[obj.id] = obj
        return normalized

    async def _enrich_sparse_items(
        self,
        items: list[dict[str, Any]],
        details_route: str,
        state_keys: set[str],
    ) -> list[dict[str, Any]]:
        """Fetch details only for list entries that do not contain state data."""
        enriched = list(items)
        task_positions: list[int] = []
        tasks: list[asyncio.Task[Any]] = []
        for position, item in enumerate(items):
            object_id = object_identifier(item)
            if object_id is None or state_keys.intersection(item):
                continue
            task_positions.append(position)
            tasks.append(
                asyncio.create_task(
                    self._request("GET", details_route.format(object_id=object_id))
                )
            )

        if not tasks:
            return enriched

        details = await asyncio.gather(*tasks, return_exceptions=True)
        for position, detail in zip(task_positions, details, strict=True):
            if isinstance(detail, Exception):
                continue
            enriched[position] = {**enriched[position], **extract_object(detail)}
        return enriched

    async def async_arm_alarm_group(self, object_id: str) -> None:
        """Arm an alarm group."""
        await self._request(
            "POST", self._routes.alarm_group_arm.format(object_id=object_id)
        )

    async def async_disarm_alarm_group(self, object_id: str) -> None:
        """Disarm an alarm group."""
        await self._request(
            "POST", self._routes.alarm_group_disarm.format(object_id=object_id)
        )

    async def async_open_door_lock(self, object_id: str) -> None:
        """Remotely open a DoorLock."""
        await self._request(
            "POST", self._routes.door_lock_open.format(object_id=object_id)
        )

    async def _request_collection_candidates(self, routes: Sequence[str]) -> Any:
        """Try collection routes and follow Kentix pagination when present."""
        last_error: KentixUnsupportedError | None = None
        for route in routes:
            try:
                return await self._request_paginated(route)
            except KentixUnsupportedError as err:
                last_error = err
        if last_error is not None:
            raise last_error
        raise KentixUnsupportedError("No Kentix collection routes configured")

    async def _request_paginated(self, route: str) -> Any:
        """Return a complete collection, following same-origin `links.next` URLs."""
        payload = await self._request("GET", route)
        if not isinstance(payload, Mapping):
            return payload

        first_items = payload.get("data")
        links = payload.get("links")
        if not isinstance(first_items, list) or not isinstance(links, Mapping):
            return payload

        all_items = list(first_items)
        next_link = links.get("next")
        seen: set[str] = set()
        while isinstance(next_link, str) and next_link and next_link not in seen:
            seen.add(next_link)
            next_payload = await self._request("GET", next_link)
            if not isinstance(next_payload, Mapping):
                break
            page_items = next_payload.get("data")
            if isinstance(page_items, list):
                all_items.extend(page_items)
            next_links = next_payload.get("links")
            next_link = (
                next_links.get("next") if isinstance(next_links, Mapping) else None
            )

        return {**payload, "data": all_items}

    async def _request_candidates(self, method: str, routes: Sequence[str]) -> Any:
        """Try route candidates in order, falling back only on unsupported routes."""
        last_error: KentixUnsupportedError | None = None
        for route in routes:
            try:
                return await self._request(method, route)
            except KentixUnsupportedError as err:
                last_error = err
        if last_error is not None:
            raise last_error
        raise KentixUnsupportedError("No Kentix API route candidates configured")

    async def _request(
        self,
        method: str,
        route: str,
        *,
        json_data: Mapping[str, Any] | None = None,
    ) -> Any:
        url = self._request_url(route)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_token}",
        }
        if json_data is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with (
                self._request_semaphore,
                self._session.request(
                    method,
                    url,
                    headers=headers,
                    json=json_data,
                    ssl=self._verify_ssl,
                    timeout=self._timeout,
                ) as response,
            ):
                return await self._handle_response(response)
        except KentixApiError:
            raise
        except (ClientError, TimeoutError, OSError) as err:
            raise KentixConnectionError(
                f"Cannot connect to {self._base_url}: {err}"
            ) from err

    def _request_url(self, route: str) -> str:
        """Build a request URL and reject cross-origin pagination links."""
        parsed_route = urlparse(route)
        if not parsed_route.scheme:
            return f"{self._base_url}{route}"

        base = urlparse(self._base_url)
        if (parsed_route.scheme, parsed_route.netloc) != (base.scheme, base.netloc):
            raise KentixApiError("Kentix pagination returned a cross-origin URL")
        return route

    async def _handle_response(self, response: ClientResponse) -> Any:
        text = await response.text()
        if response.status == 401:
            raise KentixAuthenticationError("Kentix rejected the API token")
        if response.status == 403:
            raise KentixPermissionError(
                f"Kentix denied access to {response.method} {response.url.path}"
            )
        if response.status in {404, 405, 501}:
            raise KentixUnsupportedError(
                f"Kentix endpoint is unavailable: {response.method} {response.url.path}"
            )
        if response.status >= 400:
            raise KentixApiError(
                f"Kentix API returned HTTP {response.status} for "
                f"{response.method} {response.url.path}"
            )
        if not text.strip():
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            raise KentixApiError("Kentix returned invalid JSON") from err


def extract_system_alarm_groups(payload: Any) -> list[dict[str, Any]]:
    """Extract live alarm-group values from `/api/systemvalues`."""
    if not isinstance(payload, Mapping):
        return []

    for key in ("alarmgroups", "alarm_groups"):
        value = payload.get(key)
        if isinstance(value, list):
            return _list_to_items(value)
        if isinstance(value, Mapping):
            nested = extract_items(value)
            if nested:
                return nested

    for key in ("data", "systemvalues", "system_values", "values", "result"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            nested = extract_system_alarm_groups(value)
            if nested:
                return nested
    return []


def alarm_group_runtime_identifier(item: Mapping[str, Any]) -> str | None:
    """Return an alarm-group ID without confusing a parent `group_id` for it."""
    for key in ("id", "alarmgroup_id", "alarm_group_id"):
        if key in item and item[key] is not None:
            return str(item[key])
    return None


def merge_alarm_group_runtime(
    groups: Mapping[str, KentixAlarmGroup], payload: Any
) -> dict[str, KentixAlarmGroup]:
    """Merge `/api/systemvalues` alarm-group states by ID, then unique name."""
    merged = dict(groups)
    runtime_items = extract_system_alarm_groups(payload)
    if not runtime_items:
        return merged

    names: dict[str, list[str]] = {}
    for group_id, group in groups.items():
        names.setdefault(group.name.strip().casefold(), []).append(group_id)

    for runtime in runtime_items:
        group_id = alarm_group_runtime_identifier(runtime)
        target_id = group_id if group_id in groups else None
        if target_id is None:
            name = runtime.get("name")
            if name is not None:
                candidates = names.get(str(name).strip().casefold(), [])
                if len(candidates) == 1:
                    target_id = candidates[0]
        if target_id is None:
            continue

        current = groups[target_id]
        combined = dict(current.raw)
        combined.update(runtime)
        combined["id"] = current.id
        combined.setdefault("name", current.name)
        if current.parent_group_id is not None:
            combined.setdefault("group_id", current.parent_group_id)
        merged[target_id] = KentixAlarmGroup.from_payload(combined)

    return merged


def normalize_host(host: str) -> str:
    """Normalize a user-entered host or URL."""
    value = host.strip().rstrip("/")
    if not value:
        raise ValueError("Host must not be empty")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Host must be a valid HTTP(S) URL or hostname")
    if parsed.username or parsed.password:
        raise ValueError("Credentials must not be embedded in the Kentix URL")
    if parsed.query or parsed.fragment:
        raise ValueError("Kentix URL must not contain a query or fragment")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _list_to_items(value: list[Any]) -> list[dict[str, Any]]:
    """Normalize a list of objects or IDs/names."""
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            result.append(dict(item))
        elif item is not None:
            result.append({"id": item, "name": str(item)})
    return result


def extract_items(payload: Any) -> list[dict[str, Any]]:
    """Extract a list from common SmartAPI response envelopes."""
    if isinstance(payload, list):
        return _list_to_items(payload)
    if not isinstance(payload, Mapping):
        return []
    if object_identifier(payload) is not None:
        return [dict(payload)]

    for key in (
        "data",
        "items",
        "results",
        "alarmgroups",
        "alarm_groups",
        "doorlocks",
        "door_locks",
        "names",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return _list_to_items(value)
        if isinstance(value, Mapping):
            nested = extract_items(value)
            if nested:
                return nested

    result: list[dict[str, Any]] = []
    for key, value in payload.items():
        if isinstance(value, Mapping):
            item = dict(value)
            if object_identifier(item) is None:
                item["id"] = key
            result.append(item)
        elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
            result.append({"id": key, "name": str(value)})
    return result


def extract_object(payload: Any) -> dict[str, Any]:
    """Extract an object from common SmartAPI response envelopes."""
    if not isinstance(payload, Mapping):
        return {}
    for key in ("data", "item", "result", "alarmgroup", "doorlock"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return dict(payload)


def object_identifier(item: Mapping[str, Any]) -> str | None:
    """Extract a Kentix object identifier."""
    for key in (
        "id",
        "alarmgroup_id",
        "alarm_group_id",
        "group_id",
        "doorlock_id",
        "door_lock_id",
        "device_id",
    ):
        if key in item and item[key] is not None:
            return str(item[key])
    return None
