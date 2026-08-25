"""Settings persistence — Kivy Config for cross-platform storage (PC/Android)."""

from kivy.config import Config


def get_car_ip():
    """Return configured car IP, fallback to default."""
    if not Config.has_section("xtrap"):
        return "192.168.1.226"
    return Config.get("xtrap", "car_ip") or "192.168.1.226"


def set_car_ip(ip: str):
    """Save car IP to persistent config."""
    if not ip:
        raise ValueError("IP cannot be empty")
    if not Config.has_section("xtrap"):
        Config.add_section("xtrap")
    Config.set("xtrap", "car_ip", ip)
    Config.write()
