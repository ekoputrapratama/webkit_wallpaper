import logging
import os
import sys

logger = logging.getLogger(__name__)

AUTOSTART_DIR = os.path.join(os.path.expanduser("~"), ".config", "autostart")
DESKTOP_FILE = os.path.join(AUTOSTART_DIR, "webkit_wallpaper.desktop")

DESKTOP_CONTENT = """\
[Desktop Entry]
Type=Application
Name=WebWallpaper
Comment=Web-based desktop wallpaper
Exec={exec_path}
Icon=preferences-desktop-wallpaper
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""


def _exec_path():
    path = os.path.abspath(sys.argv[0])
    logger.debug("_exec_path() -> %s", path)
    return path


def is_enabled():
    enabled = os.path.exists(DESKTOP_FILE)
    logger.debug("is_enabled() -> %s (file=%s)", enabled, DESKTOP_FILE)
    return enabled


def enable():
    logger.debug("enable() creating autostart desktop file at %s", DESKTOP_FILE)
    os.makedirs(AUTOSTART_DIR, exist_ok=True)
    content = DESKTOP_CONTENT.format(exec_path=_exec_path())
    with open(DESKTOP_FILE, "w") as f:
        f.write(content)
    logger.debug("enable() done")


def disable():
    logger.debug("disable() removing autostart desktop file")
    if os.path.exists(DESKTOP_FILE):
        os.remove(DESKTOP_FILE)
        logger.debug("disable() removed %s", DESKTOP_FILE)
    else:
        logger.debug("disable() file does not exist, nothing to remove")


def toggle():
    logger.debug("toggle() called")
    if is_enabled():
        disable()
    else:
        enable()
    result = is_enabled()
    logger.debug("toggle() finished, autostart_enabled=%s", result)
    return result
