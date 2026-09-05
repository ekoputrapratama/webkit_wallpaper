import logging
import os
import urllib.parse

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, Gtk

from webkit_wallpaper import themes
from webkit_wallpaper.wallpaper_window import get_monitor_list

logger = logging.getLogger(__name__)

THUMB_SIZE = 48


def _load_thumbnail(path, size=THUMB_SIZE):
    logger.debug("_load_thumbnail(path=%s, size=%d)", path, size)
    if not path or not os.path.isfile(path):
        logger.debug("_load_thumbnail() -> None (invalid path)")
        return None
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
        logger.debug("_load_thumbnail() -> loaded %dx%d", pixbuf.get_width(), pixbuf.get_height())
        return pixbuf
    except Exception as e:
        logger.debug("_load_thumbnail() exception: %s", e)
        return None


def _make_fallback_icon(size=THUMB_SIZE):
    logger.debug("_make_fallback_icon(size=%d)", size)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(0.3, 0.3, 0.4)
    ctx.rectangle(0, 0, size, size)
    ctx.fill()
    ctx.set_source_rgb(0.6, 0.6, 0.7)
    ctx.set_font_size(20)
    ctx.move_to(size / 2 - 6, size / 2 + 7)
    ctx.show_text("W")
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)


import cairo


class SettingsDialog(Gtk.Window):
    def __init__(self, app):
        logger.debug("SettingsDialog.__init__() called")
        super().__init__(title="WebKit Wallpaper Settings")
        self.app = app
        self.set_default_size(560, 480)
        self.set_resizable(True)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_keep_above(True)

        self.connect("delete-event", self._on_close)
        self.connect("destroy", self._on_close)

        self._themes = []
        self._build_ui()
        self._setup_dnd()
        logger.debug("SettingsDialog.__init__() done")

    def _build_ui(self):
        logger.debug("SettingsDialog._build_ui() called")
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        self.add(vbox)

        # URL row
        url_frame = Gtk.Frame(label="Web URL")
        vbox.pack_start(url_frame, False, False, 0)

        url_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        url_box.set_margin_start(8)
        url_box.set_margin_end(8)
        url_box.set_margin_top(6)
        url_box.set_margin_bottom(6)
        url_frame.add(url_box)

        self.url_entry = Gtk.Entry()
        self.url_entry.set_hexpand(True)
        self.url_entry.set_placeholder_text("https://example.com")
        self.url_entry.set_text(self.app.config.get("url", ""))
        self.url_entry.connect("activate", self._on_load_url)
        url_box.pack_start(self.url_entry, True, True, 0)

        self.load_button = Gtk.Button(label="Load")
        self.load_button.connect("clicked", self._on_load_url)
        url_box.pack_start(self.load_button, False, False, 0)

        # Display selection
        display_frame = Gtk.Frame(label="Display")
        vbox.pack_start(display_frame, False, False, 0)

        display_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        display_box.set_margin_start(8)
        display_box.set_margin_end(8)
        display_box.set_margin_top(6)
        display_box.set_margin_bottom(6)
        display_frame.add(display_box)

        self._monitors = get_monitor_list()
        self.monitor_combo = Gtk.ComboBoxText()
        self.monitor_combo.connect("changed", self._on_monitor_changed)
        self._fill_monitor_combo()

        display_box.pack_start(self.monitor_combo, True, True, 0)

        # Themes section
        theme_frame = Gtk.Frame(label="Themes — drop .zip to install")
        vbox.pack_start(theme_frame, True, True, 0)

        self.theme_list = Gtk.ListBox()
        self.theme_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.theme_list.connect("row-activated", self._on_theme_selected)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(200)
        scroll.add(self.theme_list)
        theme_frame.add(scroll)

        self._populate_themes()

        # Settings row
        settings_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        vbox.pack_start(settings_box, False, False, 0)

        self.mute_check = Gtk.CheckButton(label="Mute Audio")
        self.mute_check.set_active(self.app.config.get("mute_audio", True))
        self.mute_check.connect("toggled", self._on_mute_toggled)
        settings_box.pack_start(self.mute_check, False, False, 0)

        self.hwaccel_check = Gtk.CheckButton(label="Hardware Acceleration")
        self.hwaccel_check.set_active(self.app.config.get("hardware_accel", True))
        self.hwaccel_check.connect("toggled", self._on_hwaccel_toggled)
        settings_box.pack_start(self.hwaccel_check, False, False, 0)

        self.autopause_check = Gtk.CheckButton(
            label="Auto-pause on fullscreen")
        self.autopause_check.set_active(self.app.config.get("auto_pause", True))
        self.autopause_check.connect("toggled", self._on_autopause_toggled)
        settings_box.pack_start(self.autopause_check, False, False, 0)

        self.fps_values = [0, 60, 30, 24, 15]
        self.fps_combo = Gtk.ComboBoxText()
        for label in ["FPS: Uncapped", "FPS: 60", "FPS: 30", "FPS: 24", "FPS: 15"]:
            self.fps_combo.append_text(label)
        saved_fps = int(self.app.config.get("fps_cap", 0) or 0)
        if saved_fps in self.fps_values:
            self.fps_combo.set_active(self.fps_values.index(saved_fps))
        else:
            self.fps_combo.set_active(0)
        self.fps_combo.connect("changed", self._on_fps_changed)
        settings_box.pack_start(self.fps_combo, False, False, 0)

        # Status + close
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vbox.pack_start(bottom_box, False, False, 0)

        self.status_label = Gtk.Label()
        self.status_label.set_xalign(0)
        self.status_label.set_ellipsize(3)
        self.status_label.set_hexpand(True)
        self._update_status()
        bottom_box.pack_start(self.status_label, True, True, 0)

        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", self._on_close)
        bottom_box.pack_end(close_button, False, False, 0)

        store_button = Gtk.Button(label="Open Store")
        store_button.connect("clicked", self._on_open_store)
        bottom_box.pack_end(store_button, False, False, 0)
        logger.debug("SettingsDialog._build_ui() done")

    def _populate_themes(self):
        logger.debug("SettingsDialog._populate_themes() called")
        for child in self.theme_list.get_children():
            self.theme_list.remove(child)

        self._themes = themes.scan_themes()
        active_theme = self.app.config.get("active_theme", "")

        if not self._themes:
            logger.debug("SettingsDialog._populate_themes() no themes found, showing placeholder")
            row = Gtk.ListBoxRow()
            row.set_selectable(False)
            label = Gtk.Label(label="No themes found. Drop a .zip above to install.")
            label.set_margin_start(8)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_opacity(0.5)
            row.add(label)
            self.theme_list.add(row)
            return

        for i, theme in enumerate(self._themes):
            row = self._make_theme_row(theme)
            if theme["id"] == active_theme:
                self.theme_list.select_row(row)
            self.theme_list.add(row)

        self.theme_list.show_all()
        logger.debug("SettingsDialog._populate_themes() added %d theme rows", len(self._themes))

    def _make_theme_row(self, theme):
        logger.debug("SettingsDialog._make_theme_row(theme=%s)", theme.get("id", "unknown"))
        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_start(6)
        hbox.set_margin_end(6)
        hbox.set_margin_top(6)
        hbox.set_margin_bottom(6)

        # Thumbnail
        thumb = _load_thumbnail(theme.get("thumbnail_path", ""))
        if thumb is None:
            thumb = _make_fallback_icon()
        image = Gtk.Image.new_from_pixbuf(thumb)
        hbox.pack_start(image, False, False, 0)

        # Info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_label = Gtk.Label(xalign=0)
        name_label.set_markup(f"<b>{theme['name']}</b>")
        info_box.pack_start(name_label, False, False, 0)

        desc_text = theme.get("description", "")
        if theme.get("author"):
            desc_text += f"  —  by {theme['author']}"
        desc_label = Gtk.Label(label=desc_text, xalign=0)
        desc_label.set_ellipsize(3)
        desc_label.set_opacity(0.6)
        info_box.pack_start(desc_label, False, False, 0)

        source = "user" if theme.get("user") else "system"
        source_label = Gtk.Label(label=f"[{source}]", xalign=0)
        source_label.set_opacity(0.4)
        source_label.set_margin_top(2)
        info_box.pack_start(source_label, False, False, 0)

        hbox.pack_start(info_box, True, True, 0)

        row.add(hbox)
        row._theme_id = theme["id"]
        return row

    def _setup_dnd(self):
        logger.debug("SettingsDialog._setup_dnd() called")
        targets = [Gtk.TargetEntry.new("text/uri-list", 0, 0)]
        self.theme_list.drag_dest_set(
            Gtk.DestDefaults.ALL, targets, Gdk.DragAction.COPY
        )
        self.theme_list.connect("drag-data-received", self._on_drag_data_received)

    def _on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        uris = data.get_uris()
        logger.debug("SettingsDialog._on_drag_data_received() uris=%s", uris)
        if not uris:
            return

        for uri in uris:
            parsed = urllib.parse.urlparse(uri)
            path = urllib.parse.unquote(parsed.path)
            if not path.lower().endswith(".zip"):
                logger.debug("SettingsDialog._on_drag_data_received() skipping non-zip: %s", path)
                continue
            self._install_zip(path)

        Gtk.drag_finish(drag_context, True, False, time)

    def _install_zip(self, zip_path):
        logger.debug("SettingsDialog._install_zip(zip_path=%s)", zip_path)
        meta, error = themes.install_theme(zip_path)
        if error:
            logger.warning("SettingsDialog._install_zip() install failed: %s", error)
            self.status_label.set_text(f"Install failed: {error}")
            return
        logger.debug("SettingsDialog._install_zip() installed: %s", meta["name"])
        self.status_label.set_text(f"Installed: {meta['name']}")
        self._populate_themes()

    def _on_theme_selected(self, listbox, row):
        if row is None:
            return
        theme_id = getattr(row, "_theme_id", None)
        if theme_id:
            logger.debug("SettingsDialog._on_theme_selected(theme_id=%s)", theme_id)
            self.app.wallpaper.load_theme(theme_id)
            self._update_status()

    def _on_load_url(self, *_args):
        url = self.url_entry.get_text().strip()
        logger.debug("SettingsDialog._on_load_url(url=%s)", url)
        self.app.wallpaper.load_url(url)
        self._update_status()

    def _on_mute_toggled(self, check):
        active = check.get_active()
        logger.debug("SettingsDialog._on_mute_toggled(active=%s)", active)
        self.app.wallpaper.set_muted(active)

    def _on_hwaccel_toggled(self, check):
        active = check.get_active()
        logger.debug("SettingsDialog._on_hwaccel_toggled(active=%s)", active)
        self.app.wallpaper.set_hardware_accel(active)

    def _on_autopause_toggled(self, check):
        active = check.get_active()
        logger.debug("SettingsDialog._on_autopause_toggled(active=%s)", active)
        self.app.set_auto_pause(active)

    def _on_fps_changed(self, combo):
        active = combo.get_active()
        if 0 <= active < len(self.fps_values):
            fps = self.fps_values[active]
            logger.debug("SettingsDialog._on_fps_changed(fps=%d)", fps)
            self.app.wallpaper.set_fps_cap(fps)

    def _fill_monitor_combo(self):
        logger.debug("SettingsDialog._fill_monitor_combo() called")
        self.monitor_combo.handler_block_by_func(self._on_monitor_changed)
        try:
            self.monitor_combo.remove_all()
            self.monitor_combo.append_text("Default")
            for mon in self._monitors:
                self.monitor_combo.append_text(mon["label"])

            active = 0
            saved_id = self.app.config.get("monitor_id", "") or ""
            if saved_id:
                for i, mon in enumerate(self._monitors):
                    if mon["id"] == saved_id:
                        active = i + 1
                        break
            else:
                legacy = int(self.app.config.get("monitor", -1) or -1)
                if 0 <= legacy < len(self._monitors):
                    active = legacy + 1
            self.monitor_combo.set_active(active)
            logger.debug("SettingsDialog._fill_monitor_combo() selected index=%d", active)
        finally:
            self.monitor_combo.handler_unblock_by_func(self._on_monitor_changed)

    def _on_monitor_changed(self, combo):
        active = combo.get_active()
        if active <= 0:
            monitor_index = -1
        else:
            monitor_index = active - 1
        logger.debug("SettingsDialog._on_monitor_changed(combo_active=%d, monitor_index=%d)", active, monitor_index)
        self.app.wallpaper.set_monitor(monitor_index)

    def _update_status(self):
        active_theme = self.app.config.get("active_theme", "")
        url = self.app.config.get("url", "")
        if active_theme:
            self.status_label.set_text(f"Active theme: {active_theme}")
        elif url:
            self.status_label.set_text(f"Loaded: {url}")
        else:
            self.status_label.set_text("No URL set — showing fallback animation")

    def _on_close(self, *_args):
        logger.debug("SettingsDialog._on_close()")
        self.hide()
        return True

    def _on_open_store(self, *_args):
        logger.debug("SettingsDialog._on_open_store()")
        self.app.show_store()

    def present(self):
        logger.debug("SettingsDialog.present() called")
        self.url_entry.set_text(self.app.config.get("url", ""))
        self._populate_themes()
        self._refresh_monitor_combo()
        self._update_status()
        self.show_all()
        super().present()

    def _refresh_monitor_combo(self):
        logger.debug("SettingsDialog._refresh_monitor_combo()")
        self._monitors = get_monitor_list()
        self._fill_monitor_combo()
