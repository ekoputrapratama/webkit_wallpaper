#!/usr/bin/env python3
import os


def _has_nvidia():
    if os.path.exists("/proc/driver/nvidia"):
        return True
    try:
        with open("/proc/modules") as f:
            for line in f:
                if line.startswith("nvidia "):
                    return True
    except OSError:
        pass
    return False


def _apply_webkit_workarounds():
    # WebKitGTK's DMABUF renderer fails to allocate GBM buffers on the
    # proprietary NVIDIA driver ("Failed to create GBM buffer: Invalid
    # argument"), which stalls rendering entirely. Fall back to the legacy
    # renderer only when NVIDIA is detected; other GPUs keep full GPU
    # acceleration.
    if _has_nvidia():
        os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")


_apply_webkit_workarounds()

from webkit_wallpaper.main import main

if __name__ == "__main__":
    main()
