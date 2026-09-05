import configparser
import logging
import os
import shutil
import zipfile

logger = logging.getLogger(__name__)

USER_THEMES_DIR = os.path.join(
    os.path.expanduser("~"), ".local", "share", "webkit_wallpaper", "themes"
)
SYSTEM_THEMES_DIR = "/usr/share/webkit_wallpaper/themes"


def _parse_theme_file(theme_file):
    logger.debug("_parse_theme_file(%s)", theme_file)
    parser = configparser.ConfigParser()
    parser.read(theme_file)
    if not parser.has_section("Theme"):
        logger.debug("_parse_theme_file() no [Theme] section in %s", theme_file)
        return None
    name = parser.get("Theme", "Name", fallback="")
    description = parser.get("Theme", "Description", fallback="")
    author = parser.get("Theme", "Author", fallback="")
    version = parser.get("Theme", "Version", fallback="")
    thumbnail = parser.get("Theme", "Thumbnail", fallback="")
    entry = parser.get("Theme", "Entry", fallback="index.html")
    result = {
        "name": name,
        "description": description,
        "author": author,
        "version": version,
        "thumbnail": thumbnail,
        "entry": entry,
    }
    logger.debug("_parse_theme_file() -> %s", result)
    return result


def scan_themes():
    logger.debug("scan_themes() scanning system and user theme dirs")
    themes = []
    for themes_dir in [SYSTEM_THEMES_DIR, USER_THEMES_DIR]:
        logger.debug("scan_themes() checking dir: %s", themes_dir)
        if not os.path.isdir(themes_dir):
            logger.debug("scan_themes() dir does not exist: %s", themes_dir)
            continue
        for entry in sorted(os.listdir(themes_dir)):
            theme_dir = os.path.join(themes_dir, entry)
            if not os.path.isdir(theme_dir):
                continue
            theme_file = os.path.join(theme_dir, f"{entry}.theme")
            if not os.path.isfile(theme_file):
                continue
            meta = _parse_theme_file(theme_file)
            if meta is None:
                continue
            meta["folder"] = theme_dir
            meta["id"] = entry
            meta["user"] = themes_dir == USER_THEMES_DIR
            thumb_path = os.path.join(theme_dir, meta["thumbnail"])
            meta["thumbnail_path"] = thumb_path if os.path.isfile(thumb_path) else ""
            entry_path = os.path.join(theme_dir, meta["entry"])
            meta["entry_path"] = entry_path if os.path.isfile(entry_path) else ""
            themes.append(meta)
            logger.debug("scan_themes() found theme: %s (id=%s)", meta["name"], entry)
    logger.debug("scan_themes() total themes found: %d", len(themes))
    return themes


def get_theme_entry_uri(theme):
    logger.debug("get_theme_entry_uri(theme=%s)", theme.get("id", "unknown"))
    entry_path = theme.get("entry_path", "")
    if entry_path:
        uri = "file://" + entry_path
        logger.debug("get_theme_entry_uri() -> %s", uri)
        return uri
    logger.debug("get_theme_entry_uri() -> empty (no entry_path)")
    return ""


def install_theme(zip_path):
    logger.debug("install_theme(zip_path=%s)", zip_path)
    if not zipfile.is_zipfile(zip_path):
        logger.warning("install_theme() not a valid zip file: %s", zip_path)
        return None, "Not a valid zip file"

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        theme_files = [n for n in names if n.endswith(".theme")]
        if not theme_files:
            logger.warning("install_theme() no .theme file found in zip")
            return None, "No .theme file found in zip"

        theme_name = os.path.splitext(os.path.basename(theme_files[0]))[0]
        theme_dir = os.path.join(USER_THEMES_DIR, theme_name)
        logger.debug("install_theme() theme_name=%s, theme_dir=%s", theme_name, theme_dir)
        os.makedirs(theme_dir, exist_ok=True)

        # Find common prefix to strip (e.g. "sakura/" from "sakura/css/style.css")
        non_dir = [n for n in names if not n.endswith("/")]
        prefix = os.path.commonprefix(non_dir)
        prefix = os.path.dirname(prefix)
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"
        elif prefix:
            pass
        else:
            prefix = ""
        logger.debug("install_theme() common prefix=%r", prefix)

        for name in names:
            if name.startswith("__MACOSX") or name.startswith("."):
                continue
            # Strip common prefix to get relative path
            rel = name[len(prefix):] if prefix else name
            if not rel:
                continue
            target = os.path.join(theme_dir, rel)
            if name.endswith("/"):
                os.makedirs(target, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    meta = _parse_theme_file(os.path.join(theme_dir, f"{theme_name}.theme"))
    if meta is None:
        logger.warning("install_theme() invalid .theme file format after extraction")
        shutil.rmtree(theme_dir, ignore_errors=True)
        return None, "Invalid .theme file format"

    meta["folder"] = theme_dir
    meta["id"] = theme_name
    meta["user"] = True
    thumb_path = os.path.join(theme_dir, meta["thumbnail"])
    meta["thumbnail_path"] = thumb_path if os.path.isfile(thumb_path) else ""
    entry_path = os.path.join(theme_dir, meta["entry"])
    meta["entry_path"] = entry_path if os.path.isfile(entry_path) else ""
    logger.debug("install_theme() success: id=%s, name=%s", meta["id"], meta["name"])
    return meta, None


def uninstall_theme(theme_id):
    logger.debug("uninstall_theme(theme_id=%s)", theme_id)
    theme_dir = os.path.join(USER_THEMES_DIR, theme_id)
    if os.path.isdir(theme_dir):
        shutil.rmtree(theme_dir, ignore_errors=True)
        logger.debug("uninstall_theme() removed %s", theme_dir)
        return True
    logger.debug("uninstall_theme() dir not found: %s", theme_dir)
    return False
