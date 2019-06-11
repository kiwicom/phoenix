def is_pingdom_recovery(data):
    """Determine if this Pingdom alert is of type RECOVERY."""
    return data["current_state"] in ("SUCCESS", "UP")
