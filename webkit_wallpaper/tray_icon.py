import os

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import GLib

BACKEND = None


def _silence_legacy_warnings():
    def _drop(*_args):
        pass

    GLib.log_set_handler(
        "libayatana-appindicator",
        GLib.LogLevelFlags.LEVEL_WARNING,
        _drop,
    )


if os.environ.get("WEBKIT_WALLPAPER_TRAY_BACKEND", "").lower() != "glib":
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator3

        BACKEND = "gtk"
        _silence_legacy_warnings()
    except (ValueError, ImportError):
        try:
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3

            BACKEND = "gtk"
            _silence_legacy_warnings()
        except (ValueError, ImportError):
            pass

if BACKEND is None:
    gi.require_version("AyatanaAppIndicatorGlib", "2.0")
    from gi.repository import AyatanaAppIndicatorGlib as AppIndicator3
    from gi.repository import Gio

    BACKEND = "glib"

from gi.repository import Gtk

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

MENU_ITEMS = [
    ("settings", "Settings"),
    ("store", "Store"),
    ("reload", "Reload"),
    ("devtools", "DevTools"),
]

AUTOSTART_INDEX = len(MENU_ITEMS) + 1


class TrayIcon:
    def __init__(self, app):
        self.app = app
        self._build_indicator()
        if BACKEND == "glib":
            self._build_glib_menu()
        else:
            self._build_gtk_menu()

    def _build_indicator(self):
        icon_path = os.path.join(ASSETS_DIR, "webkit-wallpaper.png")
        icon_name = (
            icon_path
            if os.path.exists(icon_path)
            else "preferences-desktop-wallpaper"
        )
        self.indicator = AppIndicator3.Indicator.new(
            "webkit_wallpaper",
            icon_name,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("WebWallpaper")

    def _add_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", lambda _a, _p, cb=callback: cb())
        self.actions.add_action(action)

    def _build_glib_menu(self):
        self.menu = Gio.Menu.new()
        self.actions = Gio.SimpleActionGroup.new()

        for name, label in MENU_ITEMS:
            self._add_action(name, getattr(self, f"_on_{name}"))
            self.menu.append(label, f"indicator.{name}")

        self.menu.append_section(None, Gio.Menu.new())

        self._add_action("autostart", self._on_autostart_toggle)
        self.menu.insert_item(
            AUTOSTART_INDEX, Gio.MenuItem.new("", "indicator.autostart")
        )

        self.menu.append_section(None, Gio.Menu.new())

        self._add_action("quit", self._on_quit)
        self.menu.append("Quit", "indicator.quit")

        self.indicator.set_menu(self.menu)
        self.indicator.set_actions(self.actions)
        self._sync_autostart_label()

    def _build_gtk_menu(self):
        self.menu = Gtk.Menu()

        self.item_settings = Gtk.MenuItem(label="Settings")
        self.item_settings.connect("activate", self._on_settings)
        self.menu.append(self.item_settings)

        self.item_store = Gtk.MenuItem(label="Store")
        self.item_store.connect("activate", self._on_store)
        self.menu.append(self.item_store)

        self.item_reload = Gtk.MenuItem(label="Reload")
        self.item_reload.connect("activate", self._on_reload)
        self.menu.append(self.item_reload)

        self.item_devtools = Gtk.MenuItem(label="DevTools")
        self.item_devtools.connect("activate", self._on_devtools)
        self.menu.append(self.item_devtools)

        self.menu.append(Gtk.SeparatorMenuItem())

        self.item_autostart = Gtk.MenuItem(label="Enable Autostart")
        self.item_autostart.connect("activate", self._on_autostart_toggle)
        self.menu.append(self.item_autostart)

        self.menu.append(Gtk.SeparatorMenuItem())

        self.item_quit = Gtk.MenuItem(label="Quit")
        self.item_quit.connect("activate", self._on_quit)
        self.menu.append(self.item_quit)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)
        self._sync_autostart_label()

    def _sync_autostart_label(self):
        enabled = self.app.config.get("autostart_enabled", False)
        label = "Disable Autostart" if enabled else "Enable Autostart"
        if BACKEND == "glib":
            self.menu.remove(AUTOSTART_INDEX)
            self.menu.insert_item(
                AUTOSTART_INDEX, Gio.MenuItem.new(label, "indicator.autostart")
            )
        else:
            self.item_autostart.set_label(label)

    def _on_settings(self, *_args):
        self.app.show_settings()

    def _on_store(self, *_args):
        self.app.show_store()

    def _on_reload(self, *_args):
        self.app.wallpaper.reload()

    def _on_devtools(self, *_args):
        self.app.wallpaper.show_devtools()

    def _on_autostart_toggle(self, *_args):
        self.app.toggle_autostart()
        self._sync_autostart_label()

    def _on_quit(self, *_args):
        self.app.quit()
