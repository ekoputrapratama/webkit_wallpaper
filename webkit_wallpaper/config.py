import json
import os

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "webkit_wallpaper")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "url": "",
    "active_theme": "",
    "applied_store_id": "",
    "mute_audio": True,
    "hardware_accel": True,
    "fps_cap": 0,
    "autostart_enabled": False,
    "zoom": 1.0,
    "monitor": -1,
    "monitor_id": "",
}


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load():
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
            merged = {**DEFAULT_CONFIG, **saved}
            return merged
    return dict(DEFAULT_CONFIG)


def save(config):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def update(key, value):
    config = load()
    config[key] = value
    save(config)
    return config
