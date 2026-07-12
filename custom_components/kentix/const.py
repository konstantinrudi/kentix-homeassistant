"""Constants for the Kentix integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "kentix"
NAME = "Kentix"

CONF_API_TOKEN = "api_token"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_WEBHOOK_ID = "webhook_id"
CONF_MANAGE_WEBHOOK = "manage_webhook"

DEFAULT_VERIFY_SSL = False
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MANAGE_WEBHOOK = True
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
INVENTORY_REFRESH_INTERVAL = timedelta(hours=4)
WEBHOOK_SYNC_INTERVAL = timedelta(hours=4)

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

ATTR_RAW_STATE = "raw_state"
ATTR_LAST_CHANGED_BY = "last_changed_by"
ATTR_OBJECT_ID = "object_id"
ATTR_OBJECT_NAME = "object_name"
ATTR_PREVIOUS_STATE = "previous_state"
ATTR_NEW_STATE = "new_state"
ATTR_ENTRY_ID = "entry_id"
ATTR_EVENT_ID = "event_id"
ATTR_EVENT_TYPE = "event_type"

EVENT_KENTIX_ALARM_CHANGED = "kentix_alarm_changed"
EVENT_KENTIX_DOOR_CHANGED = "kentix_door_changed"
EVENT_KENTIX_DOOR_OPENED = "kentix_door_opened"
EVENT_KENTIX_WEBHOOK_RECEIVED = "kentix_webhook_received"

KENTIX_WEBHOOK_NAME_PREFIX = "Home Assistant Kentix"
KENTIX_WEBHOOK_EVENT_ALL_ALARMS = 0
KENTIX_WEBHOOK_EVENT_SYSTEM_ALARMS = 5
KENTIX_WEBHOOK_EVENT_SWITCH_COMPLETE = 50
