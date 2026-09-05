import logging
import os

logger = logging.getLogger(__name__)

_ENV = None


def _find_env_file():
    logger.debug("_find_env_file() called")
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if os.path.isfile(path):
            logger.debug("_find_env_file() found: %s", path)
            return path
    logger.debug("_find_env_file() no .env file found")
    return None


def _parse_value(val):
    logger.debug("_parse_value() raw=%r", val)
    val = val.strip()
    if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
        val = val[1:-1]
    logger.debug("_parse_value() result=%r", val)
    return val


def load_env():
    global _ENV
    if _ENV is not None:
        logger.debug("load_env() returning cached env with %d keys", len(_ENV))
        return _ENV

    logger.debug("load_env() parsing .env file")
    _ENV = {}
    path = _find_env_file()
    if not path:
        logger.debug("load_env() no .env file, returning empty dict")
        return _ENV

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = _parse_value(value)
            if key:
                os.environ.setdefault(key, value)
                _ENV[key] = value
                logger.debug("load_env() loaded key=%s", key)

    logger.debug("load_env() finished, loaded %d keys", len(_ENV))
    return _ENV


def get(key, default=""):
    load_env()
    val = os.environ.get(key, default)
    logger.debug("get(key=%s, default=%r) -> %r", key, default, val)
    return val
