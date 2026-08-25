from setuptools import setup, find_packages

setup(
    name="webkit_wallpaper",
    version="0.4.4",
    description="Linux desktop wallpaper powered by a webview",
    packages=find_packages(),
    # Installed as the "webkit_wallpaper" launcher script so autostart
    # .desktop entries and manual launches share one entry point.
    scripts=["scripts/webkit_wallpaper"],
    package_data={
        "webkit_wallpaper": ["assets/*", ".env"],
    },
    python_requires=">=3.8",
)
