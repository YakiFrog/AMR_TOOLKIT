# Map and Waypoint Editor

## Mac OS
<!-- 画像はめ込み -->
![Map and Waypoint Editor](
    image/0124.png
)

## Ubuntu 22.04
<!-- 画像はめ込み -->
![Map and Waypoint Editor](
    image/ubuntu_ver.png
)

## Setup

### Create venv and activate
```bash
python3 -m venv .
source bin/activate
```

### Install dependencies
```bash
pip install -r requirements.txt
```

## Run
```bash
python3 main_all.py
```

## Build
```bash
pyinstaller --name="WaypointEditor" \
            --windowed \
            --onefile \
            --add-data="./resources:resources" \
            main_all.py
```