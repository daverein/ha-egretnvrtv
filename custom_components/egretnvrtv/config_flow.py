"""Config flow for the Egret NVR TV integration.

Pairing exchange (see the TV app's NotificationHttpServer.java for the other side):

1. The TV is either auto-discovered via zeroconf (_egretnvrtv._tcp.local.) or entered
   manually (host/port). The same form also collects the Frigate MQTT topic prefix, and
   whether to register the TV as a Home Assistant companion app (plus its device name if
   so) — everything the TV's own setup wizard would otherwise ask for on-device.
2. This flow POSTs to the TV's `/ha_pair/start` — which makes the TV display a short PIN
   on-screen and returns its stable device_id/device_name so this flow can dedupe/title the
   entry without trusting zeroconf TXT records (best-effort and inconsistent across OEM
   Android TV builds).
3. The user reads the PIN off the TV and types it into the form shown here.
4. This flow mints a fresh Long-Lived Access Token for the instance owner (see
   _async_mint_token below), and POSTs {pin, host, token, mqtt_topic_prefix,
   register_companion_app, companion_device_name} to the TV's `/ha_pair/complete`. The TV
   only accepts this if the PIN matches what it's still showing and hasn't expired — that
   PIN is the entire proof that whoever is submitting this form is physically looking at the
   right TV, since the pairing endpoint itself has no other auth. On success the TV saves
   the host/token immediately, then (best-effort, non-fatal if it fails) completes its own
   existing companion-app registration using that same token, if asked to.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    ACCESS_TOKEN_LIFESPAN_DAYS,
    CONF_COMPANION_DEVICE_NAME,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_REGISTER_COMPANION_APP,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_PORT,
    DEFAULT_REGISTER_COMPANION_APP,
    DOMAIN,
    PAIR_COMPLETE_PATH,
    PAIR_START_PATH,
    REQUEST_TIMEOUT_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

CONF_PIN = "pin"

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_PIN = "invalid_pin"
ERROR_NO_LOCAL_URL = "no_local_url"


class EgretNvrTvConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Egret NVR TV."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._device_id: str | None = None
        self._device_name: str | None = None
        self._mqtt_topic_prefix: str = DEFAULT_MQTT_TOPIC_PREFIX
        self._register_companion_app: bool = DEFAULT_REGISTER_COMPANION_APP
        self._companion_device_name: str = ""

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a TV discovered via zeroconf."""
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT

        # Best-effort early dedup so re-discovering an already-paired TV (mDNS re-announces
        # periodically) doesn't keep popping a "new device found" notification — properties
        # are whatever the TV's TXT record happened to include, not trusted beyond this.
        early_id = discovery_info.properties.get(CONF_DEVICE_ID) or f"{self._host}:{self._port}"
        await self.async_set_unique_id(str(early_id))
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )

        self._device_name = discovery_info.properties.get(CONF_DEVICE_NAME) or self._host
        self.context["title_placeholders"] = {"name": self._device_name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm pairing with a zeroconf-discovered TV and collect setup choices."""
        if user_input is not None:
            return await self._async_start_pairing(user_input)

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=self._confirm_schema(
                {CONF_COMPANION_DEVICE_NAME: self._device_name or ""}
            ),
            description_placeholders={"name": self._device_name or self._host or ""},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual entry, for a TV that wasn't auto-discovered on the network."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            result = await self._async_start_pairing(user_input, errors=errors)
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(user_input),
                    errors=errors,
                )
            return result

        return self.async_show_form(step_id="user", data_schema=self._user_schema())

    @staticmethod
    def _confirm_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_MQTT_TOPIC_PREFIX,
                    default=defaults.get(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX),
                ): str,
                vol.Required(
                    CONF_REGISTER_COMPANION_APP,
                    default=defaults.get(
                        CONF_REGISTER_COMPANION_APP, DEFAULT_REGISTER_COMPANION_APP
                    ),
                ): bool,
                # Only used when the checkbox above is on — shown as the device/notify target
                # name in Home Assistant, same "device name" the TV's own setup wizard asks
                # for when registering as a companion app.
                vol.Optional(
                    CONF_COMPANION_DEVICE_NAME,
                    default=defaults.get(CONF_COMPANION_DEVICE_NAME, ""),
                ): str,
            }
        )

    @classmethod
    def _user_schema(cls, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        schema = {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
        }
        schema.update(cls._confirm_schema(defaults).schema)
        return vol.Schema(schema)

    async def _async_start_pairing(
        self, user_input: dict[str, Any], errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """POST /ha_pair/start, learn the TV's real identity, and move to the PIN step."""
        self._mqtt_topic_prefix = user_input[CONF_MQTT_TOPIC_PREFIX]
        self._register_companion_app = user_input[CONF_REGISTER_COMPANION_APP]
        self._companion_device_name = user_input.get(CONF_COMPANION_DEVICE_NAME, "") or (
            self._device_name or self._host or ""
        )
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"http://{self._host}:{self._port}{PAIR_START_PATH}",
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Could not reach TV at %s:%s: %s", self._host, self._port, err)
            if errors is not None:
                errors["base"] = ERROR_CANNOT_CONNECT
                return None  # type: ignore[return-value]
            return self.async_abort(reason=ERROR_CANNOT_CONNECT)

        self._device_id = str(data.get(CONF_DEVICE_ID) or f"{self._host}:{self._port}")
        self._device_name = str(data.get(CONF_DEVICE_NAME) or self._device_name or self._host)

        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )

        return await self.async_step_pin()

    async def async_step_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the PIN shown on the TV, then finish pairing."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_finish_pairing(user_input[CONF_PIN])
            if not errors:
                return self.async_create_entry(
                    title=self._device_name or self._host or "Egret NVR TV",
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_DEVICE_ID: self._device_id,
                        CONF_DEVICE_NAME: self._device_name,
                        CONF_MQTT_TOPIC_PREFIX: self._mqtt_topic_prefix,
                    },
                )
            if errors.get("base") == ERROR_INVALID_PIN:
                # The PIN the TV was showing is now spent/expired — ask it to display a fresh
                # one rather than leave the user stuck retrying a code that can never work.
                await self._async_request_new_pin()

        return self.async_show_form(
            step_id="pin",
            data_schema=vol.Schema({vol.Required(CONF_PIN): str}),
            errors=errors,
            description_placeholders={"name": self._device_name or self._host or ""},
        )

    async def _async_request_new_pin(self) -> None:
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"http://{self._host}:{self._port}{PAIR_START_PATH}",
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            ):
                pass
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Could not request a fresh PIN: %s", err)

    async def _async_finish_pairing(self, pin: str) -> dict[str, str]:
        """POST /ha_pair/complete with a freshly minted token. Returns a form errors dict."""
        try:
            local_url = get_url(self.hass, allow_external=False, prefer_external=False)
        except NoURLAvailableError:
            return {"base": ERROR_NO_LOCAL_URL}

        try:
            token = await self._async_mint_token()
        except ValueError as err:
            _LOGGER.error("Could not create a Home Assistant access token for the TV: %s", err)
            return {"base": ERROR_CANNOT_CONNECT}

        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"http://{self._host}:{self._port}{PAIR_COMPLETE_PATH}",
                json={
                    "pin": pin,
                    "host": local_url,
                    "token": token,
                    "mqtt_topic_prefix": self._mqtt_topic_prefix,
                    "register_companion_app": self._register_companion_app,
                    "companion_device_name": self._companion_device_name,
                },
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status == 403:
                    return {"base": ERROR_INVALID_PIN}
                resp.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Could not complete pairing with %s:%s: %s", self._host, self._port, err)
            return {"base": ERROR_CANNOT_CONNECT}

        return {}

    async def _async_mint_token(self) -> str:
        """Create a Long-Lived Access Token for the instance owner, for this TV to use.

        Mirrors exactly what Home Assistant's own "auth/long_lived_access_token" WebSocket
        command does for a token created by hand via the profile page (see
        homeassistant/components/auth/__init__.py) — a refresh token of the long-lived type,
        then an access token string derived from it. There's no "current user" available
        inside a config flow (only the frontend's live WebSocket connection carries that), so
        this attributes the token to the instance's owner account instead — config flows are
        already admin-only (see Home Assistant's own @require_admin guard on starting one),
        so that's the same trust level the person completing this flow already has.
        """
        owner = await self.hass.auth.async_get_owner()
        if owner is None:
            raise ValueError("This Home Assistant instance has no owner account")

        client_name = f"Egret NVR TV ({self._device_id})"

        # Re-pairing the same TV (e.g. after a factory reset or reinstall) would otherwise hit
        # "{client_name} already exists" the second time around — revoke the old token first
        # so re-pairing cleanly replaces it instead of failing, and so Home Assistant's own
        # token list doesn't accumulate stale entries for the same TV.
        for existing in list(owner.refresh_tokens.values()):
            if (
                existing.client_name == client_name
                and existing.token_type == TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
            ):
                self.hass.auth.async_remove_refresh_token(existing)

        refresh_token = await self.hass.auth.async_create_refresh_token(
            owner,
            client_name=client_name,
            token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
            access_token_expiration=timedelta(days=ACCESS_TOKEN_LIFESPAN_DAYS),
        )
        return self.hass.auth.async_create_access_token(refresh_token)
