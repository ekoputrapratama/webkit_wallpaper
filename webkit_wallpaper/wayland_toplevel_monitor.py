"""Detect fullscreen toplevels on COSMIC Wayland via ctypes/libwayland.

Connects directly to libwayland-client.so.0 and binds the
``zcosmic_toplevel_info_v1`` protocol (version 1) exposed by the COSMIC
compositor.  Version 1 emits a ``toplevel`` event for every open toplevel
window; each handle then reports a ``state`` array containing the
``activated`` and ``fullscreen`` bits.  The wallpaper is paused whenever an
*activated* toplevel is fullscreen, matching the behaviour of the X11 EWMH
monitor.

This avoids a pywayland dependency and works on desktops (like COSMIC) that
do not maintain the EWMH root-window properties used by the X11 monitor.
"""

import ctypes
import itertools
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

logger = logging.getLogger(__name__)

ZCOSMIC_INFO = b"zcosmic_toplevel_info_v1"
ZCOSMIC_HANDLE = b"zcosmic_toplevel_handle_v1"
INFO_VERSION = 1

STATE_MAXIMIZED = 0
STATE_MINIMIZED = 1
STATE_ACTIVATED = 2
STATE_FULLSCREEN = 3
STATE_STICKY = 4

_LIB_NAMES = ("libwayland-client.so.0", "libwayland-client.so")

# ---------------------------------------------------------------------------
# Protocol structs
# ---------------------------------------------------------------------------


class WlInterface(ctypes.Structure):
    pass


WlMessagePointer = ctypes.POINTER(WlInterface)


class WlMessage(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("signature", ctypes.c_char_p),
        ("types", ctypes.POINTER(WlMessagePointer)),
    ]


class WlObject(ctypes.Structure):
    _fields_ = [
        ("interface", ctypes.POINTER(WlInterface)),
        ("implementation", ctypes.c_void_p),
        ("id", ctypes.c_uint32),
    ]


class WlArray(ctypes.Structure):
    _fields_ = [
        ("size", ctypes.c_size_t),
        ("alloc", ctypes.c_size_t),
        ("data", ctypes.c_void_p),
    ]


class WlArgument(ctypes.Union):
    _fields_ = [
        ("i", ctypes.c_int32),
        ("u", ctypes.c_uint32),
        ("f", ctypes.c_int32),
        ("s", ctypes.c_char_p),
        ("o", ctypes.c_void_p),
        ("n", ctypes.c_uint32),
        ("a", ctypes.c_void_p),
        ("h", ctypes.c_int32),
    ]


WlInterface._fields_ = [
    ("name", ctypes.c_char_p),
    ("version", ctypes.c_int),
    ("method_count", ctypes.c_int),
    ("methods", ctypes.POINTER(WlMessage)),
    ("event_count", ctypes.c_int),
    ("events", ctypes.POINTER(WlMessage)),
]


def _build_protocol_definitions():
    """Build the zcosmic_toplevel interface tables used by libwayland."""
    def iface_ptr(struct):
        return ctypes.cast(ctypes.pointer(struct), WlMessagePointer)

    def msg_array(specs):
        return (WlMessage * len(specs))(
            *[WlMessage(b_name, b_sig, types) for b_name, b_sig, types in specs]
        )

    # zcosmic_toplevel_handle_v1 (events indexed by opcode):
    # 0 closed, 1 done, 2 title "s", 3 app_id "s", 4/5 output_enter/leave "o",
    # 6/7 workspace_enter/leave "o", 8 state "a",
    # 9 geometry "oiiii" (since 2), 10/11 ext_workspace_enter/leave "o" (since 3)
    handle_methods = msg_array([(b"destroy", b"", None)])
    handle_events = msg_array([
        (b"closed", b"", None),
        (b"done", b"", None),
        (b"title", b"s", None),
        (b"app_id", b"s", None),
        (b"output_enter", b"o", None),
        (b"output_leave", b"o", None),
        (b"workspace_enter", b"o", None),
        (b"workspace_leave", b"o", None),
        (b"state", b"a", None),
        (b"geometry", b"oiiii", None),
        (b"ext_workspace_enter", b"o", None),
        (b"ext_workspace_leave", b"o", None),
    ])

    handle_interface = WlInterface(
        name=ZCOSMIC_HANDLE,
        version=3,
        method_count=1,
        methods=ctypes.cast(handle_methods, ctypes.POINTER(WlMessage)),
        event_count=len(handle_events),
        events=ctypes.cast(handle_events, ctypes.POINTER(WlMessage)),
    )

    # wl_registry (the standard global registry): methods 0 bind "usun",
    # events 0 global "usu", 1 global_remove "u".  Build it ourselves instead
    # of reading the exported `wl_registry_interface` symbol through
    # ctypes.in_dll(), which returned unstable/misplaced addresses on this
    # system and corrupted the proxies created via wl_proxy_marshal_array_flags.
    registry_methods = msg_array([
        (b"bind", b"usun",
         ctypes.cast(
             (WlMessagePointer * 1)(
                 ctypes.cast(
                     ctypes.pointer(handle_interface), WlMessagePointer)),
             ctypes.POINTER(WlMessagePointer))),
    ])
    registry_events = msg_array([
        (b"global", b"usu", None),
        (b"global_remove", b"u", None),
    ])
    registry_interface = WlInterface(
        name=b"wl_registry",
        version=1,
        method_count=1,
        methods=ctypes.cast(registry_methods, ctypes.POINTER(WlMessage)),
        event_count=len(registry_events),
        events=ctypes.cast(registry_events, ctypes.POINTER(WlMessage)),
    )

    # zcosmic_toplevel_info_v1 (version 1 client):
    # events 0 toplevel "n" (new_id handle), 1 finished "",
    # 2 done "" (since 2, never sent to v1 clients)
    toplevel_types = (WlMessagePointer * 1)(iface_ptr(handle_interface))
    info_methods = msg_array([
        (b"stop", b"", None),
        (b"get_cosmic_toplevel", b"no", None),
    ])
    info_events = msg_array([
        (b"toplevel", b"n",
         ctypes.cast(toplevel_types, ctypes.POINTER(WlMessagePointer))),
        (b"finished", b"", None),
        (b"done", b"", None),
    ])

    info_interface = WlInterface(
        name=ZCOSMIC_INFO,
        version=3,
        method_count=2,
        methods=ctypes.cast(info_methods, ctypes.POINTER(WlMessage)),
        event_count=len(info_events),
        events=ctypes.cast(info_events, ctypes.POINTER(WlMessage)),
    )

    return {
        "registry_interface": registry_interface,
        "handle_interface": handle_interface,
        "info_interface": info_interface,
        "handle_event_count": len(handle_events),
        "info_event_count": len(info_events),
    }


_PROTO = _build_protocol_definitions()

# ---------------------------------------------------------------------------
# Token -> monitor registry (avoids passing/decoding raw Python object
# pointers through the C callbacks).
# ---------------------------------------------------------------------------

_tokens = itertools.count(1)
_REGISTRY = {}


def _recover(data):
    token = data.value if hasattr(data, "value") else int(data)
    return _REGISTRY.get(token)


# ---------------------------------------------------------------------------
# Callback trampolines (recover the monitor from the token, then dispatch)
# ---------------------------------------------------------------------------


def _cb_global(data, _target, name, interface, version):
    mon = _recover(data)
    if mon is not None:
        mon._on_global(name, interface, version)


def _cb_global_remove(data, _target, name):
    mon = _recover(data)
    if mon is not None:
        mon._on_global_remove(name)


def _cb_info_toplevel(data, _target, handle):
    mon = _recover(data)
    if mon is not None:
        mon._on_info_toplevel(handle)


def _cb_info_finished(data, _target):
    mon = _recover(data)
    if mon is not None:
        mon._on_info_finished()


def _cb_info_done(data, _target):
    pass


def _cb_handle_closed(data, target):
    mon = _recover(data)
    if mon is not None:
        mon._on_handle_closed(target)


def _cb_handle_done(data, _target):
    pass


def _cb_handle_title(data, target, title):
    mon = _recover(data)
    if mon is not None:
        mon._on_handle_title(target, title)


def _cb_handle_app_id(data, target, app_id):
    mon = _recover(data)
    if mon is not None:
        mon._on_handle_app_id(target, app_id)


def _cb_handle_state(data, target, state_array):
    mon = _recover(data)
    if mon is not None:
        mon._on_handle_state(target, state_array)


def _cb_other(data, target, *extra):
    pass


def _make_listener(specs):
    """Build a `void (**)(void)` implementation array from CFUNCTYPEs."""
    ptrs = []
    for fn in specs:
        ptrs.append(ctypes.cast(fn, ctypes.c_void_p))
    arr = (ctypes.c_void_p * len(ptrs))(*ptrs)
    return ctypes.cast(arr, ctypes.POINTER(ctypes.c_void_p))


_T = ctypes.c_void_p

_registry_listener = _make_listener([
    ctypes.CFUNCTYPE(None, _T, _T, ctypes.c_uint32, ctypes.c_char_p,
                     ctypes.c_uint32)(_cb_global),
    ctypes.CFUNCTYPE(None, _T, _T, ctypes.c_uint32)(_cb_global_remove),
])

_info_listener = _make_listener([
    ctypes.CFUNCTYPE(None, _T, _T, _T)(_cb_info_toplevel),
    ctypes.CFUNCTYPE(None, _T, _T)(_cb_info_finished),
    ctypes.CFUNCTYPE(None, _T, _T)(_cb_info_done),
])

_handle_listener = _make_listener([
    ctypes.CFUNCTYPE(None, _T, _T)(_cb_handle_closed),
    ctypes.CFUNCTYPE(None, _T, _T)(_cb_handle_done),
    ctypes.CFUNCTYPE(None, _T, _T, ctypes.c_char_p)(_cb_handle_title),
    ctypes.CFUNCTYPE(None, _T, _T, ctypes.c_char_p)(_cb_handle_app_id),
    ctypes.CFUNCTYPE(None, _T, _T, _T)(_cb_other),
    ctypes.CFUNCTYPE(None, _T, _T, _T)(_cb_other),
    ctypes.CFUNCTYPE(None, _T, _T, _T)(_cb_other),
    ctypes.CFUNCTYPE(None, _T, _T, _T)(_cb_other),
    ctypes.CFUNCTYPE(None, _T, _T, ctypes.POINTER(WlArray))(_cb_handle_state),
    ctypes.CFUNCTYPE(None, _T, _T, _T, ctypes.c_int32, ctypes.c_int32,
                     ctypes.c_int32, ctypes.c_int32)(_cb_other),
    ctypes.CFUNCTYPE(None, _T, _T, _T)(_cb_other),
    ctypes.CFUNCTYPE(None, _T, _T, _T)(_cb_other),
])

# ---------------------------------------------------------------------------
# libwayland-client function pointers
# ---------------------------------------------------------------------------


def _load_library():
    for name in _LIB_NAMES:
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    return None


_LIB = _load_library()

if _LIB is not None:
    _API = {
        "connect": _LIB.wl_display_connect,
        "disconnect": _LIB.wl_display_disconnect,
        "roundtrip": _LIB.wl_display_roundtrip,
        "flush": _LIB.wl_display_flush,
        "dispatch_pending": _LIB.wl_display_dispatch_pending,
        "prepare_read": _LIB.wl_display_prepare_read,
        "read_events": _LIB.wl_display_read_events,
        "cancel_read": _LIB.wl_display_cancel_read,
        "get_fd": _LIB.wl_display_get_fd,
        "add_listener": _LIB.wl_proxy_add_listener,
        "marshal_flags": _LIB.wl_proxy_marshal_array_flags,
    }
    _API["connect"].argtypes = [ctypes.c_char_p]
    _API["connect"].restype = ctypes.c_void_p
    _API["disconnect"].argtypes = [ctypes.c_void_p]
    _API["disconnect"].restype = None
    _API["roundtrip"].argtypes = [ctypes.c_void_p]
    _API["roundtrip"].restype = ctypes.c_int
    _API["flush"].argtypes = [ctypes.c_void_p]
    _API["flush"].restype = ctypes.c_int
    _API["dispatch_pending"].argtypes = [ctypes.c_void_p]
    _API["dispatch_pending"].restype = ctypes.c_int
    _API["prepare_read"].argtypes = [ctypes.c_void_p]
    _API["prepare_read"].restype = ctypes.c_int
    _API["read_events"].argtypes = [ctypes.c_void_p]
    _API["read_events"].restype = ctypes.c_int
    _API["cancel_read"].argtypes = [ctypes.c_void_p]
    _API["cancel_read"].restype = None
    _API["get_fd"].argtypes = [ctypes.c_void_p]
    _API["get_fd"].restype = ctypes.c_int
    _API["add_listener"].argtypes = [ctypes.c_void_p,
                                     ctypes.POINTER(ctypes.c_void_p),
                                     ctypes.c_void_p]
    _API["add_listener"].restype = ctypes.c_int
    # interface/version are passed as raw pointers (a new-id/proxy or a
    # `struct wl_interface *`), so keep them opaque.
    _API["marshal_flags"].argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_uint32,
                                      ctypes.c_uint32,
                                      ctypes.POINTER(WlArgument)]
    _API["marshal_flags"].restype = ctypes.c_void_p

    # wl_display_get_registry() and wl_registry_bind() are only available as
    # static inline helpers, so the requests are emitted manually below using a
    # ctypes-built wl_registry interface table (see _build_protocol_definitions).
    _WL_REGISTRY_INTERFACE = ctypes.byref(_PROTO["registry_interface"])
    REGISTRY_VERSION = 1
    DISPLAY_GET_REGISTRY_OPCODE = 1
else:
    _API = None


def _parse_state_array(state_ptr):
    if not state_ptr:
        return set()
    arr = ctypes.cast(state_ptr, ctypes.POINTER(WlArray)).contents
    step = ctypes.sizeof(ctypes.c_uint32)
    states = set()
    for i in range(arr.size // step):
        states.add(
            ctypes.c_uint32.from_address(arr.data + i * step).value
        )
    return states


class WaylandToplevelMonitor:
    """Tracks COSMIC Wayland toplevels and reports activated+fullscreen.

    API mirrors :class:`webkit_wallpaper.fullscreen_monitor.FullscreenMonitor`
    so the application can treat both backends identically
    (``is_available``, ``start``, ``stop``, ``is_fullscreen``).
    """

    def __init__(self, on_fullscreen=None, on_restore=None):
        self._on_fullscreen = on_fullscreen
        self._on_restore = on_restore
        self._fullscreen = False
        self._enabled = False
        self._available = False
        self._display = None
        self._registry = None
        self._info = None
        self._fd = -1
        self._source_id = None
        self._zcosmic_name = None
        self._zcosmic_version = 0
        self._toplevels = {}

        self._token = next(_tokens)
        _REGISTRY[self._token] = self
        self._data = ctypes.c_void_p(self._token)

        if _API is None:
            logger.warning(
                "wayland_toplevel_monitor: libwayland-client not found; "
                "fullscreen auto-pause on COSMIC disabled."
            )
            return
        try:
            # Probe once: connect, enumerate globals, look for the protocol.
            self._connect()
            if not self._available:
                logger.info(
                    "wayland_toplevel_monitor: '%s' not offered by the "
                    "compositor; fullscreen auto-pause disabled.",
                    ZCOSMIC_INFO.decode(),
                )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("wayland_toplevel_monitor init error: %s", e)
            self._teardown()

    def set_callback(self, on_fullscreen=None, on_restore=None):
        self._on_fullscreen = on_fullscreen
        self._on_restore = on_restore

    @property
    def is_available(self):
        return self._available

    @property
    def is_fullscreen(self):
        return self._fullscreen

    def start(self):
        if self._enabled:
            return
        if not self._available:
            return
        try:
            if not self._connect():
                self._teardown()
                return
            if self._info is None:
                self._bind_info()
            _API["roundtrip"](self._display)
            self._fd = _API["get_fd"](self._display)
            if self._fd < 0:
                self._teardown()
                return
            self._enabled = True
            self._source_id = GLib.io_add_watch(
                self._fd, GLib.IOCondition.IN, self._on_fd_ready
            )
            self._recompute()
            logger.info(
                "wayland_toplevel_monitor: listening to toplevel state "
                "changes (%d toplevels)", len(self._toplevels)
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("wayland_toplevel_monitor.start() failed: %s", e)
            self.stop()

    def stop(self):
        if self._source_id is not None:
            GLib.source_remove(self._source_id)
            self._source_id = None
        self._enabled = False
        self._toplevels.clear()
        self._info = None
        self._fd = -1
        self._teardown()
        self._fullscreen = False
        logger.info("wayland_toplevel_monitor: stopped")

    # -- protocol wiring ----------------------------------------------------

    def _connect(self):
        if self._display is not None:
            return True
        disp = _API["connect"](None)
        if not disp:
            return False
        self._display = disp
        args = (WlArgument * 1)()
        reg = _API["marshal_flags"](
            disp, DISPLAY_GET_REGISTRY_OPCODE, _WL_REGISTRY_INTERFACE,
            REGISTRY_VERSION, 0, args)
        if not reg:
            self._teardown()
            return False
        self._registry = reg
        _API["add_listener"](reg, _registry_listener, self._data)
        _API["roundtrip"](disp)
        if self._zcosmic_name is None:
            self._available = False
            return False
        self._available = True
        return True

    def _bind_info(self):
        args = (WlArgument * 4)()
        args[0].u = self._zcosmic_name
        args[1].s = ZCOSMIC_INFO
        args[2].u = INFO_VERSION
        info = _API["marshal_flags"](
            self._registry, 0,
            ctypes.byref(_PROTO["info_interface"]),
            INFO_VERSION, 0, args
        )
        if not info:
            raise RuntimeError("wl_registry.bind('%s') returned NULL"
                               % ZCOSMIC_INFO.decode())
        self._info = info
        _API["add_listener"](info, _info_listener, self._data)

    def _teardown(self):
        if self._display is not None:
            try:
                _API["disconnect"](self._display)
            except Exception:  # pragma: no cover - defensive
                pass
        self._display = None
        self._registry = None
        self._info = None
        self._fd = -1

    def _on_fd_ready(self, _fd, _condition):
        try:
            _API["flush"](self._display)
            for _ in range(16):
                if _API["prepare_read"](self._display) == 0:
                    break
                _API["dispatch_pending"](self._display)
            else:
                _API["cancel_read"](self._display)
                _API["dispatch_pending"](self._display)
                return True
            if _API["read_events"](self._display) < 0:
                _API["cancel_read"](self._display)
            _API["dispatch_pending"](self._display)
            self._recompute()
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("wayland_toplevel_monitor fd handler error: %s", e)
        return True

    # -- protocol handlers --------------------------------------------------

    def _on_global(self, name, interface, version):
        if interface == ZCOSMIC_INFO and self._zcosmic_name is None:
            self._zcosmic_name = name
            self._zcosmic_version = version
            logger.debug("wayland_toplevel_monitor: found %s v%d",
                         ZCOSMIC_INFO.decode(), version)

    def _on_global_remove(self, name):
        if name == self._zcosmic_name:
            self._zcosmic_name = None
            self._available = False

    def _on_info_toplevel(self, handle):
        if not handle:
            return
        self._toplevels.setdefault(handle, {"states": set(), "title": b"", "app_id": b""})
        _API["add_listener"](handle, _handle_listener, self._data)

    def _on_info_finished(self):
        self._available = False
        logger.warning(
            "wayland_toplevel_monitor: compositor sent 'finished'; "
            "fullscreen auto-pause disabled."
        )

    def _on_handle_closed(self, target):
        self._toplevels.pop(int(target), None)

    def _on_handle_title(self, target, title):
        entry = self._toplevels.get(int(target))
        if entry is not None:
            entry["title"] = title or b""

    def _on_handle_app_id(self, target, app_id):
        entry = self._toplevels.get(int(target))
        if entry is not None:
            entry["app_id"] = app_id or b""

    def _on_handle_state(self, target, state_array):
        key = int(target)
        entry = self._toplevels.get(key)
        if entry is None:
            entry = self._toplevels[key] = {
                "states": set(), "title": b"", "app_id": b""}
        entry["states"] = _parse_state_array(state_array)

    # -- fullscreen evaluation ----------------------------------------------

    def _recompute(self):
        fullscreen_now = any(
            STATE_ACTIVATED in entry["states"]
            and STATE_FULLSCREEN in entry["states"]
            for entry in self._toplevels.values()
        )
        self._set_fullscreen(fullscreen_now)

    def _set_fullscreen(self, value):
        if value == self._fullscreen:
            return
        self._fullscreen = value
        logger.info("wayland_toplevel_monitor: fullscreen=%s", value)
        if value:
            cb = self._on_fullscreen
        else:
            cb = self._on_restore
        if cb:
            cb()