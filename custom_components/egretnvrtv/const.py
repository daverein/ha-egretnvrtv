"""Constants for the Egret NVR TV integration."""

DOMAIN = "egretnvrtv"

# Matches the service type the TV app advertises via Android's NsdManager — see
# HaIntegrationAdvertiser.java in the app's own repo.
ZEROCONF_SERVICE_TYPE = "_egretnvrtv._tcp.local."

DEFAULT_PORT = 7676

CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"
DEFAULT_MQTT_TOPIC_PREFIX = "frigate"

# Whether to also register the TV as a Home Assistant "mobile_app" companion device (so it
# shows up as a selectable notify target in blueprints) — the same optional step the TV's own
# setup wizard offers, collected here instead so it's a checkbox instead of on-device typing.
CONF_REGISTER_COMPANION_APP = "register_companion_app"
DEFAULT_REGISTER_COMPANION_APP = True
CONF_COMPANION_DEVICE_NAME = "companion_device_name"

# Mirrors the Android app's own R.string.app_name (its default companion device name when
# none has been set on the TV yet) — kept as a plain constant here since this side has no way
# to read that resource directly; update both if the app's display name ever changes.
DEFAULT_COMPANION_DEVICE_NAME_BASE = "Egret NVR TV"

# TV-side HTTP routes (NotificationHttpServer.java), reached over plain HTTP on the local
# network — see that file's own doc comment for the two-step start/complete exchange.
PAIR_START_PATH = "/ha_pair/start"
PAIR_COMPLETE_PATH = "/ha_pair/complete"

REQUEST_TIMEOUT_SECONDS = 10

# Long-Lived Access Tokens are meant to be effectively permanent (Home Assistant's own
# profile UI defaults to the same span) — the TV persists this token indefinitely once
# paired, same as one a user would have pasted in by hand.
ACCESS_TOKEN_LIFESPAN_DAYS = 3650
