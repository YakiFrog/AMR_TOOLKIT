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

## Notes / Bug fixes

- Ubuntu 24 (Wayland/HiDPI) でのマウス位置のずれ（ペン、消しゴム、ウェイポイント配置）が出る問題を修正しました。
    - 修正内容の概要:
        - ラベル上の表示座標（表示された Pixmap）と実画像（pixmap）ピクセル座標の変換を一元化するヘルパーを追加しました (ImageViewer.display_to_image_coords / image_to_display_coords)。
        - DrawableLabel / ImageViewer のマウスイベントで正しい座標変換を行うように更新（クリック／ドラッグ／ホバー／右クリックなど）。
        - main() で Qt の HiDPI 設定を有効化して、Wayland/HiDPI 環境でのスケーリング挙動を改善。
        - ウェイポイントのマークと文字（フォント）を少し小さくしました（`WAYPOINT_SETTINGS` の BASE_SIZE 等を調整）。

    - テスト方法:
        - 通常起動: python3 main_all.py
        - X11 での比較: QT_QPA_PLATFORM=xcb python3 main_all.py
        - スケーリングを無効にして挙動を確認: QT_AUTO_SCREEN_SCALE_FACTOR=0 QT_SCALE_FACTOR=1 python3 main_all.py
