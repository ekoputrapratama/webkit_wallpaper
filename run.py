#!/usr/bin/env python3
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)

from webkit_wallpaper.main import main

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.debug("run.py invoked as __main__")
    main()
