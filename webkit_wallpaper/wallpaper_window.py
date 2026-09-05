import logging
import os

import gi

from webkit_wallpaper import config as config_store

logger = logging.getLogger(__name__)

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
    result = os.environ.get("XDG_SESSION_TYPE") == "wayland"
    logger.debug("is_wayland() -> %s", result)
    return result


def is_gnome():
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    result = "gnome" in desktop
    logger.debug("is_gnome() -> %s (desktop=%r)", result, desktop)
    return result


def is_kde():
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    result = "kde" in desktop
    logger.debug("is_kde() -> %s (desktop=%r)", result, desktop)
    return result


def _backend_preference():
    pref = os.environ.get("WEBKIT_WALLPAPER_BACKEND", "auto").strip().lower()
    logger.debug("_backend_preference() -> %r", pref)
    return pref


def has_layer_shell_support():
    logger.debug("has_layer_shell_support() called")
    pref = _backend_preference()
    if pref == "x11":
        logger.debug("has_layer_shell_support() -> False (pref=x11)")
        return False
    if not HAS_LAYER_SHELL:
        logger.debug("has_layer_shell_support() -> False (HAS_LAYER_SHELL=False)")
        return False
    if not is_wayland():
        logger.debug("has_layer_shell_support() -> False (not wayland)")
        return False
    try:
        if not GtkLayerShell.is_supported():
            logger.debug("has_layer_shell_support() -> False (GtkLayerShell.is_supported()=False)")
            return False
    except (AttributeError, GLib.Error) as e:
        logger.debug("has_layer_shell_support() -> False (exception: %s)", e)
        return False
    if pref == "layer-shell":
        logger.debug("has_layer_shell_support() -> True (pref=layer-shell)")
        return True
    if is_gnome():
        logger.debug("has_layer_shell_support() -> False (gnome mutter no layer-shell)")
        return False
    logger.debug("has_layer_shell_support() -> True")
    return True


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
    logger.debug("get_monitor_list() called")
    display = Gdk.Display.get_default()
    if display is None:
        logger.debug("get_monitor_list() -> [] (no display)")
        return []
    monitors = []
    seen_ids = {}
    for i in range(display.get_n_monitors()):
        mon = display.get_monitor(i)
        geo = mon.get_geometry()
        name = mon.get_model() or f"Monitor {i}"
        plug = ""
        try:
            screen = Gdk.Display.get_default().get_default_screen()
            plug = screen.get_monitor_plug_name(i) or ""
        except Exception:
            pass
        if plug:
            mid = plug
        else:
            try:
                manufacturer = mon.get_manufacturer() or ""
            except Exception:
                manufacturer = ""
            mid = f"{manufacturer} {name}".strip()
        if mid in seen_ids:
            seen_ids[mid] += 1
            mid = f"{mid}#{seen_ids[mid]}"
        else:
            seen_ids[mid] = 0
        label = name if not plug else f"{name} ({plug})"
        monitors.append({
            "index": i,
            "id": mid,
            "name": name,
            "plug": plug,
            "label": label,
            "x": geo.x,
            "y": geo.y,
            "width": geo.width,
            "height": geo.height,
        })
    logger.debug("get_monitor_list() -> %d monitors: %s", len(monitors), [(m["id"], m["label"]) for m in monitors])
    return monitors


class WallpaperWindow(Gtk.Window):

    def __init__(self, config, on_url_change=None):
        logger.debug("WallpaperWindow.__init__() called")
        super().__init__(title="WebWallpaper")
        self.config = config
        self.on_url_change = on_url_change
        self._paused = False
        self._destroyed = False
        self._visibility_watchdog_id = None
        self._display_toggle_attempted = False
        self._gdk_window_monitoring = False
        self._paused = False
        self._resume_waiting = False
        self._capturing_snapshot = False
        self._screenshot_pixbuf = None
        self._monitor_id = config.get("monitor_id", "") or ""
        self._monitor_index = self._resolve_monitor_index()
        if (not self._monitor_id and self._monitor_index >= 0
                and not config.get("monitor_id")):
            monitors = get_monitor_list()
            for m in monitors:
                if m["index"] == self._monitor_index:
                    self._monitor_id = m["id"]
                    config["monitor_id"] = self._monitor_id
                    config_store.save(config)
                    logger.debug(
                        "WallpaperWindow.__init__() migrated monitor_id=%s",
                        self._monitor_id)
                    break

        self.set_decorated(False)
        self.set_app_paintable(True)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self._setup_platform()
        self._setup_webview()
        self._apply_config()

        self.connect("destroy", self._on_destroy)
        self.connect("configure-event", self._on_configure)

        self._connect_display_signals()
        self._schedule_visibility_retry()
        logger.debug("WallpaperWindow.__init__() done")

    def _on_destroy(self, *_args):
        logger.debug("WallpaperWindow._on_destroy() cleaning up timers")
        self._destroyed = True
        self._cancel_all_timers()
        Gtk.main_quit()

    def _cancel_all_timers(self):
        for attr in (
                "_display_retry_id",
                "_visibility_retry_id",
                "_visibility_watchdog_id",
        ):
            tid = getattr(self, attr, None)
            if tid is not None:
                try:
                    GLib.source_remove(tid)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _on_monitors_changed(self, *_args):
        if self._destroyed:
            return False
        logger.debug("WallpaperWindow._on_monitors_changed()")
        if getattr(self, "_monitor_refresh_scheduled", False):
            return False
        self._monitor_refresh_scheduled = True
        GLib.idle_add(self._reapply_monitor)
        return False

    def _connect_display_signals(self):
        logger.debug("WallpaperWindow._connect_display_signals() called")
        display = Gdk.Display.get_default()
        if display is not None:
            display.connect("monitor-added", self._on_monitors_changed)
            display.connect("monitor-removed", self._on_monitors_changed)
            if display.get_n_monitors() > 0:
                logger.debug(
                    "WallpaperWindow._connect_display_signals() display ready with %d monitors",
                    display.get_n_monitors())
                return
        logger.debug(
            "WallpaperWindow._connect_display_signals() display not ready, starting retry timer"
        )
        self._display_retry_id = GLib.timeout_add(500,
                                                  self._retry_display_setup)

    def _retry_display_setup(self):
        if self._destroyed:
            return False
        logger.debug("WallpaperWindow._retry_display_setup() called")
        display = Gdk.Display.get_default()
        if display is None:
            return True
        if display.get_n_monitors() == 0:
            return True
        if hasattr(self, "_display_retry_id"):
            GLib.source_remove(self._display_retry_id)
            del self._display_retry_id
        logger.debug(
            "WallpaperWindow._retry_display_setup() display ready, reapplying monitor"
        )
        self._reapply_monitor()
        return False

    def _schedule_visibility_retry(self):
        logger.debug(
            "WallpaperWindow._schedule_visibility_retry() scheduling retries")
        self._visibility_retry_count = 0
        self._visibility_retry_id = GLib.timeout_add(
            500, self._visibility_retry_tick)

    def _visibility_retry_tick(self):
        if self._destroyed:
            return False
        self._visibility_retry_count += 1
        count = self._visibility_retry_count
        visible = self.is_visible()
        logger.debug(
            "WallpaperWindow._visibility_retry_tick() attempt %d, visible=%s",
            count, visible)
        
        if not visible:
            self.show_all()
            visible = self.is_visible()
            logger.debug(
                "WallpaperWindow._visibility_retry_tick() after show_all, visible=%s",
                visible)
        if count >= 6:
            logger.debug(
                "WallpaperWindow._visibility_retry_tick() initial retries done, switching to watchdog"
            )
            self._visibility_retry_id = None
            if not visible:
                logger.debug(
                    "WallpaperWindow._visibility_retry_tick() still not visible, starting long watchdog"
                )
                self._visibility_watchdog_id = GLib.timeout_add(
                    2000, self._visibility_watchdog_tick)
            return False
        return True

    def _visibility_watchdog_tick(self):
        if self._destroyed:
            return False
        visible = self.is_visible()
        if not visible:
            logger.debug(
                "WallpaperWindow._visibility_watchdog_tick() window not visible, calling show_all()"
            )
            self.show_all()
            visible = self.is_visible()
            if visible:
                logger.debug(
                    "WallpaperWindow._visibility_watchdog_tick() window now visible, stopping watchdog"
                )
                self._visibility_watchdog_id = None
                self._ensure_gdk_window_monitoring()
                return False
            if not getattr(self, "_display_toggle_attempted", False):
                logger.debug(
                    "WallpaperWindow._visibility_watchdog_tick() still not visible, trying display toggle"
                )
                self._display_toggle_attempted = True
                self._try_display_toggle()
                return True
        else:
            logger.debug(
                "WallpaperWindow._visibility_watchdog_tick() window visible, stopping watchdog"
            )
            self._visibility_watchdog_id = None
            self._ensure_gdk_window_monitoring()
            return False
        return True

    def _try_display_toggle(self):
        logger.debug("WallpaperWindow._try_display_toggle() called")
        monitors = get_monitor_list()
        if len(monitors) < 2:
            logger.debug(
                "WallpaperWindow._try_display_toggle() only %d monitor(s), cannot toggle",
                len(monitors))
            self.show_all()
            return
        original_index = self._monitor_index
        if original_index < 0:
            original_index = 0
        alt_index = 1 if original_index == 0 else 0
        logger.debug(
            "WallpaperWindow._try_display_toggle() switching to monitor %d temporarily",
            alt_index)
        self.set_monitor(alt_index)
        self.show_all()
        GLib.timeout_add(500, self._restore_monitor, original_index)

    def _restore_monitor(self, original_index):
        if self._destroyed:
            return False
        logger.debug(
            "WallpaperWindow._restore_monitor(original_index=%d) called",
            original_index)
        self.set_monitor(original_index)
        self.show_all()
        return False

    def _ensure_gdk_window_monitoring(self):
        if getattr(self, "_gdk_window_monitoring", False):
            return
        gdk_win = self.get_window()
        if gdk_win is None:
            logger.debug(
                "WallpaperWindow._ensure_gdk_window_monitoring() no GDK window yet, retrying"
            )
            GLib.timeout_add(1000, self._try_start_gdk_monitoring)
            return
        self._gdk_window_monitoring = True
        logger.debug(
            "WallpaperWindow._ensure_gdk_window_monitoring() connecting state-changed signal"
        )
        gdk_win.connect("state-changed", self._on_gdk_window_state_changed)

    def _try_start_gdk_monitoring(self):
        if self._destroyed:
            return False
        if getattr(self, "_gdk_window_monitoring", False):
            return False
        gdk_win = self.get_window()
        if gdk_win is None:
            return True
        self._gdk_window_monitoring = True
        logger.debug(
            "WallpaperWindow._try_start_gdk_monitoring() connecting state-changed signal"
        )
        gdk_win.connect("state-changed", self._on_gdk_window_state_changed)
        return False

    def _on_gdk_window_state_changed(self, gdk_window, changed_mask):
        if self._destroyed:
            return
        state = gdk_window.get_state()
        is_mapped = bool(state & Gdk.GdkWindowState.MAPPED)
        logger.debug(
            "WallpaperWindow._on_gdk_window_state_changed() state=0x%x mapped=%s",
            state,
            is_mapped,
        )
        if not is_mapped:
            logger.debug(
                "WallpaperWindow._on_gdk_window_state_changed() window unmapped, scheduling re-show"
            )
            GLib.timeout_add(500, self._try_re_show)

    def _try_re_show(self):
        if self._destroyed:
            return False
        visible = self.is_visible()
        logger.debug("WallpaperWindow._try_re_show() visible=%s", visible)
        if not visible:
            self.show_all()
        return False

    def is_visible(self):
        gdk_win = self.get_window()
        if gdk_win is None:
            logger.debug(
                "WallpaperWindow.is_visible() -> False (no GDK window)")
            return False
        visible = gdk_win.is_visible()
        logger.debug("WallpaperWindow.is_visible() -> %s", visible)
        return visible

    def _reapply_monitor(self):
        if self._destroyed:
            return False
        logger.debug("WallpaperWindow._reapply_monitor() called")
        self._monitor_refresh_scheduled = False
        new_index = self._resolve_monitor_index()
        if new_index != self._monitor_index:
            logger.debug(
                "WallpaperWindow._reapply_monitor() monitor index changed: %d -> %d",
                self._monitor_index, new_index)
            self._monitor_index = new_index
        if self._platform == "layer-shell":
            self._apply_layer_shell_monitor()
            self.show_all()
        else:
            self._size_to_screen()
            self.queue_resize()
            if self.get_realized():
                self.show_all()
        return False

    def _resolve_monitor_index(self):
        logger.debug(
            "WallpaperWindow._resolve_monitor_index() called (monitor_id=%r)",
            self._monitor_id)
        monitors = get_monitor_list()
        if not monitors:
            logger.debug(
                "WallpaperWindow._resolve_monitor_index() -> -1 (no monitors)")
            return -1
        if self._monitor_id:
            for m in monitors:
                if m["id"] == self._monitor_id:
                    logger.debug(
                        "WallpaperWindow._resolve_monitor_index() -> %d (matched monitor_id)",
                        m["index"])
                    return m["index"]
            logger.debug(
                "WallpaperWindow._resolve_monitor_index() -> -1 (monitor_id not found)"
            )
            return -1
        legacy = int(self.config.get("monitor", -1) or -1)
        if 0 <= legacy < len(monitors):
            logger.debug(
                "WallpaperWindow._resolve_monitor_index() -> %d (legacy)",
                legacy)
            return legacy
        logger.debug(
            "WallpaperWindow._resolve_monitor_index() -> -1 (no match)")
        return -1

    def _setup_platform(self):
        logger.debug("WallpaperWindow._setup_platform() called")
        if is_wayland() and has_layer_shell_support():
            try:
                GtkLayerShell.init_for_window(self)
                GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BACKGROUND)
                GtkLayerShell.set_exclusive_zone(self, -1)
                GtkLayerShell.set_keyboard_mode(
                    self, GtkLayerShell.KeyboardMode.NONE)
                for edge in [
                        GtkLayerShell.Edge.LEFT,
                        GtkLayerShell.Edge.RIGHT,
                        GtkLayerShell.Edge.TOP,
                        GtkLayerShell.Edge.BOTTOM,
                ]:
                    GtkLayerShell.set_anchor(self, edge, True)
                self._platform = "layer-shell"
                self._apply_layer_shell_monitor()
                logger.info(
                    "WallpaperWindow._setup_platform() Using layer-shell (Wayland BACKGROUND layer)"
                )
            except Exception as e:
                logger.error(
                    "WallpaperWindow._setup_platform() layer-shell init failed: %s",
                    e)
                self._setup_x11_fallback()
        else:
            self._setup_x11_fallback()

    def _setup_x11_fallback(self):
        logger.debug("WallpaperWindow._setup_x11_fallback() called")
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.set_keep_below(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.stick()
        self._platform = "x11" if not is_wayland() else "wayland-fallback"
        self._size_to_screen()
        if is_wayland():
            logger.info(
                "WallpaperWindow._setup_x11_fallback() Using X11 desktop window via XWayland (platform=wayland-fallback)"
            )
        else:
            logger.info(
                "WallpaperWindow._setup_x11_fallback() Using X11 fallback (platform=%s)",
                self._platform)

    def _size_to_screen(self):
        logger.debug(
            "WallpaperWindow._size_to_screen() called (monitor_index=%d)",
            self._monitor_index)
        screen = self.get_screen()
        display = screen.get_display()
        n_monitors = display.get_n_monitors()
        if n_monitors == 0:
            logger.debug(
                "WallpaperWindow._size_to_screen() no monitors, returning")
            return
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
        logger.debug(
            "WallpaperWindow._size_to_screen() geometry: x=%d y=%d w=%d h=%d",
            x, y, w, h)
        self.move(x, y)
        self.resize(w, h)

    def _on_configure(self, widget, event):
        if self._destroyed:
            return False
        if self._platform in ("x11", "wayland-fallback"):
            self._size_to_screen()

    def set_monitor(self, monitor_index):
        logger.debug("WallpaperWindow.set_monitor(monitor_index=%d)",
                     monitor_index)
        monitors = get_monitor_list()
        self._monitor_index = monitor_index
        self._monitor_id = ""
        for m in monitors:
            if m["index"] == monitor_index:
                self._monitor_id = m["id"]
                break
        self.config["monitor"] = monitor_index
        self.config["monitor_id"] = self._monitor_id
        config_store.save(self.config)
        if self._platform == "layer-shell":
            self._apply_layer_shell_monitor()
        else:
            self._size_to_screen()
            self.queue_resize()

    def _apply_layer_shell_monitor(self):
        logger.debug(
            "WallpaperWindow._apply_layer_shell_monitor() called (monitor_index=%d)",
            self._monitor_index)
        if not HAS_LAYER_SHELL:
            return
        display = Gdk.Display.get_default()
        if display is None:
            return
        n_monitors = display.get_n_monitors()
        if 0 <= self._monitor_index < n_monitors:
            monitor = display.get_monitor(self._monitor_index)
        else:
            monitor = None
            for i in range(n_monitors):
                if display.get_monitor(i).is_primary():
                    monitor = display.get_monitor(i)
                    break
            if monitor is None and n_monitors > 0:
                monitor = display.get_monitor(0)
        if monitor is None:
            logger.debug(
                "WallpaperWindow._apply_layer_shell_monitor() no monitor found"
            )
            return
        GtkLayerShell.set_monitor(self, monitor)
        for edge in [
                GtkLayerShell.Edge.LEFT,
                GtkLayerShell.Edge.RIGHT,
                GtkLayerShell.Edge.TOP,
                GtkLayerShell.Edge.BOTTOM,
        ]:
            GtkLayerShell.set_anchor(self, edge, True)
        logger.debug(
            "WallpaperWindow._apply_layer_shell_monitor() applied layer-shell monitor"
        )

    def _setup_webview(self):
        logger.debug("WallpaperWindow._setup_webview() called")
        self.web_view = WebKit2.WebView.new()
        settings = self.web_view.get_settings()
        settings.set_enable_webgl(True)
        settings.set_hardware_acceleration_policy(
            WebKit2.HardwareAccelerationPolicy.ALWAYS)
        settings.set_enable_java(False)
        settings.set_enable_plugins(False)
        settings.set_media_playback_requires_user_gesture(False)
        settings.set_enable_developer_extras(True)
        settings.set_enable_write_console_messages_to_stdout(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)

        if not self.config.get("hardware_accel", True):
            settings.set_hardware_acceleration_policy(
                WebKit2.HardwareAccelerationPolicy.NEVER)

        self._fps_cap = int(self.config.get("fps_cap", 0) or 0)
        logger.debug("WallpaperWindow._setup_webview() fps_cap=%d",
                     self._fps_cap)
        self._apply_fps_cap_script()

        self.web_view.connect("web-process-crashed", self._on_web_crash)
        self.web_view.connect("load-failed", self._on_load_failed)
        self.web_view.connect("load-changed", self._on_load_changed)

        if self.config.get("mute_audio", True):
            self.web_view.set_is_muted(True)

        self._web_area = Gtk.Stack()
        self._web_area.set_transition_type(
            Gtk.StackTransitionType.NONE)
        self._screenshot_image = Gtk.Image()
        self._screenshot_image.set_halign(Gtk.Align.FILL)
        self._screenshot_image.set_valign(Gtk.Align.FILL)
        self._web_area.add_named(self.web_view, "webview")
        self._web_area.add_named(self._screenshot_image, "screenshot")
        self._web_area.set_visible_child_name("webview")
        self.add(self._web_area)
        logger.debug("WallpaperWindow._setup_webview() done")

    def _on_web_crash(self, web_view):
        if self._destroyed:
            return True
        uri = web_view.get_uri()
        logger.warning(
            "WallpaperWindow._on_web_crash() web process crashed, uri=%s, retrying in 2s",
            uri)
        GLib.timeout_add(2000, self._reload_uri, uri)
        return True

    def _reload_uri(self, uri):
        if self._destroyed:
            return False
        logger.debug("WallpaperWindow._reload_uri(uri=%s)", uri)
        if uri and uri != "about:blank":
            self.web_view.load_uri(uri)
        return False

    def _on_load_failed(self, web_view, load_event, error):
        logger.warning(
            "WallpaperWindow._on_load_failed() load_event=%s, error=%s",
            load_event, error)
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
        logger.debug("WallpaperWindow._on_load_changed() %s -> %s", tag, uri)
        if (load_event == WebKit2.LoadEvent.FINISHED
                and getattr(self, "_resume_waiting", False)):
            self._finish_resume()

    def _apply_config(self):
        logger.debug("WallpaperWindow._apply_config() called")
        active_theme = self.config.get("active_theme", "")
        if active_theme:
            logger.debug(
                "WallpaperWindow._apply_config() loading active theme: %s",
                active_theme)
            self.load_theme(active_theme)
        else:
            url = self.config.get("url", "")
            if url:
                logger.debug("WallpaperWindow._apply_config() loading URL: %s",
                             url)
                self.web_view.load_uri(url)
            else:
                logger.debug(
                    "WallpaperWindow._apply_config() loading fallback HTML")
                self.web_view.load_html(FALLBACK_HTML, "file:///")

    def load_url(self, url):
        logger.debug("WallpaperWindow.load_url(url=%s)", url)
        self._exit_pause_state()
        self.config["url"] = url
        self.config["active_theme"] = ""
        if url:
            self.web_view.load_uri(url)
        else:
            self.web_view.load_html(FALLBACK_HTML, "file:///")

    def load_theme(self, theme_id):
        logger.debug("WallpaperWindow.load_theme(theme_id=%s)", theme_id)
        self._exit_pause_state()
        self.config["active_theme"] = theme_id
        self.config["url"] = ""
        all_themes = themes.scan_themes()
        for t in all_themes:
            if t["id"] == theme_id:
                uri = themes.get_theme_entry_uri(t)
                if uri:
                    logger.debug(
                        "WallpaperWindow.load_theme() loading theme URI: %s",
                        uri)
                    self.web_view.load_uri(uri)
                else:
                    logger.debug(
                        "WallpaperWindow.load_theme() no URI for theme, loading fallback"
                    )
                    self.web_view.load_html(FALLBACK_HTML, "file:///")
                return
        logger.warning(
            "WallpaperWindow.load_theme() theme_id=%s not found in scanned themes",
            theme_id)
        self.web_view.load_html(FALLBACK_HTML, "file:///")

    def set_muted(self, muted):
        logger.debug("WallpaperWindow.set_muted(muted=%s)", muted)
        self.config["mute_audio"] = muted
        self.web_view.set_is_muted(muted)
        config_store.save(self.config)

    def set_hardware_accel(self, enabled):
        logger.debug("WallpaperWindow.set_hardware_accel(enabled=%s)", enabled)
        self.config["hardware_accel"] = enabled
        policy = (WebKit2.HardwareAccelerationPolicy.ALWAYS
                  if enabled else WebKit2.HardwareAccelerationPolicy.NEVER)
        self.web_view.get_settings().set_hardware_acceleration_policy(policy)
        config_store.save(self.config)

    def set_fps_cap(self, fps):
        logger.debug("WallpaperWindow.set_fps_cap(fps=%s)", fps)
        self._fps_cap = int(fps or 0)
        self.config["fps_cap"] = self._fps_cap
        self._apply_fps_cap_script()
        self.reload()
        config_store.save(self.config)

    def _apply_fps_cap_script(self):
        logger.debug("WallpaperWindow._apply_fps_cap_script() fps_cap=%d",
                     self._fps_cap)
        manager = self.web_view.get_user_content_manager()
        manager.remove_all_scripts()
        if self._fps_cap > 0:
            script = WebKit2.UserScript.new(
                FPS_CAP_SCRIPT % self._fps_cap,
                WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                WebKit2.UserScriptInjectionTime.START,
            )
            manager.add_script(script)
            logger.debug(
                "WallpaperWindow._apply_fps_cap_script() injected fps cap script"
            )

    def reload(self):
        logger.debug("WallpaperWindow.reload()")
        self._exit_pause_state()
        self.web_view.reload()

    def show_devtools(self):
        logger.debug("WallpaperWindow.show_devtools()")
        inspector = self.web_view.get_inspector()
        if not inspector.is_attached():
            inspector.attach()
        inspector.detach()
        inspector.show()

    def pause(self):
        logger.debug("WallpaperWindow.pause()")
        if self._paused:
            return
        self._paused = True
        self._resume_waiting = False
        self.web_view.set_is_muted(True)
        self.web_view.run_javascript(
            "document.querySelector('video')?.pause()")
        self._capture_snapshot()

    def _exit_pause_state(self):
        """Force the webview back in front, dropping any screenshot."""
        dirty = self._paused or self._resume_waiting
        self._paused = False
        self._resume_waiting = False
        if dirty:
            self._web_area.set_visible_child_name("webview")
            self.web_view.show()
            if self._screenshot_pixbuf is not None:
                self._screenshot_pixbuf = None
            self._screenshot_image.clear()
            logger.debug(
                "WallpaperWindow._exit_pause_state() cleared paused screenshot")

    def _capture_snapshot(self):
        if self._capturing_snapshot:
            return
        self._capturing_snapshot = True
        try:
            self.web_view.get_snapshot(
                WebKit2.SnapshotRegion.VISIBLE,
                WebKit2.SnapshotOptions.NONE,
                None,
                self._on_snapshot,
            )
        except Exception as e:
            logger.exception(
                "WallpaperWindow._capture_snapshot() failed: %s", e)
            self._capturing_snapshot = False
            self._show_paused_overlay(None)

    def _on_snapshot(self, web_view, result, user_data=None):
        self._capturing_snapshot = False
        pixbuf = None
        try:
            surface = web_view.get_snapshot_finish(result)
            if surface is not None:
                pixbuf = Gdk.pixbuf_get_from_surface(
                    surface, 0, 0,
                    surface.get_width(), surface.get_height())
        except Exception as e:
            logger.exception("WallpaperWindow._on_snapshot() failed: %s", e)
        self._show_paused_overlay(pixbuf)

    def _show_paused_overlay(self, pixbuf):
        if pixbuf is not None:
            self._screenshot_pixbuf = pixbuf
            self._screenshot_image.set_from_pixbuf(
                self._screenshot_pixbuf)
        self._web_area.set_visible_child_name("screenshot")
        self.web_view.hide()
        logger.debug(
            "WallpaperWindow._show_paused_overlay() screenshot=%s",
            pixbuf is not None)

    def resume(self):
        logger.debug("WallpaperWindow.resume()")
        if not self._paused:
            return
        self._paused = False
        self._resume_waiting = True
        self.web_view.show()
        if not self.config.get("mute_audio", True):
            self.web_view.set_is_muted(False)
        self.web_view.run_javascript(
            "document.querySelector('video')?.play()")
        # Reload behind the screenshot; the screenshot stays visible until
        # the page finishes loading again so we never show a blank screen.
        self.web_view.reload()

    def _finish_resume(self):
        if not self._resume_waiting:
            return
        self._resume_waiting = False
        self._web_area.set_visible_child_name("webview")
        if self._screenshot_pixbuf is not None:
            self._screenshot_pixbuf = None
        self._screenshot_image.clear()
        logger.debug("WallpaperWindow._finish_resume() screenshot cleared")

    def is_paused(self):
        logger.debug("WallpaperWindow.is_paused() -> %s", self._paused)
        return self._paused


from webkit_wallpaper import themes
