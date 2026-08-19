import os
import shutil
import tempfile
import threading
import urllib.parse
import urllib.request
import zipfile

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from webkit_wallpaper import config as config_mod
from webkit_wallpaper import store
from webkit_wallpaper import themes as themes_mod

THUMB_WIDTH = 240
THUMB_HEIGHT = 140

_STORE_CSS = """
.store-card {
    border-radius: 8px;
    border: 1px solid alpha(@borders, 0.6);
    background-color: shade(@theme_bg_color, 1.02);
    padding: 0px;
    margin: 2px;
}
.store-card:hover {
    border-color: alpha(@selected_bg_color, 0.8);
    background-color: shade(@theme_bg_color, 1.06);
}
.card-thumbnail {
    border-radius: 8px 8px 0 0;
}
.card-info {
    padding: 10px 12px 6px 12px;
}
.card-desc {
    font-size: 0.85em;
    opacity: 0.55;
}
.card-bottom {
    padding: 6px 12px 10px 12px;
}
.card-separator {
    margin: 0px 12px;
    opacity: 0.3;
}
.apply-btn {
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: bold;
    background-color: alpha(@selected_bg_color, 0.85);
    color: @theme_fg_color;
    min-height: 20px;
}
.apply-btn:hover {
    background-color: alpha(@selected_bg_color, 1.0);
}
.apply-btn:disabled {
    opacity: 0.5;
}
.apply-btn-applied {
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: bold;
    background-color: alpha(@success_color, 0.85);
    color: @theme_fg_color;
    min-height: 20px;
}
.donate-btn {
    border-radius: 6px;
    padding: 6px 12px;
    background-image: none;
    background-color: #2196F3;
    color: white;
    min-height: 20px;
}
.donate-btn:hover {
    background-image: none;
    background-color: #1976D2;
}
.donate-btn:backdrop {
    background-image: none;
    background-color: #2196F3;
    color: white;
}
.type-badge {
    font-size: 0.75em;
    font-weight: bold;
    padding: 2px 8px;
    border-radius: 10px;
    background-color: alpha(@theme_fg_color, 0.1);
    opacity: 0.6;
}
"""


def _init_store_css():
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(_STORE_CSS.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def _load_pixbuf_from_url(url, width=THUMB_WIDTH, height=THUMB_HEIGHT):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        loader = GdkPixbuf.PixbufLoader()
        loader.write(data)
        loader.close()
        pixbuf = loader.get_pixbuf()
        return _scale_cover(pixbuf, width, height)
    except Exception:
        return None


def _scale_cover(pixbuf, target_w, target_h):
    src_w = pixbuf.get_width()
    src_h = pixbuf.get_height()
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    scaled = pixbuf.scale_simple(new_w, new_h, GdkPixbuf.InterpType.BILINEAR)
    x = (new_w - target_w) // 2
    y = (new_h - target_h) // 2
    return scaled.new_subpixbuf(x, y, target_w, target_h)


def _make_placeholder(width=THUMB_WIDTH, height=THUMB_HEIGHT):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(0.15, 0.15, 0.2)
    ctx.rectangle(0, 0, width, height)
    ctx.fill()
    ctx.set_source_rgb(0.4, 0.4, 0.5)
    ctx.set_font_size(14)
    ctx.move_to(width / 2 - 20, height / 2 + 5)
    ctx.show_text("No Preview")
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, width, height)


_PLACEHOLDER_PATH = None


def _make_placeholder_path():
    global _PLACEHOLDER_PATH
    if _PLACEHOLDER_PATH and os.path.isfile(_PLACEHOLDER_PATH):
        return _PLACEHOLDER_PATH
    pixbuf = _make_placeholder()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    pixbuf.savev(tmp.name, "png", [], [])
    _PLACEHOLDER_PATH = tmp.name
    return tmp.name


import cairo


def _download_zip(url):
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            shutil.copyfileobj(resp, tmp)
        tmp.close()
        return tmp.name
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        return None


class StoreWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(title="Wallpaper Store")
        self.app = app
        self.set_default_size(860, 640)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self.connect("delete-event", self._on_close)
        self.connect("destroy", self._on_close)

        self._wallpapers = []
        self._filtered = []
        self._build_ui()

    def _build_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_start(12)
        header.set_margin_end(12)
        header.set_margin_top(8)
        header.set_margin_bottom(8)
        vbox.pack_start(header, False, False, 0)

        title = Gtk.Label(xalign=0)
        title.set_markup("<b><big>Wallpaper Store</big></b>")
        header.pack_start(title, True, True, 0)

        self.refresh_button = Gtk.Button(label="Refresh")
        self.refresh_button.connect("clicked", self._on_refresh)
        header.pack_end(self.refresh_button, False, False, 0)

        # Search
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_box.set_margin_start(12)
        search_box.set_margin_end(12)
        search_box.set_margin_bottom(8)
        vbox.pack_start(search_box, False, False, 0)

        search_label = Gtk.Label(label="Search:")
        search_box.pack_start(search_label, False, False, 0)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        search_box.pack_start(self.search_entry, True, True, 0)

        # Grid
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.pack_start(scroll, True, True, 0)

        self.flow = Gtk.FlowBox()
        self.flow.set_homogeneous(True)
        self.flow.set_column_spacing(6)
        self.flow.set_row_spacing(6)
        self.flow.set_margin_start(8)
        self.flow.set_margin_end(8)
        self.flow.set_margin_top(4)
        self.flow.set_margin_bottom(4)
        self.flow.set_valign(Gtk.Align.START)
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self.flow)

        # Status bar
        self.status_bar = Gtk.Label(xalign=0)
        self.status_bar.set_margin_start(12)
        self.status_bar.set_margin_end(12)
        self.status_bar.set_margin_top(4)
        self.status_bar.set_margin_bottom(4)
        self.status_bar.set_opacity(0.6)
        vbox.pack_start(self.status_bar, False, False, 0)

        self._show_placeholder()

    def _show_placeholder(self):
        child = Gtk.FlowBoxChild()
        label = Gtk.Label(label="Open Settings to configure Firebase,\nthen click Refresh to browse wallpapers.")
        label.set_justify(Gtk.Justification.CENTER)
        label.set_opacity(0.4)
        child.add(label)
        self.flow.add(child)
        self.flow.show_all()

    def _clear_grid(self):
        for child in self.flow.get_children():
            self.flow.remove(child)

    def _on_refresh(self, *_args):
        self._clear_grid()
        self.status_bar.set_text("Loading wallpapers...")
        self.refresh_button.set_sensitive(False)

        store.fetch_wallpapers_background(self._on_wallpapers_loaded)

    def _on_wallpapers_loaded(self, wallpapers, error):
        GLib.idle_add(self._apply_results, wallpapers, error)

    def _apply_results(self, wallpapers, error):
        self.refresh_button.set_sensitive(True)
        self._clear_grid()

        if error:
            self.status_bar.set_text(error)
            return

        self._wallpapers = wallpapers
        self._filtered = list(wallpapers)
        self._render_grid()
        self.status_bar.set_text(f"{len(wallpapers)} wallpapers loaded")

    def _on_search_changed(self, entry):
        query = entry.get_text().strip().lower()
        if not query:
            self._filtered = list(self._wallpapers)
        else:
            self._filtered = [
                w
                for w in self._wallpapers
                if query in w.get("name", "").lower()
                or query in w.get("description", "").lower()
                or query in w.get("author", "").lower()
                or any(query in t.lower() for t in w.get("tags", []))
            ]
        self._clear_grid()
        self._render_grid()
        self.status_bar.set_text(f"{len(self._filtered)} results")

    def _render_grid(self):
        if not self._filtered:
            child = Gtk.FlowBoxChild()
            label = Gtk.Label(label="No wallpapers found.")
            label.set_opacity(0.4)
            child.add(label)
            self.flow.add(child)
            self.flow.show_all()
            return

        for wp in self._filtered:
            card = self._make_card(wp)
            self.flow.add(card)
        self.flow.show_all()

    def _make_card(self, wp):
        card = Gtk.FlowBoxChild()
        card._wallpaper = wp
        card.set_valign(Gtk.Align.START)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.get_style_context().add_class("store-card")
        outer.set_hexpand(True)
        card.add(outer)

        # Thumbnail — start with placeholder, load in background
        thumb_url = wp.get("thumbnail_url", "")
        is_gif = thumb_url.lower().endswith(".gif")

        if is_gif:
            anim = GdkPixbuf.PixbufAnimation.new_from_file_at_scale(
                _make_placeholder_path(), THUMB_WIDTH, THUMB_HEIGHT, True
            )
            image = Gtk.Image.new_from_animation(anim)
            image.get_style_context().add_class("card-thumbnail")
            image.set_hexpand(True)
            outer.pack_start(image, False, False, 0)
            if thumb_url:
                threading.Thread(
                    target=self._load_gif_bg, args=(thumb_url, image), daemon=True
                ).start()
        else:
            pixbuf = _make_placeholder()
            thumb_area = Gtk.DrawingArea()
            thumb_area.get_style_context().add_class("card-thumbnail")
            thumb_area.set_hexpand(True)
            thumb_area.set_size_request(-1, THUMB_HEIGHT)
            thumb_area._pixbuf = pixbuf
            thumb_area.connect("draw", self._draw_thumb)
            outer.pack_start(thumb_area, False, False, 0)
            if thumb_url:
                threading.Thread(
                    target=self._load_thumb_bg, args=(thumb_url, thumb_area),
                    daemon=True,
                ).start()

        # Info section
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        info.get_style_context().add_class("card-info")
        outer.pack_start(info, False, False, 0)

        name = Gtk.Label(xalign=0)
        name.set_markup(f"<b>{_escape(wp.get('name', 'Untitled'))}</b>")
        name.set_ellipsize(3)
        name.set_max_width_chars(28)
        info.pack_start(name, False, False, 0)

        author = wp.get("author", "")
        if author:
            author_label = Gtk.Label(label=f"by {author}", xalign=0)
            author_label.set_opacity(0.6)
            author_label.set_ellipsize(3)
            author_label.set_max_width_chars(28)
            info.pack_start(author_label, False, False, 0)

        desc = wp.get("description", "")
        if desc:
            desc_label = Gtk.Label(xalign=0)
            short = desc if len(desc) <= 80 else desc[:77] + "..."
            desc_label.set_text(short)
            desc_label.set_ellipsize(3)
            desc_label.set_max_width_chars(28)
            desc_label.get_style_context().add_class("card-desc")
            info.pack_start(desc_label, False, False, 0)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.get_style_context().add_class("card-separator")
        outer.pack_start(sep, False, False, 0)

        # Bottom row: type badge + apply button
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.get_style_context().add_class("card-bottom")
        outer.pack_start(bottom, False, False, 0)

        wp_type = wp.get("type", "url")
        badge = Gtk.Label(label=wp_type.upper())
        badge.get_style_context().add_class("type-badge")
        bottom.pack_start(badge, False, False, 0)

        donation_url = wp.get("donation_url", "")
        if donation_url:
            donate_label = wp.get("donation_label", "Support Author")
            donate_btn = Gtk.Button(label=donate_label)
            donate_btn.set_relief(Gtk.ReliefStyle.NONE)
            donate_btn.get_style_context().add_class("donate-btn")
            donate_btn.connect("clicked", self._on_donate, donation_url)
            bottom.pack_start(donate_btn, False, False, 0)

        applied = self._is_applied(wp)
        apply_btn = Gtk.Button(label="Applied" if applied else "Apply")
        apply_btn.get_style_context().add_class(
            "apply-btn-applied" if applied else "apply-btn"
        )
        apply_btn.set_hexpand(True)
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.set_sensitive(not applied)
        apply_btn.connect("clicked", self._on_apply, wp)
        card._apply_btn = apply_btn
        bottom.pack_end(apply_btn, True, True, 0)

        return card

    def _load_thumb_bg(self, url, widget):
        pixbuf = _load_pixbuf_from_url(url)
        if pixbuf is None:
            pixbuf = _make_placeholder()
        widget._pixbuf = pixbuf
        GLib.idle_add(widget.queue_draw)

    def _load_gif_bg(self, url, widget):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            tmp = tempfile.NamedTemporaryFile(suffix=".gif", delete=False)
            tmp.write(data)
            tmp.close()
            anim = GdkPixbuf.PixbufAnimation.new_from_file(tmp.name)
            GLib.idle_add(self._set_gif, widget, anim, tmp.name)
        except Exception:
            anim = GdkPixbuf.PixbufAnimation.new_from_file(_make_placeholder_path())
            GLib.idle_add(self._set_gif, widget, anim, None)

    def _set_gif(self, widget, anim, tmp_path):
        widget.set_from_animation(anim)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _draw_thumb(self, widget, cr):
        pb = widget._pixbuf
        alloc = widget.get_allocation()
        w, h = alloc.width, alloc.height
        scale = max(w / pb.get_width(), h / pb.get_height())
        sw = int(pb.get_width() * scale)
        sh = int(pb.get_height() * scale)
        scaled = pb.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)
        Gdk.cairo_set_source_pixbuf(cr, scaled, (w - sw) / 2, (h - sh) / 2)
        cr.paint()
        return False

    def _on_donate(self, button, url):
        import webbrowser
        webbrowser.open(url)

    def _is_applied(self, wp):
        config = self.app.config
        return config.get("applied_store_id", "") == wp.get("id", "")

    def _refresh_card_states(self):
        for child in self.flow.get_children():
            wp = getattr(child, "_wallpaper", None)
            apply_btn = getattr(child, "_apply_btn", None)
            if wp is None or apply_btn is None:
                continue
            applied = self._is_applied(wp)
            if applied:
                apply_btn.set_label("Applied")
                apply_btn.set_sensitive(False)
                apply_btn.get_style_context().add_class("apply-btn-applied")
                apply_btn.get_style_context().remove_class("apply-btn")
            else:
                apply_btn.set_label("Apply")
                apply_btn.set_sensitive(True)
                apply_btn.get_style_context().remove_class("apply-btn-applied")
                apply_btn.get_style_context().add_class("apply-btn")

    def _on_apply(self, button, wp):
        wp_type = wp.get("type", "url")
        url = wp.get("wallpaper_url", "")

        if wp_type == "theme" or url.endswith(".zip"):
            self.status_bar.set_text(f"Downloading: {wp.get('name', '')}...")
            self.apply_button = button
            button.set_sensitive(False)
            threading.Thread(
                target=self._apply_theme_background, args=(wp, url), daemon=True
            ).start()
            return

        if url:
            self.app.wallpaper.load_url(url)

        self.app.config["applied_store_id"] = wp.get("id", "")
        config_mod.save(self.app.config)
        self._refresh_card_states()
        self.status_bar.set_text(f"Applied: {wp.get('name', '')}")

    def _apply_theme_background(self, wp, url):
        zip_path = _download_zip(url)
        if zip_path is None:
            GLib.idle_add(self._apply_theme_done, wp, False, "Download failed")
            return
        try:
            meta, error = themes_mod.install_theme(zip_path)
            if error:
                GLib.idle_add(self._apply_theme_done, wp, False, error)
            else:
                GLib.idle_add(self._apply_theme_done, wp, True, meta["id"])
        except Exception as e:
            GLib.idle_add(self._apply_theme_done, wp, False, str(e))
        finally:
            try:
                os.unlink(zip_path)
            except OSError:
                pass

    def _apply_theme_done(self, wp, success, result):
        if self.apply_button:
            self.apply_button.set_sensitive(True)
        if success:
            self.app.wallpaper.load_theme(result)
            self.app.config["applied_store_id"] = wp.get("id", "")
            config_mod.save(self.app.config)
            self._refresh_card_states()
            self.status_bar.set_text(f"Applied: {wp.get('name', '')}")
        else:
            self.status_bar.set_text(f"Failed: {result}")

    def _on_close(self, *_args):
        self.hide()
        return True

    def present(self):
        self.show_all()
        super().present()
        if not self._wallpapers:
            self._on_refresh()


_init_store_css()


def _escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
