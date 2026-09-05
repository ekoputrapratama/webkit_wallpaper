import json
import logging
import os

logger = logging.getLogger(__name__)

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
    "auto_pause": True,
}


def ensure_config_dir():
    logger.debug("ensure_config_dir() dir=%s", CONFIG_DIR)
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load():
    logger.debug("load() called")
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        logger.debug("load() reading config from %s", CONFIG_FILE)
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
            merged = {**DEFAULT_CONFIG, **saved}
            logger.debug("load() loaded config keys=%s", list(merged.keys()))
            return merged
    logger.debug("load() no config file found, returning defaults")
    return dict(DEFAULT_CONFIG)


def save(config):
    logger.debug("save() called with keys=%s", list(config.keys()))
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    logger.debug("save() config written to %s", CONFIG_FILE)


def update(key, value):
    logger.debug("update(key=%s, value=%s)", key, value)
    config = load()
    config[key] = value
    save(config)
    logger.debug("update() done, config now has %d keys", len(config))
    return config
