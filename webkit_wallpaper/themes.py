import configparser
import os
import shutil
import zipfile

USER_THEMES_DIR = os.path.join(
    os.path.expanduser("~"), ".local", "share", "webkit_wallpaper", "themes"
)
SYSTEM_THEMES_DIR = "/usr/share/webkit_wallpaper/themes"


def _parse_theme_file(theme_file):
    parser = configparser.ConfigParser()
    parser.read(theme_file)
    if not parser.has_section("Theme"):
        return None
    name = parser.get("Theme", "Name", fallback="")
    description = parser.get("Theme", "Description", fallback="")
    author = parser.get("Theme", "Author", fallback="")
    version = parser.get("Theme", "Version", fallback="")
    thumbnail = parser.get("Theme", "Thumbnail", fallback="")
    entry = parser.get("Theme", "Entry", fallback="index.html")
    return {
        "name": name,
        "description": description,
        "author": author,
        "version": version,
        "thumbnail": thumbnail,
        "entry": entry,
    }


def scan_themes():
    themes = []
    for themes_dir in [SYSTEM_THEMES_DIR, USER_THEMES_DIR]:
        if not os.path.isdir(themes_dir):
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
    return themes


def get_theme_entry_uri(theme):
    entry_path = theme.get("entry_path", "")
    if entry_path:
        return "file://" + entry_path
    return ""


def install_theme(zip_path):
    if not zipfile.is_zipfile(zip_path):
        return None, "Not a valid zip file"

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        theme_files = [n for n in names if n.endswith(".theme")]
        if not theme_files:
            return None, "No .theme file found in zip"

        theme_name = os.path.splitext(os.path.basename(theme_files[0]))[0]
        theme_dir = os.path.join(USER_THEMES_DIR, theme_name)
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
        shutil.rmtree(theme_dir, ignore_errors=True)
        return None, "Invalid .theme file format"

    meta["folder"] = theme_dir
    meta["id"] = theme_name
    meta["user"] = True
    thumb_path = os.path.join(theme_dir, meta["thumbnail"])
    meta["thumbnail_path"] = thumb_path if os.path.isfile(thumb_path) else ""
    entry_path = os.path.join(theme_dir, meta["entry"])
    meta["entry_path"] = entry_path if os.path.isfile(entry_path) else ""
    return meta, None


def uninstall_theme(theme_id):
    theme_dir = os.path.join(USER_THEMES_DIR, theme_id)
    if os.path.isdir(theme_dir):
        shutil.rmtree(theme_dir, ignore_errors=True)
        return True
    return False
