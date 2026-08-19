import os

import gi

gi.require_version("Gtk", "3.0")

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

from gi.repository import Gtk

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


class TrayIcon:
    def __init__(self, app):
        self.app = app
        self._build_indicator()
        self._build_menu()

    def _build_indicator(self):
        icon_path = os.path.join(ASSETS_DIR, "webkit-wallpaper.png")
        if os.path.exists(icon_path):
            self.indicator = AppIndicator3.Indicator.new(
                "webkit_wallpaper",
                icon_path,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
            )
        else:
            self.indicator = AppIndicator3.Indicator.new(
                "webkit_wallpaper",
                "preferences-desktop-wallpaper",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
            )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("WebWallpaper")

    def _build_menu(self):
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
        self.item_autostart.set_label(
            "Disable Autostart" if enabled else "Enable Autostart"
        )

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
