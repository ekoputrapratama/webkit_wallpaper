import os

import gi

from webkit_wallpaper import config as config_store

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2

HAS_LAYER_SHELL = False
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell

    HAS_LAYER_SHELL = True
except (ValueError, ImportError):
    pass


def is_wayland():
    return os.environ.get("XDG_SESSION_TYPE") == "wayland"


def has_layer_shell_support():
    if not HAS_LAYER_SHELL:
        return False
    if not is_wayland():
        return False
    if is_gnome():
        return False
    return True


def is_gnome():
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    return "gnome" in desktop


FPS_CAP_SCRIPT = """(function() {
  if (window.__wwRafCapped) return;
  window.__wwRafCapped = true;
  var cap = %d;
  if (!cap || cap <= 0) return;
  var interval = 1000 / cap;
  var states = new Map();
  var nativeRAF = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function(cb) {
    return nativeRAF(function retry(timestamp) {
      var now = performance.now();
      var next = states.get(cb) || 0;
      if (now + 1 >= next) {
        if (now - next > interval * 2) {
          next = now;
        }
        states.set(cb, next + interval);
        cb(timestamp);
      } else {
        nativeRAF(retry);
      }
    });
  };
})();"""


FALLBACK_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; }
  body {
    width: 100vw; height: 100vh;
    background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e);
    background-size: 400% 400%;
    animation: gradient 15s ease infinite;
    display: flex; align-items: center; justify-content: center;
    font-family: sans-serif; color: rgba(255,255,255,0.15);
    font-size: 1.2rem;
    user-select: none;
  }
  @keyframes gradient {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
</style>
</head>
<body>
  <div>WebWallpaper — set a URL from the tray menu</div>
</body>
</html>"""


def get_monitor_list():
    display = Gdk.Display.get_default()
    if display is None:
        return []
    monitors = []
    for i in range(display.get_n_monitors()):
        mon = display.get_monitor(i)
        geo = mon.get_geometry()
        name = mon.get_model() or mon.get_connector_type() or f"Monitor {i}"
        plug = ""
        try:
            screen = Gdk.Display.get_default().get_default_screen()
            plug = screen.get_monitor_plug_name(i) or ""
        except Exception:
            pass
        label = name if not plug else f"{name} ({plug})"
        monitors.append({
            "index": i,
            "name": name,
            "plug": plug,
            "label": label,
            "x": geo.x,
            "y": geo.y,
            "width": geo.width,
            "height": geo.height,
        })
    return monitors


class WallpaperWindow(Gtk.Window):
    def __init__(self, config, on_url_change=None):
        super().__init__(title="WebWallpaper")
        self.config = config
        self.on_url_change = on_url_change
        self._paused = False
        self._monitor_index = config.get("monitor", -1)

        self.set_decorated(False)
        self.set_app_paintable(True)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self._setup_platform()
        self._setup_webview()
        self._apply_config()

        self.connect("destroy", Gtk.main_quit)
        self.connect("configure-event", self._on_configure)

    def _setup_platform(self):
        if is_wayland() and has_layer_shell_support():
            try:
                GtkLayerShell.init_for_window(self)
                GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BACKGROUND)
                GtkLayerShell.set_exclusive_zone(self, 0)
                GtkLayerShell.set_keyboard_mode(
                    self, GtkLayerShell.KeyboardMode.NONE
                )
                for edge in [
                    GtkLayerShell.Edge.LEFT,
                    GtkLayerShell.Edge.RIGHT,
                    GtkLayerShell.Edge.TOP,
                    GtkLayerShell.Edge.BOTTOM,
                ]:
                    GtkLayerShell.set_anchor(self, edge, True)
                self._platform = "layer-shell"
                self._apply_layer_shell_monitor()
                print("[WebWallpaper] Using layer-shell (Wayland BACKGROUND layer)")
            except Exception as e:
                print(f"[WebWallpaper] layer-shell init failed: {e}")
                self._setup_x11_fallback()
        else:
            self._setup_x11_fallback()

    def _setup_x11_fallback(self):
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.set_keep_below(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.stick()
        self._platform = "x11" if not is_wayland() else "wayland-fallback"
        self._size_to_screen()
        print(f"[WebWallpaper] Using X11 fallback (platform={self._platform})")

    def _size_to_screen(self):
        screen = self.get_screen()
        display = screen.get_display()
        n_monitors = display.get_n_monitors()
        monitor_idx = self._monitor_index

        if monitor_idx >= 0 and monitor_idx < n_monitors:
            geo = display.get_monitor(monitor_idx).get_geometry()
            x, y, w, h = geo.x, geo.y, geo.width, geo.height
        elif n_monitors > 1:
            x = 0
            y = 0
            w = 0
            h = 0
            for i in range(n_monitors):
                geo = display.get_monitor(i).get_geometry()
                left = min(x, geo.x)
                top = min(y, geo.y)
                right = max(x + w, geo.x + geo.width)
                bottom = max(y + h, geo.y + geo.height)
                x, y, w, h = left, top, right - left, bottom - top
        else:
            geo = display.get_monitor(0).get_geometry()
            x, y, w, h = geo.x, geo.y, geo.width, geo.height
        self.move(x, y)
        self.resize(w, h)

    def _on_configure(self, widget, event):
        if self._platform in ("x11", "wayland-fallback"):
            self._size_to_screen()

    def set_monitor(self, monitor_index):
        self._monitor_index = monitor_index
        self.config["monitor"] = monitor_index
        config_store.save(self.config)
        if self._platform == "layer-shell":
            self._apply_layer_shell_monitor()
        else:
            self._size_to_screen()
            self.queue_resize()

    def _apply_layer_shell_monitor(self):
        if not HAS_LAYER_SHELL:
            return
        display = Gdk.Display.get_default()
        if display is None:
            return
        n_monitors = display.get_n_monitors()
        if self._monitor_index >= 0 and self._monitor_index < n_monitors:
            monitor = display.get_monitor(self._monitor_index)
        else:
            monitor = display.get_monitor(0)
        GtkLayerShell.set_monitor(self, monitor)
        for edge in [
            GtkLayerShell.Edge.LEFT,
            GtkLayerShell.Edge.RIGHT,
            GtkLayerShell.Edge.TOP,
            GtkLayerShell.Edge.BOTTOM,
        ]:
            GtkLayerShell.set_anchor(self, edge, True)

    def _setup_webview(self):
        self.web_view = WebKit2.WebView.new()
        settings = self.web_view.get_settings()
        settings.set_enable_webgl(True)
        settings.set_hardware_acceleration_policy(
            WebKit2.HardwareAccelerationPolicy.ALWAYS
        )
        settings.set_enable_java(False)
        settings.set_enable_plugins(False)
        settings.set_media_playback_requires_user_gesture(False)
        settings.set_enable_developer_extras(True)
        settings.set_enable_write_console_messages_to_stdout(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)

        if not self.config.get("hardware_accel", True):
            settings.set_hardware_acceleration_policy(
                WebKit2.HardwareAccelerationPolicy.NEVER
            )

        self._fps_cap = int(self.config.get("fps_cap", 0) or 0)
        self._apply_fps_cap_script()

        self.web_view.connect("web-process-crashed", self._on_web_crash)
        self.web_view.connect("load-failed", self._on_load_failed)
        self.web_view.connect("load-changed", self._on_load_changed)

        if self.config.get("mute_audio", True):
            self.web_view.set_is_muted(True)

        self.add(self.web_view)

    def _on_web_crash(self, web_view):
        uri = web_view.get_uri()
        GLib.timeout_add(2000, self._reload_uri, uri)
        return True

    def _reload_uri(self, uri):
        if uri and uri != "about:blank":
            self.web_view.load_uri(uri)
        return False

    def _on_load_failed(self, web_view, load_event, error):
        return False

    def _on_load_changed(self, web_view, load_event):
        names = {
            WebKit2.LoadEvent.STARTED: "STARTED",
            WebKit2.LoadEvent.REDIRECTED: "REDIRECTED",
            WebKit2.LoadEvent.COMMITTED: "COMMITTED",
            WebKit2.LoadEvent.FINISHED: "FINISHED",
        }
        tag = names.get(load_event, str(load_event))
        uri = web_view.get_uri() or ""
        print(f"[WebKit LOAD] {tag} -> {uri}")

    def _apply_config(self):
        active_theme = self.config.get("active_theme", "")
        if active_theme:
            self.load_theme(active_theme)
        else:
            url = self.config.get("url", "")
            if url:
                self.web_view.load_uri(url)
            else:
                self.web_view.load_html(FALLBACK_HTML, "file:///")

    def load_url(self, url):
        self.config["url"] = url
        self.config["active_theme"] = ""
        if url:
            self.web_view.load_uri(url)
        else:
            self.web_view.load_html(FALLBACK_HTML, "file:///")

    def load_theme(self, theme_id):
        self.config["active_theme"] = theme_id
        self.config["url"] = ""
        all_themes = themes.scan_themes()
        for t in all_themes:
            if t["id"] == theme_id:
                uri = themes.get_theme_entry_uri(t)
                if uri:
                    self.web_view.load_uri(uri)
                else:
                    self.web_view.load_html(FALLBACK_HTML, "file:///")
                return
        self.web_view.load_html(FALLBACK_HTML, "file:///")

    def set_muted(self, muted):
        self.config["mute_audio"] = muted
        self.web_view.set_is_muted(muted)
        config_store.save(self.config)

    def set_hardware_accel(self, enabled):
        self.config["hardware_accel"] = enabled
        policy = (
            WebKit2.HardwareAccelerationPolicy.ALWAYS
            if enabled
            else WebKit2.HardwareAccelerationPolicy.NEVER
        )
        self.web_view.get_settings().set_hardware_acceleration_policy(policy)
        config_store.save(self.config)

    def set_fps_cap(self, fps):
        self._fps_cap = int(fps or 0)
        self.config["fps_cap"] = self._fps_cap
        self._apply_fps_cap_script()
        self.reload()
        config_store.save(self.config)

    def _apply_fps_cap_script(self):
        manager = self.web_view.get_user_content_manager()
        manager.remove_all_scripts()
        if self._fps_cap > 0:
            script = WebKit2.UserScript.new(
                FPS_CAP_SCRIPT % self._fps_cap,
                WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                WebKit2.UserScriptInjectionTime.START,
            )
            manager.add_script(script)

    def reload(self):
        self.web_view.reload()

    def show_devtools(self):
        inspector = self.web_view.get_inspector()
        if not inspector.is_attached():
            inspector.attach()
        inspector.detach()
        inspector.show()

    def pause(self):
        self._paused = True
        self.web_view.set_is_muted(True)
        self.web_view.run_javascript("document.querySelector('video')?.pause()")

    def resume(self):
        self._paused = False
        if not self.config.get("mute_audio", True):
            self.web_view.set_is_muted(False)
        self.web_view.run_javascript("document.querySelector('video')?.play()")

    def is_paused(self):
        return self._paused


from webkit_wallpaper import themes
