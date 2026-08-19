#!/usr/bin/env python3
import os
os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")
os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

from webkit_wallpaper.main import main

if __name__ == "__main__":
    main()
