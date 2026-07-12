"""Config flow for Kentix."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.components import webhook as ha_webhook
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    KentixApiClient,
    KentixApiError,
    KentixAuthenticationError,
    KentixConnectionError,
    KentixPermissionError,
    normalize_host,
)
from .const import (
    CONF_API_TOKEN,
    CONF_MANAGE_WEBHOOK,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_ACCESS_MANAGERS,
    CONF_VERIFY_SSL,
    CONF_WEBHOOK_ID,
    DEFAULT_MANAGE_WEBHOOK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHOW_ACCESS_MANAGERS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


class KentixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Kentix config flow."""

    VERSION = 1

    async def _async_validate(self, host: str, api_token: str, verify_ssl: bool) -> str:
        normalized_host = normalize_host(host)
        client = KentixApiClient(
            async_get_clientsession(self.hass, verify_ssl=verify_ssl),
            normalized_host,
            api_token,
            verify_ssl=verify_ssl,
        )
        await client.async_validate_connection()
        return normalized_host

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                normalized_host = await self._async_validate(
                    user_input[CONF_HOST],
                    user_input[CONF_API_TOKEN],
                    user_input[CONF_VERIFY_SSL],
                )
            except KentixAuthenticationError:
                errors["base"] = "invalid_auth"
            except KentixPermissionError:
                errors["base"] = "insufficient_permissions"
            except (KentixConnectionError, KentixApiError, ValueError):
                errors["base"] = "cannot_connect"
            except Exception:  # pragma: no cover - HA logs unexpected failures
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(normalized_host.lower())
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: normalized_host}
                )
                display_host = normalized_host.removeprefix("https://").removeprefix(
                    "http://"
                )
                return self.async_create_entry(
                    title=f"KentixONE ({display_host})",
                    data={
                        CONF_HOST: normalized_host,
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                        CONF_WEBHOOK_ID: ha_webhook.async_generate_id(),
                    },
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_MANAGE_WEBHOOK: DEFAULT_MANAGE_WEBHOOK,
                        CONF_SHOW_ACCESS_MANAGERS: DEFAULT_SHOW_ACCESS_MANAGERS,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update an expired or revoked API token."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                normalized_host = await self._async_validate(
                    entry.data[CONF_HOST],
                    user_input[CONF_API_TOKEN],
                    entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                )
            except KentixAuthenticationError:
                errors["base"] = "invalid_auth"
            except KentixPermissionError:
                errors["base"] = "insufficient_permissions"
            except (KentixConnectionError, KentixApiError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(normalized_host.lower())
                self._abort_if_unique_id_mismatch()
                return self.async_update_and_abort(
                    entry,
                    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow changing host, token, and TLS settings."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                normalized_host = await self._async_validate(
                    user_input[CONF_HOST],
                    user_input[CONF_API_TOKEN],
                    user_input[CONF_VERIFY_SSL],
                )
            except KentixAuthenticationError:
                errors["base"] = "invalid_auth"
            except KentixPermissionError:
                errors["base"] = "insufficient_permissions"
            except (KentixConnectionError, KentixApiError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(normalized_host.lower())
                self._abort_if_unique_id_mismatch()
                display_host = normalized_host.removeprefix("https://").removeprefix(
                    "http://"
                )
                return self.async_update_and_abort(
                    entry,
                    title=f"KentixONE ({display_host})",
                    data_updates={
                        CONF_HOST: normalized_host,
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(
                host=entry.data[CONF_HOST],
                verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Return the options flow."""
        return KentixOptionsFlow()


class KentixOptionsFlow(OptionsFlow):
    """Kentix options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        manage_webhook = self.config_entry.options.get(
            CONF_MANAGE_WEBHOOK, DEFAULT_MANAGE_WEBHOOK
        )
        show_access_managers = self.config_entry.options.get(
            CONF_SHOW_ACCESS_MANAGERS, DEFAULT_SHOW_ACCESS_MANAGERS
        )
        webhook_id = self.config_entry.data.get(CONF_WEBHOOK_ID, "")
        webhook_url = ha_webhook.async_generate_path(webhook_id) if webhook_id else "-"
        if self.config_entry.state is ConfigEntryState.LOADED:
            webhook_url = self.config_entry.runtime_data.webhook_url

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                    vol.Required(
                        CONF_MANAGE_WEBHOOK, default=manage_webhook
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_SHOW_ACCESS_MANAGERS, default=show_access_managers
                    ): BooleanSelector(),
                }
            ),
            description_placeholders={"webhook_url": webhook_url},
        )


def _connection_schema(
    *, host: str | None = None, verify_ssl: bool = DEFAULT_VERIFY_SSL
) -> vol.Schema:
    """Build the connection form schema."""
    host_marker = (
        vol.Required(CONF_HOST, default=host) if host else vol.Required(CONF_HOST)
    )
    return vol.Schema(
        {
            host_marker: TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_API_TOKEN): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_VERIFY_SSL, default=verify_ssl): BooleanSelector(),
        }
    )
