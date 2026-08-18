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

# Whether the TV should subscribe to Frigate's frigate/events MQTT topic directly over the
# Home Assistant websocket, instead of (or in addition to — though enabling both shows every
# event twice) a "Notifications for Android TV" blueprint push. Same choice the TV's own
# setup wizard and Home Assistant settings card already offer; collected here so pairing
# doesn't leave it at whatever it happened to default to.
CONF_SUBSCRIBE_TO_FRIGATE_EVENTS = "subscribe_to_frigate_events"
DEFAULT_SUBSCRIBE_TO_FRIGATE_EVENTS = True

# Alert appearance — mirrors the TV's own "Alert Configuration" card/wizard step
# (NotificationConfigDialog.java, NotificationDefaultsPreferences.java). Label strings match
# that dialog's own option text exactly; the TV side maps them back to its internal
# position/size integer encoding (see NotificationHttpServer's own POSITION_VALUES/SIZE_VALUES
# lookup, kept in sync with OverlayController's gravityFor()/textSizeSp()).
CONF_ALERT_POSITION = "alert_position"
ALERT_POSITION_OPTIONS = ["Bottom Right", "Bottom Left", "Top Right", "Top Left"]
DEFAULT_ALERT_POSITION = "Bottom Right"

CONF_ALERT_SIZE = "alert_size"
ALERT_SIZE_OPTIONS = ["Small", "Medium", "Large", "Max"]
DEFAULT_ALERT_SIZE = "Medium"

CONF_ALERT_DURATION_SECONDS = "alert_duration_seconds"
ALERT_DURATION_OPTIONS = [10, 15, 20, 25, 30]
DEFAULT_ALERT_DURATION_SECONDS = 20

# Whether a clip plays inline (muted) right in the alert popup, vs. just a snapshot + play
# icon that opens the full-screen player on demand.
CONF_PLAY_CLIPS_INLINE = "play_clips_inline"
DEFAULT_PLAY_CLIPS_INLINE = False

# History — mirrors HistoryPreferences.java. Saving *every* notification (rather than only
# ones carrying a stable "[[id=...]]"/event id) is off by default on the TV itself; exposed
# here so it doesn't need a follow-up trip to Settings after pairing.
CONF_SAVE_ALL_NOTIFICATIONS = "save_all_notifications"
DEFAULT_SAVE_ALL_NOTIFICATIONS = False

CONF_HISTORY_SIZE = "history_size"
HISTORY_SIZE_OPTIONS = [100, 250, 500, 750, 1000]
DEFAULT_HISTORY_SIZE = 100

# TV-side HTTP routes (NotificationHttpServer.java), reached over plain HTTP on the local
# network — see that file's own doc comment for the two-step start/complete exchange.
PAIR_START_PATH = "/ha_pair/start"
PAIR_COMPLETE_PATH = "/ha_pair/complete"

REQUEST_TIMEOUT_SECONDS = 10

# Long-Lived Access Tokens are meant to be effectively permanent (Home Assistant's own
# profile UI defaults to the same span) — the TV persists this token indefinitely once
# paired, same as one a user would have pasted in by hand.
ACCESS_TOKEN_LIFESPAN_DAYS = 3650
