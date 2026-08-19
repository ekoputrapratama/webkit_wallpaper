import os
import sys

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
    return os.path.abspath(sys.argv[0])


def is_enabled():
    return os.path.exists(DESKTOP_FILE)


def enable():
    os.makedirs(AUTOSTART_DIR, exist_ok=True)
    content = DESKTOP_CONTENT.format(exec_path=_exec_path())
    with open(DESKTOP_FILE, "w") as f:
        f.write(content)


def disable():
    if os.path.exists(DESKTOP_FILE):
        os.remove(DESKTOP_FILE)


def toggle():
    if is_enabled():
        disable()
    else:
        enable()
    return is_enabled()
