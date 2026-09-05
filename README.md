# WebKit Wallpaper

A Linux desktop wallpaper app that renders web pages and WebGL shaders as your background. Browse and install themes from the community store, or load any URL directly.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![GTK](https://img.shields.io/badge/GTK-3-orange)
[![AUR package](https://img.shields.io/aur/version/webkit-wallpaper)](https://aur.archlinux.org/packages/webkit-wallpaper)

## Support this project

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Y8Y1GAB4X)
<a href="https://www.buymeacoffee.com/ekoputraprm" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>

## Features

- Use any web page or WebGL shader as your desktop wallpaper
- Community theme store powered by Firebase
- System tray with quick controls
- Auto-start on login
- Dark/light theme support
- Drag & drop `.zip` theme installation
- **Auto-pause**: when another app is fullscreen, the wallpaper is paused (shown as a frozen screenshot) to free GPU/CPU, and resumes automatically when fullscreen closes
- Works on X11 and Wayland (wlroots, COSMIC, KDE)

## Desktop integration

| Desktop        | Integration                                                                         | Tested | Auto pause |
| -------------- | ----------------------------------------------------------------------------------- | :----: | :--------: |
| **KDE Plasma** | [webwallpaper-kde](https://github.com/ekoputrapratama/webwallpaper-kde/)            |   ✅   |     ✅     |
| **Hyprland**   | [webkit_wallpaper/layer_shell](https://github.com/ekoputrapratama/webkit_wallpaper) |   ❌   |     ❌     |
| **Niri**       | [webkit_wallpaper/layer_shell](https://github.com/ekoputrapratama/webkit_wallpaper) |   ❌   |     ❌     |
| **Wayfire**    | [webkit_wallpaper/layer_shell](https://github.com/ekoputrapratama/webkit_wallpaper) |   ❌   |     ❌     |
| **COSMIC**     | [webkit_wallpaper/layer_shell](https://github.com/ekoputrapratama/webkit_wallpaper) |   ✅   |     ✅     |
| **Sway**       | [webkit_wallpaper/layer_shell](https://github.com/ekoputrapratama/webkit_wallpaper) |   ❌   |     ❌     |

## Installation

### Arch Linux (AUR)

```bash
# Using yay
yay -S webkit-wallpaper

# Or using paru
paru -S webkit-wallpaper
```

### System Dependencies

**Debian / Ubuntu:**

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
    gir1.2-ayatanaappindicator3-0.1

# Fallback (GTK-free appindicator, if the above is unavailable):
sudo apt install gir1.2-ayatanaappindicatorglib-2.0

# For Wayland layer-shell support (Sway, Hyprland, KDE Plasma 6, COSMIC)
sudo apt install gir1.2-gtklayershell-0.1
# Arch: sudo pacman -S gtk-layer-shell

# For auto-pause on fullscreen (X11 / XWayland detection via EWMH):
sudo apt install x11-utils
# Arch: sudo pacman -S xorg-xprop
```

**Important:** KDE Plasma 6 supports the wlr-layer-shell protocol, but you
need the **GTK-specific bindings** (`gtk-layer-shell` / `gir1.2-gtklayershell-0.1`),
not the Qt version (`layer-shell-qt`). The Qt version only works for Qt apps.

The tray icon uses the classic dbusmenu-based appindicator libraries first,
since GNOME Shell, KDE, XFCE and COSMIC panels all render those. The newer
`libayatana-appindicator-glib` is only used when the legacy ones are missing
(its `org.gtk.Menus` protocol is not yet supported by the GNOME Shell
AppIndicator extension). Force a backend with
`WEBKIT_WALLPAPER_TRAY_BACKEND=glib`.

### Run

```bash
cd webkit_wallpaper
python3 run.py
```

## Theme Structure

A theme is a folder containing an INI-style `.theme` file and the web assets:

```
my_theme/
├── my_theme.theme      # Identity file
├── thumbnail.png       # Preview image for the store
├── index.html          # Entry point
├── style.css
└── script.js
```

### `.theme` file format

```ini
[Theme]
Name=My Theme
Description=A short description
Author=Your Name
Version=1.0
Thumbnail=thumbnail.png
Entry=index.html
```

### Theme directories

The app scans these locations for installed themes:

- **System**: `/usr/share/webkit_wallpaper/themes/`
- **User**: `~/.local/share/webkit_wallpaper/themes/`

## Becoming a Theme Author

### 1. Create a theme

Create a folder with a `.theme` file and your web assets. The entry point should be an HTML file that fills the full viewport (`100vw x 100vh`). Use CSS animations or WebGL for animated wallpapers.

**Minimal example:**

```html
<!DOCTYPE html>
<html>
  <head>
    <style>
      * {
        margin: 0;
      }
      body {
        width: 100vw;
        height: 100vh;
        background: linear-gradient(135deg, #667eea, #764ba2);
        background-size: 400% 400%;
        animation: g 8s ease infinite;
      }
      @keyframes g {
        0% {
          background-position: 0% 50%;
        }
        50% {
          background-position: 100% 50%;
        }
        100% {
          background-position: 0% 50%;
        }
      }
    </style>
  </head>
  <body></body>
</html>
```

### 2. Zip your theme

```bash
cd my_theme
zip -r ../my_theme.zip .
```

### 3. Submit to the store

Go to the [Theme Submitter](./theme-submitter/) web app:

1. Register an account
2. Fill in the theme details
3. Upload your `.zip` and a thumbnail image
4. Optionally add a donation link (Ko-fi, Buy Me a Coffee, etc.)
5. Submit

Your theme will appear in the store for others to install.

## Installing Themes

**From the store:** Open the tray menu → Store → browse and click Apply.

**From a `.zip` file:** Open Settings → drag and drop a `.zip` onto the Themes section.

**Manually:** Extract a theme folder into `~/.local/share/webkit_wallpaper/themes/`.

## Auto-pause on fullscreen

By default the wallpaper pauses whenever another window goes fullscreen: it
captures a frozen screenshot of the current frame, hides the webview, and
shows the screenshot in its place so the WebKit web process stops rendering
(no blank screen — the screenshot covers the window until the webview has
finished reloading after you close the fullscreen app).

- Toggle it from **Settings → Auto-pause on fullscreen**, or from the tray
  menu's **Auto-pause on fullscreen** item.
- Use the tray menu's **Pause**/**Resume** item to pause/resume manually.
- Detection works via the X11 EWMH protocol, so it covers X11 sessions and
  XWayland windows. It requires the `xprop` utility (`x11-utils` /
  `xorg-xprop`); if it's missing, auto-pause logs a notice and stays off.
  Native Wayland-only compositors that don't expose window state via EWMH
  (e.g. GNOME Wayland) can't be detected this way.

## Troubleshooting

### KDE Plasma — wallpaper behind panels/windows

KDE Plasma 6 supports the `wlr-layer-shell` protocol, but the app needs the
**GTK layer-shell bindings** (`gir1.2-gtklayershell-0.1` on Debian/Ubuntu,
`gtk-layer-shell` on Arch). The Qt package `layer-shell-qt` only works for
Qt apps and does not help here. If the wallpaper appears behind all windows,
install the GTK bindings:

```bash
# Debian / Ubuntu
sudo apt install gir1.2-gtklayershell-0.1

# Arch Linux
sudo pacman -S gtk-layer-shell
```

On KDE Plasma 5, the compositor does **not** support layer-shell. The app
will fall back to X11 desktop window hints via XWayland, which works but
may not be perfectly reliable.

### NVIDIA (proprietary driver)

WebKitGTK's DMABUF renderer cannot allocate GBM buffers on the proprietary
NVIDIA driver, which stalls rendering entirely. `run.py` detects NVIDIA and
automatically sets `WEBKIT_DISABLE_DMABUF_RENDERER=1` to fall back to the
legacy renderer. On some NVIDIA + XWayland setups frames are still copied
through software, which costs performance at high resolutions — use the
**FPS cap** setting in the tray menu → Settings to reduce CPU/GPU load
(30 or 24 FPS is usually fine for a wallpaper).

To override the automatic workaround, set the variable yourself before
launching (it is never overwritten):

```bash
WEBKIT_DISABLE_DMABUF_RENDERER=0 python3 run.py
```

## License

[MIT](./LICENSE)
