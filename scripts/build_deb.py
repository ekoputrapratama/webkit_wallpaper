#!/usr/bin/env python3
"""Build a Debian (.deb) package using only the Python standard library.

Produces dist/webkit-wallpaper_<version>-1_all.deb with an FHS layout:

    /usr/bin/webkit_wallpaper                          launcher
    /usr/share/webkit_wallpaper/webkit_wallpaper/     application (incl. assets)
    /usr/share/applications/webkit-wallpaper.desktop  menu entry
    /usr/share/pixmaps/webkit-wallpaper.png           icon
    /usr/share/doc/webkit-wallpaper/                  license + readme
    /usr/share/man/man1/webkit-wallpaper.1.gz         man page

Usage:
    python3 scripts/build_deb.py
    python3 scripts/build_deb.py --version 0.1.0-1 -o dist

The developer's .env is never copied into the package.
"""
import argparse
import gzip
import hashlib
import io
import lzma
import re
import shutil
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = "webkit-wallpaper"
BIN_NAME = "webkit_wallpaper"

EXCLUDE_FILES = {}          # never ship developer credentials
EXCLUDE_DIRS = {"__pycache__", "debian", ".git"}

CONTROL_TEMPLATE = """Package: {pkg}
Version: {version}
Section: utils
Priority: optional
Architecture: all
Installed-Size: {installed_size}
Depends: python3 (>= 3.8), python3-gi, python3-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
Recommends: gir1.2-ayatanaappindicator3-0.1 | gir1.2-appindicator3-0.1, gir1.2-gtklayershell-0.1
Suggests: gir1.2-gtklayershell-0.1
Homepage: https://github.com/ekoputrapratama/webkit_wallpaper
Maintainer: Ekoputra Pratama <muhammad.sayuti94@gmeil.com>
Description: Linux desktop live wallpaper powered by a webview
 Run any web page, canvas animation or shader as your desktop wallpaper.
 Supports multi-monitor setups, Wayland (layer-shell) and X11, per-monitor
 themes with configurable FPS cap, and a built-in theme store.
 .
 Requires WebKitGTK 4.1 (Debian 12+/Ubuntu 22.04+). On Wayland compositors,
 install gir1.2-gtklayershell-0.1 for proper desktop-layer placement.
"""

LAUNCHER = """#!/usr/bin/env python3
import sys

sys.path.insert(0, "/usr/share/{pkg_underscore}")

from webkit_wallpaper.main import main

if __name__ == "__main__":
    sys.exit(main())
"""

DESKTOP = """[Desktop Entry]
Type=Application
Name=WebKit Wallpaper
GenericName=Live Wallpaper
Comment=Web-based desktop wallpaper powered by WebKitGTK
Exec={bin}
TryExec={bin}
Icon=webkit-wallpaper
Terminal=false
Categories=Utility;
Keywords=wallpaper;live;webkit;html;
StartupNotify=false
"""

MANPAGE = """.TH WEBKIT_WALLPAPER 1 "{date}" "webkit-wallpaper {version}" "User Commands"
.SH NAME
webkit_wallpaper \\- Linux desktop live wallpaper powered by a webview
.SH SYNOPSIS
.B webkit_wallpaper
.RI [ command ]
.SH DESCRIPTION
.B webkit_wallpaper
renders a web page, canvas animation or shader as the desktop wallpaper.
It runs in the system tray; use the tray menu to open Settings, browse the
theme Store, toggle autostart, or quit.
.SH COMMANDS
.TP
.B start
Start the wallpaper (default).
.TP
.B stop
Stop any running instance.
.SH FILES
.TP
.I ~/.config/webkit_wallpaper/config.json
User configuration.
.TP
.I ~/.local/share/webkit_wallpaper/themes/
User-installed themes.
.SH HOMEPAGE
https://github.com/ekoputrapratama/webkit_wallpaper
"""


def detect_version():
    text = (ROOT / "setup.py").read_text()
    m = re.search(r'version\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit("Could not detect version from setup.py")
    return m.group(1)


def copy_tree(src, dst):
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        parts = set(rel.parts)
        if parts & EXCLUDE_DIRS:
            continue
        if item.name in EXCLUDE_FILES or item.suffix in (".pyc", ".pyo"):
            continue
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def make_tar_bytes(root):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tf:
        entries = sorted(root.rglob("*"), key=lambda p: str(p.relative_to(root)))
        for path in entries:
            arcname = "./" + str(path.relative_to(root))
            ti = tf.gettarinfo(str(path), arcname=arcname)
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = "root"
            ti.mtime = int(time.time())
            if path.is_dir():
                ti.type = tarfile.DIRTYPE
                ti.mode = 0o755
                tf.addfile(ti)
            else:
                ti.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                with open(path, "rb") as fh:
                    tf.addfile(ti, fh)
    return buf.getvalue()


def ar_member(name, data):
    header = "{:<16}{:<12}{:<6}{:<6}{:<8}{:<10}".format(
        name, "0", "0", "0", "100644", str(len(data))
    ).encode("ascii") + b"`\n"
    pad = b"\n" if len(data) % 2 else b""
    return header + data + pad


def write_ar(path, members):
    with open(path, "wb") as f:
        f.write(b"!<arch>\n")
        for name, data in members:
            f.write(ar_member(name, data))


def build(version, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    staging = out_dir / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    data_root = staging / "data"
    deb_root = staging / "DEBIAN"
    share = data_root / "usr" / "share"
    app_dir = share / PKG.replace("-", "_")

    # --- application files -------------------------------------------------
    app_pkg = app_dir / "webkit_wallpaper"
    app_pkg.mkdir(parents=True)
    copy_tree(ROOT / "webkit_wallpaper", app_pkg)

    bindir = data_root / "usr" / "bin"
    bindir.mkdir(parents=True)
    launcher = bindir / BIN_NAME
    launcher.write_text(LAUNCHER.format(pkg_underscore=PKG.replace("-", "_")))
    launcher.chmod(0o755)

    apps = share / "applications"
    apps.mkdir(parents=True)
    (apps / f"{PKG}.desktop").write_text(DESKTOP.format(bin=BIN_NAME))

    icons = share / "pixmaps"
    icons.mkdir(parents=True)
    shutil.copy2(ROOT / "webkit_wallpaper" / "assets" / "webkit-wallpaper.png",
                 icons / "webkit-wallpaper.png")

    docs = share / "doc" / PKG
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / "LICENSE", docs / "copyright")
    shutil.copy2(ROOT / "README.md", docs / "README.md")

    man = share / "man" / "man1"
    man.mkdir(parents=True)
    gz = gzip.compress(MANPAGE.format(date=time.strftime("%B %Y"),
                                      version=version).encode(), 9, mtime=0)
    (man / f"{BIN_NAME}.1.gz").write_bytes(gz)

    # --- control + md5sums --------------------------------------------------
    installed_kb = sum(p.stat().st_size for p in app_pkg.rglob("*") if p.is_file())
    installed_kb += launcher.stat().st_size
    installed_kb += (icons / "webkit-wallpaper.png").stat().st_size
    installed_kb //= 1024
    installed_kb += 8  # slack for metadata files

    lines = []
    for p in sorted(data_root.rglob("*")):
        if p.is_file():
            digest = hashlib.md5(p.read_bytes()).hexdigest()
            lines.append(f"{digest}  {p.relative_to(data_root)}")
    deb_root.mkdir()
    (deb_root / "md5sums").write_text("\n".join(lines) + "\n")
    (deb_root / "control").write_text(CONTROL_TEMPLATE.format(
        pkg=PKG, version=version, installed_size=installed_kb))

    control_tar = gzip.compress(make_tar_bytes(deb_root), 9, mtime=0)
    data_tar = lzma.compress(make_tar_bytes(data_root))

    deb_path = out_dir / f"{PKG}_{version}_all.deb"
    write_ar(deb_path, [
        ("debian-binary", b"2.0\n"),
        ("control.tar.gz", control_tar),
        ("data.tar.xz", data_tar),
    ])
    shutil.rmtree(staging)
    return deb_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", default=None,
                    help="package version (default: from setup.py + -1)")
    ap.add_argument("-o", "--out", default=str(ROOT / "dist"))
    args = ap.parse_args()

    version = args.version or f"{detect_version()}-1"
    deb = build(version, Path(args.out))
    print(f"Built {deb} ({deb.stat().st_size / 1024:.0f} KiB)")


if __name__ == "__main__":
    main()
