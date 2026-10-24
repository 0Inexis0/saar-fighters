"""System-wide Wayland idle notifications in an isolated helper process.

Uses libwayland-client's public C ABI and ext-idle-notify. No input is recorded.
Protocol: https://wayland.app/protocols/ext-idle-notify-v1
"""
import ctypes as C
import ctypes.util

TIMEOUT_MS = 300_000


class Interface(C.Structure):
    pass


class Message(C.Structure):
    _fields_ = [("name", C.c_char_p), ("signature", C.c_char_p),
                ("types", C.POINTER(C.POINTER(Interface)))]


Interface._fields_ = [("name", C.c_char_p), ("version", C.c_int),
                     ("method_count", C.c_int), ("methods", C.POINTER(Message)),
                     ("event_count", C.c_int), ("events", C.POINTER(Message))]


def watch():
    lib = C.CDLL(ctypes.util.find_library("wayland-client") or "libwayland-client.so.0")
    lib.wl_display_connect.argtypes = [C.c_char_p]
    lib.wl_display_connect.restype = C.c_void_p
    for name in ("wl_display_roundtrip", "wl_display_dispatch"):
        getattr(lib, name).argtypes = [C.c_void_p]
        getattr(lib, name).restype = C.c_int
    lib.wl_display_disconnect.argtypes = [C.c_void_p]
    lib.wl_proxy_marshal_flags.argtypes = [C.c_void_p, C.c_uint,
                                         C.POINTER(Interface), C.c_uint, C.c_uint]
    lib.wl_proxy_marshal_flags.restype = C.c_void_p
    lib.wl_proxy_add_listener.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p]
    lib.wl_proxy_add_listener.restype = C.c_int
    display = lib.wl_display_connect(None)
    if not display:
        raise RuntimeError("Wayland-Verbindung nicht verfügbar")
    try:
        registry_interface = Interface.in_dll(lib, "wl_registry_interface")
        seat_interface = Interface.in_dll(lib, "wl_seat_interface")
        destroy = (Message * 1)(Message(b"destroy", b"", None))
        events = (Message * 2)(Message(b"idled", b"", None), Message(b"resumed", b"", None))
        notification_interface = Interface(b"ext_idle_notification_v1", 1, 1, destroy, 2, events)
        types = (C.POINTER(Interface) * 3)(C.pointer(notification_interface), None, C.pointer(seat_interface))
        methods = (Message * 3)(Message(b"destroy", b"", None),
                               Message(b"get_idle_notification", b"nuo", types),
                               Message(b"get_input_idle_notification", b"2nuo", types))
        notifier_interface = Interface(b"ext_idle_notifier_v1", 2, 3, methods, 0, None)
        registry = lib.wl_proxy_marshal_flags(display, 1, C.byref(registry_interface), 1, 0, C.c_void_p())
        globals_found = {}
        global_callback = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint, C.c_char_p, C.c_uint)
        remove_callback = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint)

        @global_callback
        def announced(data, proxy, name, interface, version):
            globals_found[interface] = (name, version)

        @remove_callback
        def removed(data, proxy, name):
            # A replaced seat needs a fresh connection; the parent restarts us.
            if any(value[0] == name for key, value in globals_found.items()
                   if key in (b"wl_seat", b"ext_idle_notifier_v1")):
                print("resumed", flush=True)
                import os
                os._exit(1)

        listeners = (C.c_void_p * 2)(C.cast(announced, C.c_void_p), C.cast(removed, C.c_void_p))
        if lib.wl_proxy_add_listener(registry, listeners, None) != 0 or lib.wl_display_roundtrip(display) < 0:
            raise RuntimeError("Wayland-Registry nicht erreichbar")

        def bind(interface, maximum):
            name, offered = globals_found[interface.name]
            version = min(offered, maximum)
            proxy = lib.wl_proxy_marshal_flags(registry, 0, C.byref(interface), version, 0,
                                              C.c_uint(name), interface.name, C.c_uint(version), C.c_void_p())
            if not proxy:
                raise RuntimeError("Wayland-Schnittstelle nicht verfügbar")
            return proxy, version

        seat, _ = bind(seat_interface, 1)
        notifier, version = bind(notifier_interface, 2)
        notification = lib.wl_proxy_marshal_flags(
            notifier, 2 if version >= 2 else 1, C.byref(notification_interface), 1, 0,
            C.c_void_p(), C.c_uint(TIMEOUT_MS), C.c_void_p(seat))
        event_callback = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p)

        @event_callback
        def idled(data, proxy):
            print("idled", flush=True)

        @event_callback
        def resumed(data, proxy):
            print("resumed", flush=True)

        event_listeners = (C.c_void_p * 2)(C.cast(idled, C.c_void_p), C.cast(resumed, C.c_void_p))
        if not notification or lib.wl_proxy_add_listener(notification, event_listeners, None) != 0:
            raise RuntimeError("Inaktivitätserkennung nicht verfügbar")
        print("ready", flush=True)
        while lib.wl_display_dispatch(display) >= 0:
            pass
        raise RuntimeError("Wayland-Verbindung unterbrochen")
    finally:
        lib.wl_display_disconnect(display)


if __name__ == "__main__":
    watch()
