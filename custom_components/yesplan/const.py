"""Constants for the Yesplan integration."""

DOMAIN = "yesplan"

CONF_BASE_URL = "base_url"
CONF_API_KEY = "api_key"
CONF_LOCATIONS = "locations"
CONF_DAYS_AHEAD = "days_ahead"
CONF_SCAN_INTERVAL = "scan_interval"

# Names (keywords) of the Yesplan custom data fields that hold ticket sales.
# Empty by default: they differ per installation. Capacity is required for ticket data.
CONF_CUSTOM_FIELDS = "custom_fields"
CONF_TICKET_CAPACITY = "ticket_capacity"
CONF_TICKET_SOLD = "ticket_sold"
CONF_TICKET_AVAILABLE = "ticket_available"

DEFAULT_DAYS_AHEAD = 3
DEFAULT_SCAN_INTERVAL = 15  # minutes
