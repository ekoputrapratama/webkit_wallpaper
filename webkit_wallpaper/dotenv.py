import os

_ENV = None


def _find_env_file():
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if os.path.isfile(path):
            return path
    return None


def _parse_value(val):
    val = val.strip()
    if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
        val = val[1:-1]
    return val


def load_env():
    global _ENV
    if _ENV is not None:
        return _ENV

    _ENV = {}
    path = _find_env_file()
    if not path:
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

    return _ENV


def get(key, default=""):
    load_env()
    return os.environ.get(key, default)
