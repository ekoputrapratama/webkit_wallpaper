from setuptools import setup, find_packages

setup(
    name="webkit_wallpaper",
    version="0.1.0",
    description="Linux desktop wallpaper powered by a webview",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "webkit_wallpaper=webkit_wallpaper.main:main",
        ],
    },
    package_data={
        "webkit_wallpaper": ["assets/*"],
    },
    python_requires=">=3.8",
)
