from setuptools import setup

setup(
    name="waypoint-editor",
    version="1.0",
    packages=["src"],
    install_requires=[
        "numpy",
        "PySide6",
        "PyYAML"
    ],
)

""" ビルドコマンド """

"""
pyinstaller --name="WaypointEditor" \
            --windowed \
            --onefile \
            --add-data="./resources:resources" \
            main_all.py

"""