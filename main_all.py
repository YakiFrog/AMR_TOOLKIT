import sys
import os
import numpy as np
import yaml  # PyYAMLをインポート
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QMenuBar, QMenu, QLabel, QPushButton,
                              QFileDialog, QScrollArea, QSplitter, QGesture, 
                              QPinchGesture, QSlider, QCheckBox, QFrame, QTextEdit,
                              QMessageBox, QDialog, QLineEdit, QToolTip,
                              QDoubleSpinBox, QGridLayout)
from PySide6.QtCore import Qt, QPoint, Signal, QEvent, QSize, QMimeData, QTimer, QRect, QRectF
from PySide6.QtGui import (QPixmap, QImage, QWheelEvent, QPainter, QPen, QCursor,
                          QDrag, QColor, QPolygon)  # QDragをQtGuiからインポート
from enum import Enum
from collections import OrderedDict


def read_pgm_file(path):
    """P5 PGM を読み込み (ndarray, width, height) を返す。失敗時は (None, 0, 0)。

    路面マッピングの色付き地図（.colored.pgm）はインデックス値のPGMなので、
    呼び出し側で JSON の palette を使って RGB 化する。
    """
    try:
        with open(path, 'rb') as f:
            magic = f.readline().decode('ascii').strip()
            if magic != 'P5':
                return None, 0, 0
            while True:
                line = f.readline().decode('ascii').strip()
                if not line.startswith('#'):
                    break
            width, height = map(int, line.split())
            max_val = int(f.readline().decode('ascii').strip())
            data = f.read()
            if max_val > 255:
                arr = np.frombuffer(data, dtype='>u2')
            else:
                arr = np.frombuffer(data, dtype=np.uint8)
            arr = np.asarray(arr[:width * height]).reshape((height, width))
            return arr, width, height
    except Exception:
        return None, 0, 0


# 共通のスタイル定義
COMMON_STYLES = """
    QWidget {
        font-size: 11px;
    }
"""

WAYPOINT_SETTINGS = {
    'BASE_SIZE': 8,           # 基本サイズ（少し小さく）
    'ARROW_LENGTH_MULT': 2.0,  # 矢印の長さ倍率（少し短く）
    'ARROW_WIDTH_MULT': 0.65,   # 矢印の幅倍率（少し細め）
    'FONT_SIZE_MAIN_MULT': 1.3,      # メイン文字サイズ（少し小さく）
    'FONT_SIZE_ATTR_MULT': 0.6,      # 属性文字サイズ（少し小さく）
    'EDIT_SIZE_MULT': 1.15,     # 編集時のサイズ倍率（わずかに縮小）
}

# Waypointの追加属性とデフォルト値
WAYPOINT_ATTRIBUTE_DEFAULTS = OrderedDict([
    ('rotate', 0.0),
    ('stop', False),
    ('wait_time', 0.0),
    ('change_map', ''),
    ('threshold', -1.0),
    ('person_area', False),
])


def count_configured_waypoint_actions(attributes):
    """Count attributes whose values differ from the action defaults."""
    configured = 0
    for key, value in attributes.items():
        if key not in WAYPOINT_ATTRIBUTE_DEFAULTS:
            if value is not None and value != '':
                configured += 1
            continue

        default = WAYPOINT_ATTRIBUTE_DEFAULTS[key]
        try:
            if isinstance(default, bool):
                normalized = (
                    value.lower() in ('true', '1', 'yes', 'on')
                    if isinstance(value, str)
                    else bool(value)
                )
            elif isinstance(default, float):
                normalized = float(value)
            elif isinstance(default, int):
                normalized = int(value)
            else:
                normalized = str(value)
        except (TypeError, ValueError):
            normalized = value

        if normalized != default:
            configured += 1

    return configured

# Waypointのエクスポート/インポートフォーマット定義
WAYPOINT_FORMAT = {
    'version': '1.0',
    'format': {
        'number': 'int',      # ウェイポイントの番号
        'x': 'float',         # X座標 (メートル)
        'y': 'float',         # Y座標 (メートル) 
        'angle_radians': 'float',  # 角度 (ラジアン)
        'rotate': 'float',      # 到着後の追加回転量
        'stop': 'bool',         # 停止フラグ
        'wait_time': 'float',   # 待機時間 (秒)
        'change_map': 'string', # 切り替え先の地図名
        'threshold': 'float',   # 個別の到着判定距離
        'person_area': 'bool',  # 人物探索エリア
        'manual': 'bool'        # 手動記録ステータス（get_pos_ent等で手動配置した場合のみtrue）
    }
}

# OrderedDictへの変換
WAYPOINT_FORMAT = OrderedDict([
    ('version', WAYPOINT_FORMAT['version']),
    ('format', OrderedDict(WAYPOINT_FORMAT['format']))
])

# Format Editorタブに表示する、ウェイポイント各パラメータの解説（デフォルト値の意味）
WAYPOINT_PARAM_HELP = """【ウェイポイント デフォルトパラメータの意味】

■ 基本フィールド
・number        : ウェイポイント番号（自動採番）
・x, y          : マップ座標 [m]（mapフレーム）
・angle_radians : 姿勢（ヨー角）[rad]

■ 付与タスク（デフォルト値のままの項目はYAML出力から省略されます）
・rotate        : 到着後に追加で回す角度 [rad]（既定 0.0）
・stop          : true で到達時に停止（/stop=true を発行）（既定 false）
・wait_time     : 到達後に待機する時間 [s]（既定 0.0）
・change_map    : 到達後に切り替える地図名。空文字なら切り替えなし（既定 ""）
・threshold     : このWPだけの到達判定距離 [m]。負なら全体既定(2.0m)を使用（既定 -1.0）
・person_area   : true で人物探索エリア。到達後は /stop=false が来るまで停止（既定 false）
・manual        : 手動記録ステータス。get_pos_ent 等で手動配置したWPのみ true（既定 false）。
                  地図上では「緑＋手動バッジ」、自動記録(get_pos_dis等)は false（赤）で表示。

■ 補足
・デフォルト値と等しい属性はエクスポート時に省略されます
  （例: stop=false は出力されない / manual=false も出力されない）。
・タスク付きWP（stop/wait_time/change_map/person_area）は到達判定が 0.5m になります。
"""

# 共通のレイアウト設定
LAYOUT_MARGINS = 8
WIDGET_SPACING = 5
STANDARD_HEIGHT = 25

# ピンチジェスチャーの感度調整用定数
SCALE_SENSITIVITY = 0.2

# スケール関連の定数を追加
MIN_SCALE = 0.02  # 1/50 (スライダー値1に対応)
MAX_SCALE = 2.0   # 100/50 (スライダー値100に対応)
DEFAULT_SCALE = 1.0  # 50/50 (スライダー値50に対応)

class DrawingMode(Enum):
    """"描画モードを定義"""
    NONE = 0
    PEN = 1
    ERASER = 2
    WAYPOINT = 3
    LANDMARK = 4

class Waypoint:
    """ウェイポイントを管理するクラス"""
    counter = 0
    
    @classmethod
    def reset_counter(cls):
        """カウンターをリセット"""
        cls.counter = 0
    
    def __init__(self, pixel_x, pixel_y, angle=0, name=None):
        Waypoint.counter += 1
        self.number = Waypoint.counter
        self.pixel_x = pixel_x
        self.pixel_y = pixel_y
        self.x = 0
        self.y = 0
        self.angle = angle
        self.name = name if name else f"Waypoint {self.number}"
        self.resolution = 0.05  # 解像度を保存
        self.update_display_name()
        self.attributes = dict(WAYPOINT_ATTRIBUTE_DEFAULTS)

    def set_angle(self, angle):
        """角度を設定し、表示名を更新"""
        self.angle = angle
        self.update_display_name()

    def update_display_name(self):
        """表示名を更新"""
        degrees = int(self.angle * 180 / np.pi)  # ラジアンを度に変換
        self.display_name = f"#{self.number:02d} ({self.x:.2f}, {self.y:.2f}) {degrees}°"

    def update_metric_coordinates(self, origin_x, origin_y, resolution):
        """ピクセル座標からメートル座標を計算"""
        # 原点情報を保存
        self._origin_x = origin_x
        self._origin_y = origin_y
        self.resolution = resolution
        
        # 原点からの相対位置をピクセルで計算
        rel_x = (self.pixel_x - origin_x) / 20
        rel_y = (-self.pixel_y + origin_y) / 20 # Y軸を反転

        # メートル単位に変換
        self.x = rel_x 
        self.y = rel_y
        self.update_display_name()

    def renumber(self, new_number):
        """ウェイポイントの番号を変更"""
        self.number = new_number
        self.name = f"Waypoint {self.number}"
        self.update_display_name()

    def set_position(self, x, y):
        """ピクセル座標を更新"""
        self.pixel_x = x
        self.pixel_y = y
        if hasattr(self, '_origin_x') and hasattr(self, '_origin_y'):
            # 既存の原点情報がある場合は座標を更新
            self.update_metric_coordinates(self._origin_x, self._origin_y, self.resolution)

    def set_attribute(self, key, value):
        """属性を設定"""
        self.attributes[key] = value
    
    def get_attribute(self, key, default=None):
        """属性を取得"""
        return self.attributes.get(key, default)


class Landmark:
    """名前付きランドマークを管理するクラス"""
    counter = 0

    @classmethod
    def reset_counter(cls):
        cls.counter = 0

    def __init__(self, pixel_x, pixel_y, angle=0, name=None):
        Landmark.counter += 1
        self.number = Landmark.counter
        self.pixel_x = pixel_x
        self.pixel_y = pixel_y
        self.x = 0
        self.y = 0
        self.angle = angle
        self.name = name if name else f"Landmark {self.number}"
        self.aliases = []
        self.resolution = 0.05
        self.update_display_name()

    def set_angle(self, angle):
        self.angle = angle
        self.update_display_name()

    def set_name(self, name):
        cleaned = str(name).strip()
        if cleaned:
            self.name = cleaned
        self.update_display_name()

    def update_display_name(self):
        degrees = int(self.angle * 180 / np.pi)
        self.display_name = f"{self.name} ({self.x:.2f}, {self.y:.2f}) {degrees}°"

    def update_metric_coordinates(self, origin_x, origin_y, resolution):
        self._origin_x = origin_x
        self._origin_y = origin_y
        self.resolution = resolution
        self.x = (self.pixel_x - origin_x) / 20
        self.y = (-self.pixel_y + origin_y) / 20
        self.update_display_name()

    def set_position(self, x, y):
        self.pixel_x = x
        self.pixel_y = y
        if hasattr(self, '_origin_x') and hasattr(self, '_origin_y'):
            self.update_metric_coordinates(self._origin_x, self._origin_y, self.resolution)

class CustomScrollArea(QScrollArea):
    """カスタムスクロールエリアクラス
    画像の表示領域とスクロール・ズーム機能を提供"""
    scale_changed = Signal(float)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.last_pos = None
        self.mouse_pressed = False
        self.drawing_mode_enabled = False  # 描画モード状態を追加
        
        # ジェスチャー設定を1箇所に集約
        for attr in [self, self.viewport()]:
            attr.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)

    def set_drawing_mode(self, enabled):
        """描画モードの有効/無効を設定"""
        self.drawing_mode_enabled = enabled
        # 描画モード時はビューポートのマウストラッキングを有効化
        self.viewport().setMouseTracking(enabled)

    def mousePressEvent(self, event):
        """マウス押下時のイベント処理
        左クリックでドラッグ開始"""
        if self.drawing_mode_enabled:
            # 描画モード時はイベントを親に伝播
            event.ignore()
        else:
            # 通常モード時は既存のスクロール処理
            if event.button() == Qt.MouseButton.LeftButton:
                self.mouse_pressed = True
                self.last_pos = event.position().toPoint()  # 修正
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
            else:
                super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_mode_enabled:
            event.ignore()
        else:
            if event.button() == Qt.MouseButton.LeftButton:
                self.mouse_pressed = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
                event.accept()
            else:
                super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """マウス移動時のイベント処理
        ドラッグによるスクロール処理を実装"""
        if self.drawing_mode_enabled:
            event.ignore()
        else:
            if self.mouse_pressed and self.last_pos:
                delta = event.position().toPoint() - self.last_pos  # 修正
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() - delta.y())
                self.last_pos = event.position().toPoint()  # 修正
                event.accept()
            else:
                super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 現在のスケールを考慮して調整
            factor = 1.04 if event.angleDelta().y() > 0 else 0.96
            self.scale_changed.emit(factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def event(self, event):
        # ジェスチャー処理を簡略化
        if event.type() == QEvent.Type.Gesture:
            if gesture := event.gesture(Qt.GestureType.PinchGesture):
                # ピンチジェスチャーのスケール係数をスライダーの単位に合わせて調整
                total_scale = gesture.totalScaleFactor()
                if abs(total_scale - 1.0) > 0.01:
                    # より滑らかなスケーリングのために調整
                    scale = 1.0 + ((total_scale - 1.0) * 0.05)
                    self.scale_changed.emit(scale)
                return True
        return super().event(event)

class DrawableLabel(QLabel):
    """描画可能なラベルクラス"""
    waypoint_clicked = Signal(QPoint)  # ウェイポイト追加用のシグナルを追加
    waypoint_updated = Signal(Waypoint)  # 角度更新用のシグナルを追加
    waypoint_completed = Signal(QPoint)  # 角度確定用のシグナルを追加
    landmark_clicked = Signal(QPoint)
    landmark_updated = Signal(Landmark)
    mouse_position_changed = Signal(QPoint)  # マウス位置シグナルを追加
    waypoint_edited = Signal(Waypoint)  # ウェイポイント編集完了時のシグナル
    landmark_edited = Signal(Landmark)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drawing_enabled = False
        self.parent_viewer = None
        self.cursor_pixmap = None  # カーソル用のピクスマップ
        self.current_cursor_size = 0  # 現在のカーソルサイズ
        self.setMouseTracking(True)
        self.temp_waypoint = None  # 一時的なウェイポイント保存用
        self.temp_landmark = None
        self.is_setting_angle = False  # 角度設定中フラグ
        self.click_pos = None  # クリック位置を保存
        self.edit_mode = False  # 編集モード状態
        self.editing_waypoint = None  # 編集中のウェイポイント
        self.editing_landmark = None
        self.is_dragging = False
        self.drag_start = None
        self.last_pos = None  # Add this line
        self.is_editing_angle = False
        self._drag_offset = (0, 0)  # ドラッグ時に掴んだ位置との相対オフセット（滑らかな移動用）
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # 矢印キーでの微調整用

    def set_drawing_mode(self, enabled):
        self.drawing_enabled = enabled
        if enabled:
            self.updateCursor()  # カーソルを更新
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def updateCursor(self):
        """カーソルを更新"""
        if not self.parent_viewer:
            return

        # 現在のツールのサイズを取得
        size = self.parent_viewer.pen_size if self.parent_viewer.drawing_mode == DrawingMode.PEN else self.parent_viewer.eraser_size
        scaled_size = int(size)  # pen_size/eraser_size は表示単位（ラベル上のピクセル）として扱う
            
        # サイズが変更された場合のみ新しいカーソルを作成
        if (scaled_size != self.current_cursor_size):
            self.current_cursor_size = scaled_size
            # カーソルサイズを実際の描画サイズに合わせて調整（*2を削除）
            cursor_size = max(scaled_size, 8)  # カーソルの最小サイズを8ピクセルに設定
            
            # カーソル用のピクスマップを作成
            self.cursor_pixmap = QPixmap(cursor_size, cursor_size)
            self.cursor_pixmap.fill(Qt.GlobalColor.transparent)
            
            # 円を描画
            painter = QPainter(self.cursor_pixmap)
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(0, 0, cursor_size-1, cursor_size-1)
            painter.end()
            
            # カーソルを設定
            cursor = QCursor(self.cursor_pixmap, cursor_size // 2, cursor_size // 2)
            self.setCursor(cursor)

    def mouseDoubleClickEvent(self, event):
        """ウェイポイントをダブルクリックして編集モードの切り替え"""
        if not self.parent_viewer or self.parent_viewer.drawing_mode != DrawingMode.NONE:
            return
        pos = event.position().toPoint()
        im_pos = self.parent_viewer.display_to_image_coords(pos)
        if im_pos is None:
            return
        x = im_pos.x()
        y = im_pos.y()

        if self.edit_mode and (self.editing_waypoint or self.editing_landmark):
            # 編集モードを終了
            self.edit_mode = False
            self.editing_waypoint = None
            self.editing_landmark = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if self.parent_viewer:
                self.parent_viewer.update_display()  # 表示を更新して赤色に戻す
        else:
            for landmark in self.parent_viewer.landmarks:
                hover_range = max(6, int(WAYPOINT_SETTINGS['BASE_SIZE'] * 1.6))
                if abs(landmark.pixel_x - x) < hover_range and abs(landmark.pixel_y - y) < hover_range:
                    self.edit_mode = True
                    self.editing_waypoint = None
                    self.editing_landmark = landmark
                    self.setFocus(Qt.FocusReason.MouseFocusReason)
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    if self.parent_viewer:
                        self.parent_viewer.show_edit_message("ランドマーク: ドラッグで移動、Shift+ドラッグで角度を変更")
                        self.parent_viewer.update_display()
                    return

            # クリックされた位置にあるウェイポイントを探す
            for waypoint in self.parent_viewer.waypoints:
                hover_range = max(6, int(WAYPOINT_SETTINGS['BASE_SIZE'] * 1.6))
                if abs(waypoint.pixel_x - x) < hover_range and abs(waypoint.pixel_y - y) < hover_range:
                    self.edit_mode = True
                    self.editing_waypoint = waypoint
                    self.setFocus(Qt.FocusReason.MouseFocusReason)
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    # ステータスメッセージを表示
                    if self.parent_viewer:
                        self.parent_viewer.show_edit_message("ドラッグで移動、Shift+ドラッグで角度を変更")
                        self.parent_viewer.update_display()  # 表示を更新して青色に変更
                    break

    def mousePressEvent(self, event):
        if self.drawing_enabled and self.parent_viewer:
            if self.parent_viewer.drawing_mode == DrawingMode.WAYPOINT:
                if event.button() == Qt.MouseButton.LeftButton:
                    pos = event.position().toPoint()
                    self.click_pos = pos  # クリック位置を保存
                    self.is_setting_angle = True
                    self.waypoint_clicked.emit(pos)
            elif self.parent_viewer.drawing_mode == DrawingMode.LANDMARK:
                if event.button() == Qt.MouseButton.LeftButton:
                    pos = event.position().toPoint()
                    self.click_pos = pos
                    self.is_setting_angle = True
                    self.landmark_clicked.emit(pos)
            else:
                pos = event.position().toPoint()
                self.last_pos = pos
                self.parent_viewer.draw_line(pos, pos)  # 点を描画
        elif self.edit_mode and (self.editing_waypoint or self.editing_landmark):
            pos = event.position().toPoint()
            im_pos = self.parent_viewer.display_to_image_coords(pos)
            if im_pos is None:
                return
            x = im_pos.x()
            y = im_pos.y()
            editing_item = self.editing_waypoint or self.editing_landmark

            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shiftキーが押されている場合は角度編集モード
                self.is_editing_angle = True
                self.editing_start_pos = pos
            else:
                # 通常クリックは位置の移動。掴んだ位置との相対オフセットを保持して
                # カーソル位置へジャンプさせず、滑らかに追従させる。
                self._drag_offset = (editing_item.pixel_x - x, editing_item.pixel_y - y)
                self.parent_viewer._edit_dragging = True
                editing_item.set_position(x + self._drag_offset[0], y + self._drag_offset[1])
                if self.parent_viewer:
                    self.parent_viewer.update_display()
                    if self.editing_waypoint:
                        self.parent_viewer.waypoint_edited.emit(self.editing_waypoint)
                    else:
                        self.parent_viewer.landmark_edited.emit(self.editing_landmark)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """マウス移動時のイベント処理"""
        # マウス位置を通知
        pos = event.position().toPoint()
        self.mouse_position_changed.emit(pos)

        if self.parent_viewer and self.parent_viewer.waypoints:
            im_pos = self.parent_viewer.display_to_image_coords(pos)
            if im_pos is None:
                QToolTip.hideText()
                return
            x = im_pos.x()
            y = im_pos.y()

            # ホバー検出範囲を設定（ベースサイズに依存）
            hover_range = max(6, int(WAYPOINT_SETTINGS['BASE_SIZE'] * 1.6))  # ピクセル単位での検出範囲

            for waypoint in self.parent_viewer.waypoints:
                if abs(waypoint.pixel_x - x) < hover_range and abs(waypoint.pixel_y - y) < hover_range:
                        if waypoint.attributes:
                            tooltip = "<b>Actions:</b><br>"
                            for key, value in waypoint.attributes.items():
                                tooltip += f"{key}: {value}"
                                # 最後の要素以外には改行を追加
                                if key != list(waypoint.attributes.keys())[-1]:
                                    tooltip += "<br>"
                            # QPointFからQPointに変換
                            global_pos = QPoint(
                                int(event.globalPosition().x()),
                                int(event.globalPosition().y())
                            )
                            QToolTip.showText(global_pos, tooltip.strip())
                            return
                
                QToolTip.hideText()

        # 既存の描画モード処理を続行
        if self.drawing_enabled and self.parent_viewer:
            if self.is_setting_angle and self.parent_viewer.drawing_mode == DrawingMode.WAYPOINT:
                if self.temp_waypoint and self.click_pos:
                    # プレビュー用の角度計算（Y軸を反転）
                    dx = pos.x() - self.click_pos.x()
                    dy = -(pos.y() - self.click_pos.y())  # Y軸を反転
                    angle = np.arctan2(dy, dx)
                    self.temp_waypoint.set_angle(angle)
                    self.waypoint_updated.emit(self.temp_waypoint)
            elif self.is_setting_angle and self.parent_viewer.drawing_mode == DrawingMode.LANDMARK:
                if self.temp_landmark and self.click_pos:
                    dx = pos.x() - self.click_pos.x()
                    dy = -(pos.y() - self.click_pos.y())
                    angle = np.arctan2(dy, dx)
                    self.temp_landmark.set_angle(angle)
                    self.landmark_updated.emit(self.temp_landmark)
            elif self.last_pos:
                self.parent_viewer.draw_line(self.last_pos, pos)  # 線を描画
                self.last_pos = pos
                self.updateCursor()  # マウス移動時にカーソルを更新
        elif self.edit_mode and (self.editing_waypoint or self.editing_landmark):
            pos = event.position().toPoint()
            im_pos = self.parent_viewer.display_to_image_coords(pos)
            if im_pos is None:
                return
            x = im_pos.x()
            y = im_pos.y()
            editing_item = self.editing_waypoint or self.editing_landmark

            if self.is_editing_angle:
                # 角度の計算
                dx = pos.x() - self.editing_start_pos.x()
                dy = -(pos.y() - self.editing_start_pos.y())  # Y軸を反転
                angle = np.arctan2(dy, dx)
                editing_item.set_angle(angle)
            else:
                # 位置の更新（掴んだ相対オフセットを保持して滑らかに追従）
                editing_item.set_position(x + self._drag_offset[0], y + self._drag_offset[1])

            if self.parent_viewer:
                self.parent_viewer.update_display()
                if self.editing_waypoint:
                    self.parent_viewer.waypoint_edited.emit(self.editing_waypoint)
                else:
                    self.parent_viewer.landmark_edited.emit(self.editing_landmark)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_enabled:
            if self.is_setting_angle and self.click_pos:
                # 最終的な角度計算（Y軸を反転）
                current_pos = event.position().toPoint()  # 修正
                dx = current_pos.x() - self.click_pos.x()
                dy = -(current_pos.y() - self.click_pos.y())  # Y軸を反転
                if self.temp_waypoint:
                    final_angle = np.arctan2(dy, dx)
                    self.temp_waypoint.set_angle(final_angle)
                    self.waypoint_updated.emit(self.temp_waypoint)
                if self.temp_landmark:
                    final_angle = np.arctan2(dy, dx)
                    self.temp_landmark.set_angle(final_angle)
                    self.landmark_updated.emit(self.temp_landmark)
                self.is_setting_angle = False
                self.click_pos = None
                self.temp_waypoint = None
                self.temp_landmark = None
            elif (self.parent_viewer
                    and self.parent_viewer.drawing_mode in (DrawingMode.PEN, DrawingMode.ERASER)):
                # ペン/消しゴムの1ストロークを確定（履歴・地図同期・膨張更新）
                self.parent_viewer.finish_drawing_stroke()
            self.last_pos = None
        elif self.edit_mode and (self.editing_waypoint or self.editing_landmark):
            self.is_editing_angle = False
            if self.parent_viewer:
                self.parent_viewer._edit_dragging = False
                self.parent_viewer.update_display()
                if self.editing_waypoint:
                    self.parent_viewer.waypoint_edited.emit(self.editing_waypoint)
                else:
                    self.parent_viewer.landmark_edited.emit(self.editing_landmark)
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        """編集モード中は矢印キーでWP/ランドマークを1pxずつ微調整（Shiftで10px）。"""
        if self.edit_mode and (self.editing_waypoint or self.editing_landmark):
            step = 10 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 1
            dx = dy = 0
            key = event.key()
            if key == Qt.Key.Key_Left:
                dx = -step
            elif key == Qt.Key.Key_Right:
                dx = step
            elif key == Qt.Key.Key_Up:
                dy = -step  # 画像は下方向が+y
            elif key == Qt.Key.Key_Down:
                dy = step
            if dx or dy:
                item = self.editing_waypoint or self.editing_landmark
                item.set_position(item.pixel_x + dx, item.pixel_y + dy)
                if self.parent_viewer:
                    self.parent_viewer.update_display()
                    if self.editing_waypoint:
                        self.parent_viewer.waypoint_edited.emit(self.editing_waypoint)
                    else:
                        self.parent_viewer.landmark_edited.emit(self.editing_landmark)
                event.accept()
                return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """右クリックメニューの表示"""
        if not self.parent_viewer:
            return

        # クリックされた位置のウェイポイントを探す
        pos = event.pos()
        im_pos = self.parent_viewer.display_to_image_coords(pos)
        if im_pos is None:
            return
        x = im_pos.x()
        y = im_pos.y()

        for waypoint in self.parent_viewer.waypoints:
            hover_range = max(6, int(WAYPOINT_SETTINGS['BASE_SIZE'] * 1.6))
            if abs(waypoint.pixel_x - x) < hover_range and abs(waypoint.pixel_y - y) < hover_range:
                    menu = QMenu(self)
                    menu.setStyleSheet("""
                        QMenu {
                            background-color: #0078d7;
                            color: white;
                        }
                        QMenu::item {
                            background-color: transparent;
                            padding: 5px 20px;
                            color: white;
                            font-weight: bold;
                        }
                        QMenu::item:selected {
                            background-color: #0058a3;
                            color: white;
                        }
                    """)
                    edit_action = menu.addAction("Add Actions") 
                    action = menu.exec(event.globalPos())
                    
                    # ウェイポイントの編集ダイアログを表示
                    if action == edit_action:
                        dialog = AttributeDialog(waypoint, format_manager.get_format(), self)
                        if dialog.exec() == QDialog.DialogCode.Accepted:
                            waypoint.attributes = dialog.get_attributes()
                            self.parent_viewer.update_display()
                            if self.parent_viewer:
                                self.parent_viewer.waypoint_edited.emit(waypoint)
                    break

class Layer(QWidget):  
    """レイヤークラス"""
    changed = Signal()  # レイヤーの状態変更通知用シグナル
    
    def __init__(self, name, visible=True):
        super().__init__()
        self.name = name
        self.visible = visible
        self.pixmap = None
        self.opacity = 1.0

    def set_visible(self, visible):
        if (self.visible != visible):
            self.visible = visible
            self.changed.emit()

    def set_opacity(self, opacity):
        new_opacity = max(0.0, min(1.0, opacity))
        if (self.opacity != new_opacity):
            self.opacity = new_opacity
            self.changed.emit()

class ImageViewer(QWidget):
    """画像表示用ウィジェット
    PGM画像の表示とズーム機能を管理"""
    # スケール変更通知用のシグナルを追加
    scale_changed = Signal(float)
    layer_changed = Signal()  # レイヤーの状態変更通知用
    waypoint_added = Signal(Waypoint)  # ウェイポイント追加通知用のシグナル
    waypoint_removed = Signal(int)  # 削除シグナルを追加
    waypoint_edited = Signal(Waypoint)  # 編集完了シグナルを追加
    landmark_added = Signal(Landmark)
    landmark_removed = Signal(int)
    landmark_edited = Signal(Landmark)
    history_changed = Signal(bool, bool)  # (can_undo, can_redo)
    
    def __init__(self):
        super().__init__()
        self.scale_factor = 1.0  # 画像の拡大率
        self.drawing_mode = DrawingMode.NONE
        self.last_point = None
        self.pen_color = Qt.GlobalColor.black
        self.pen_size = 2       # デフォルトのペンサイズ
        self.eraser_size = 10   # デフォルトの消しゴムサイズ
        self.is_drawing = False  # 描画中フラグを追加
        self.current_drawing_points = []  # 現在の描画ストロークを保存
        
        # スクロールエリアを最初に初期化
        self.scroll_area = CustomScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(600, 400)
        self.scroll_area.setStyleSheet("QScrollArea { border: 2px solid #ccc; background-color: white; }")

        # 座標表示用ラベルを初期化
        self.coord_label = QLabel(self.scroll_area.viewport())
        self.coord_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.8);
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 3px 5px; 
                font-size: 12px;
                font-family: monospace;
                min-height: 40px;
                min-width: 150px;
            }
        """)
        self.coord_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.coord_label.hide()

        # レイヤー管理の初期化
        self.layers = []
        self.active_layer = None
        
        # 基本レイヤーの作成とシグナル接続
        self.roadmap_layer = Layer("Road Map Layer")  # 路面マッピング色付き地図（SLAM地図の下）
        self.pgm_layer = Layer("PGM Layer")
        self.drawing_layer = Layer("Drawing Layer")
        self.waypoint_layer = Layer("Waypoint Layer")
        self.landmark_layer = Layer("Landmark Layer")
        self.origin_layer = Layer("Origin Layer")
        self.path_layer = Layer("Path Layer")
        self.inflation_layer = Layer("Inflation Layer")  # 障害物膨張（Nav2 global costmap相当）
        self.inflation_layer.opacity = 0.2
        self.layers = [
            self.roadmap_layer,   # 0. 路面マップ（最下層・オプション）
            self.pgm_layer,       # 1. PGM画像
            self.drawing_layer,   # 2. ペンと消しゴムの描画
            self.path_layer,      # 3. パス
            self.waypoint_layer,  # 4. ウェイポイント
            self.landmark_layer,  # 5. ランドマーク
            self.origin_layer     # 6. 原点（最上層）
        ]
        self.active_layer = self.drawing_layer
        
        for layer in self.layers:
            layer.changed.connect(self.on_layer_changed)
        
        self.waypoints = []
        self.landmarks = []
        self.waypoint_size = 15
        self.show_grid = False
        self.grid_size = 50
        self.origin_point = None
        self.resolution = 0.05
        self.map_origin = None            # ベース地図のワールド原点 [x, y]（YAMLのorigin）
        self.roadmap_resolution = None    # 路面マップの解像度（colored.json）
        self.roadmap_origin = None        # 路面マップのワールド原点 [x, y]（colored.json）
        self.current_map_yaml_path = None

        # 障害物膨張（Nav2 global_costmap の inflation_layer 相当）
        # デフォルト値はシリウスの params/nav2_params.yaml (global_costmap) と同じ。
        self.map_image_array = None           # ベースPGMのグレースケール配列
        self.inflation_enabled = False        # 膨張表示のオン/オフ
        self.inflation_radius = 0.75          # inflation_radius [m]
        self.inflation_cost_scaling = 3.0     # cost_scaling_factor
        self.inflation_inscribed_radius = 0.35  # 内接半径 [m]（フットプリント由来）
        self.inflation_occupied_thresh = 0.65  # ROS map YAML の occupied_thresh
        self.inflation_negate = 0              # ROS map YAML の negate
        self._inflation_params_key = None
        self._inflation_rgba = None            # 膨張オーバーレイのRGBAキャッシュ（局所更新用）
        self._inflation_cost = None            # 膨張コストグリッド(0-254)（パス計画用）
        self._inflation_cost_key = None
        self._inflation_timer = QTimer(self)
        self._inflation_timer.setSingleShot(True)
        self._inflation_timer.setInterval(250)
        self._inflation_timer.timeout.connect(self.recompute_inflation)

        # 各コンポーネントの設定
        self.setup_display()
        self.setup_scroll_area()
        self.setup_drawing_tools()

        # シグナルを接続
        self.pgm_display.waypoint_edited.connect(self.handle_waypoint_edited)
        self.pgm_display.landmark_edited.connect(self.handle_landmark_edited)
        self.scroll_area.scale_changed.connect(self.handle_scale_change)

        # 履歴管理用の変数を追加
        self.history = []  # 操作履歴
        self.current_index = -1  # 現在の履歴インデックス
        self.max_history = 10  # 最大履歴数（メモリ節約のため削減）
        
        # パフォーマンス最適化用の変数
        self._is_drawing_stroke = False  # ストローク描画中フラグ
        self._edit_dragging = False      # WP/ランドマークのドラッグ中フラグ（ドラッグ中は高速描画）
        self._stroke_old_pixmap = None   # ストローク開始時のpixmap
        self._stroke_old_map = None      # 消しゴム用: ストローク開始時の地図配列
        self._stroke_erase_bbox = None   # 消しゴム用: 消去した範囲 [x0, y0, x1, y1]
        self._update_pending = False     # 更新待ちフラグ
        self._cached_result = None       # 合成結果キャッシュ
        self._cache_valid = False        # キャッシュ有効フラグ

    def setup_display(self):
        """画像表示用ラベルの設定を集約"""
        self.pgm_display = DrawableLabel()
        self.pgm_display.parent_viewer = self
        self.pgm_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pgm_display.setStyleSheet("background-color: white;")
        self.pgm_display.waypoint_clicked.connect(self.add_waypoint)
        self.pgm_display.waypoint_updated.connect(self.update_waypoint)
        self.pgm_display.landmark_clicked.connect(self.add_landmark)
        self.pgm_display.landmark_updated.connect(self.update_landmark)
        self.pgm_display.mouse_position_changed.connect(self.update_mouse_position)

        # ステータスメッセージ用のラベルを設定
        self.status_label = QLabel(self.scroll_area.viewport())
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
        self.status_label.hide()

        # スクロールエリアにpgm_displayを設定
        self.scroll_area.setWidget(self.pgm_display)

    def setup_scroll_area(self):
        """スクロールエリアの設定を集約"""
        self.scroll_area.scale_changed.connect(self.handle_scale_change)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.scroll_area)

        # 座標表示用ラベルをスクロールエリアのビューポートの子として設定
        self.coord_label.setParent(self.scroll_area.viewport())
        self.coord_label.hide()  # 初期状態では非表示

        # ステータスメッセージ用のラベルをスクロールエリアのビューポートの子として設定
        self.status_label = QLabel()
        self.status_label.setParent(self.scroll_area.viewport())
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
        self.status_label.hide()

        # スクロールエリアのリサイズイベントをオーバーライド
        original_resize_event = self.scroll_area.resizeEvent
        def new_resize_event(event):
            original_resize_event(event)
            # 座標ラベルを右上に配置（右端から30ピクセル離す）
            label_width = 150
            label_height = 40  # min-heightに合わせて調整
            new_x = self.scroll_area.viewport().width() - label_width - 30  # 30ピクセル左に移動
            new_y = 10  # 上端から10ピクセルの位置
            self.coord_label.setGeometry(new_x, new_y, label_width, label_height)
            
            # ステータスメッセージを下部中央に配置
            status_width = 300
            status_height = 30
            status_x = (self.scroll_area.viewport().width() - status_width) // 2
            status_y = self.scroll_area.viewport().height() - status_height - 10  # 下部に10ピクセルのマージン
            self.status_label.setGeometry(status_x, status_y, status_width, status_height)
            
            self.coord_label.raise_()
            self.status_label.raise_()
        self.scroll_area.resizeEvent = new_resize_event

    def show_edit_message(self, message):
        """編集時のヘルプメッセージを表示"""
        # メッセージの表示位置を調整（ビューアーの中央下）
        self.status_label.setText(message)
        self.status_label.adjustSize()
        
        # スクロールエリアのビューポート内での位置を計算
        viewport = self.scroll_area.viewport()
        x = (viewport.width() - self.status_label.width()) // 2
        y = viewport.height() - self.status_label.height() - 20  # 下端から20ピクセル上
        
        self.status_label.move(x, y)
        self.status_label.show()
        self.status_label.raise_()  # 最前面に表示
        
        # 3秒後にメッセージを非表示
        QTimer.singleShot(3000, self.status_label.hide)

    def setup_drawing_tools(self):
        """描画ツールの設定"""
        tools_layout = QVBoxLayout()
        
        # ボタンのレイアウト
        buttons_layout = QHBoxLayout()
        
        # ペンボタン
        self.pen_button = QPushButton("ペン")
        self.pen_button.setCheckable(True)
        self.pen_button.clicked.connect(lambda: self.set_drawing_mode(DrawingMode.PEN))
        
        # 消しゴムボタン
        self.eraser_button = QPushButton("消しゴム")
        self.eraser_button.setCheckable(True)
        self.eraser_button.clicked.connect(lambda: self.set_drawing_mode(DrawingMode.ERASER))
        
        # ウェイポイントボタンを追加
        self.waypoint_button = QPushButton("ウェイポイント")
        self.waypoint_button.setCheckable(True)
        self.waypoint_button.clicked.connect(lambda: self.set_drawing_mode(DrawingMode.WAYPOINT))

        self.landmark_button = QPushButton("ランドマーク")
        self.landmark_button.setCheckable(True)
        self.landmark_button.clicked.connect(lambda: self.set_drawing_mode(DrawingMode.LANDMARK))
        
        buttons_layout.addWidget(self.pen_button)
        buttons_layout.addWidget(self.eraser_button)
        buttons_layout.addWidget(self.waypoint_button)
        buttons_layout.addWidget(self.landmark_button)
        
        # スライダーのレイアウト
        sliders_layout = QHBoxLayout()
        
        # ペンの太さスライダー
        pen_slider_layout = QVBoxLayout()
        pen_slider_label = QLabel("ペンの太さ")
        self.pen_slider = QSlider(Qt.Orientation.Horizontal)
        self.pen_slider.setRange(1, 20)
        self.pen_slider.setValue(self.pen_size)
        self.pen_slider.valueChanged.connect(self.set_pen_size)
        pen_slider_layout.addWidget(pen_slider_label)
        pen_slider_layout.addWidget(self.pen_slider)
        
        # 消しゴムの太さスライダー
        eraser_slider_layout = QVBoxLayout()
        eraser_slider_label = QLabel("消しゴムの太さ")
        self.eraser_slider = QSlider(Qt.Orientation.Horizontal)
        self.eraser_slider.setRange(5, 50)
        self.eraser_slider.setValue(self.eraser_size)
        self.eraser_slider.valueChanged.connect(self.set_eraser_size)
        eraser_slider_layout.addWidget(eraser_slider_label)
        eraser_slider_layout.addWidget(self.eraser_slider)
        
        # スライダーをレイアウトに追加
        sliders_layout.addLayout(pen_slider_layout)
        sliders_layout.addLayout(eraser_slider_layout)
        
        # メインレイアウトに追加
        tools_layout.addLayout(buttons_layout)
        tools_layout.addLayout(sliders_layout)
        self.layout().insertLayout(0, tools_layout)

    def set_pen_size(self, size):
        """ペンの太さを設定"""
        self.pen_size = size
        if self.drawing_mode == DrawingMode.PEN:
            self.pgm_display.updateCursor()

    def set_eraser_size(self, size):
        """消しゴムの太さを設定"""
        self.eraser_size = size
        if self.drawing_mode == DrawingMode.ERASER:
            self.pgm_display.updateCursor()

    def set_drawing_mode(self, mode):
        """描画モードの切り替え"""
        # 同じモードを選択した場合は描画モードを解除
        if self.drawing_mode == mode:
            self.drawing_mode = DrawingMode.NONE
            self.pen_button.setChecked(False)
            self.eraser_button.setChecked(False)
            self.waypoint_button.setChecked(False)
            self.landmark_button.setChecked(False)
            self.pgm_display.set_drawing_mode(False)
            self.scroll_area.set_drawing_mode(False)
            return

        # 異なるモードを選択した場合は描画モードを変更
        self.drawing_mode = mode
        self.pen_button.setChecked(mode == DrawingMode.PEN)
        self.eraser_button.setChecked(mode == DrawingMode.ERASER)
        self.waypoint_button.setChecked(mode == DrawingMode.WAYPOINT)
        self.landmark_button.setChecked(mode == DrawingMode.LANDMARK)
        
        # ラベルの描画モードを設定
        self.pgm_display.set_drawing_mode(mode != DrawingMode.NONE)
        # スクロールエリアの描画モードを設定
        self.scroll_area.set_drawing_mode(mode != DrawingMode.NONE)
        # カーソルを更新
        if (mode != DrawingMode.NONE):
            if mode in (DrawingMode.WAYPOINT, DrawingMode.LANDMARK):
                self.pgm_display.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.pgm_display.updateCursor()

    def draw_line(self, start_pos, end_pos):
        """2点間に線を描画"""
        if not self.drawing_layer.pixmap or self.drawing_mode == DrawingMode.NONE:
            return

        # ストローク開始時のみpixmapを保存（メモリ節約）
        if not self._is_drawing_stroke:
            self._is_drawing_stroke = True
            self._stroke_old_pixmap = self.drawing_layer.pixmap.copy()
            self._stroke_erase_bbox = None
            if self.drawing_mode == DrawingMode.ERASER and self.map_image_array is not None:
                # 消しゴムは地図（障害物）を実際に消すため、元の地図配列を退避する
                self._stroke_old_map = self.map_image_array.copy()

        # 開始/終了位置を画像ピクセル座標に変換
        start_img = self.display_to_image_coords(start_pos)
        end_img = self.display_to_image_coords(end_pos)
        if start_img is None or end_img is None:
            return
        scaled_start = start_img
        scaled_end = end_img

        # スケールに応じて描画サイズを調整（表示単位 -> 画像ピクセル単位）
        if self.pgm_display.pixmap() and self.pgm_layer.pixmap:
            orig_w = self.pgm_layer.pixmap.width()
            disp_w = self.pgm_display.pixmap().width()
            scale_factor = orig_w / disp_w if disp_w else 1.0
        else:
            scale_factor = 1.0
        scaled_pen_size = max(1, int(self.pen_size * scale_factor))
        scaled_eraser_size = max(1, int(self.eraser_size * scale_factor))

        if self.drawing_mode == DrawingMode.PEN:
            painter = QPainter(self.drawing_layer.pixmap)
            painter.setPen(QPen(self.pen_color, scaled_pen_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(scaled_start, scaled_end)
            painter.end()
        else:  # ERASER
            # 描画レイヤーはペン跡を透明に消す
            painter = QPainter(self.drawing_layer.pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.setPen(QPen(Qt.GlobalColor.black, scaled_eraser_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(scaled_start, scaled_end)
            painter.end()

            # ベース地図の障害物を自由空間(白)に置き換える（コストマップ/膨張に反映）
            if self.pgm_layer.pixmap is not None:
                map_painter = QPainter(self.pgm_layer.pixmap)
                map_painter.setPen(QPen(Qt.GlobalColor.white, scaled_eraser_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                map_painter.drawLine(scaled_start, scaled_end)
                map_painter.end()
                self._extend_erase_bbox(scaled_start, scaled_end, scaled_eraser_size)

        # キャッシュを無効化
        self._cache_valid = False
        self.update_display()

    def _extend_erase_bbox(self, start, end, size):
        """消しゴムで消した範囲を記録する（履歴・配列同期用）"""
        if self.pgm_layer.pixmap is None:
            return
        half = size // 2 + 2
        width = self.pgm_layer.pixmap.width()
        height = self.pgm_layer.pixmap.height()
        x0 = max(0, min(start.x(), end.x()) - half)
        y0 = max(0, min(start.y(), end.y()) - half)
        x1 = min(width, max(start.x(), end.x()) + half)
        y1 = min(height, max(start.y(), end.y()) + half)
        if self._stroke_erase_bbox is None:
            self._stroke_erase_bbox = [x0, y0, x1, y1]
        else:
            b = self._stroke_erase_bbox
            b[0] = min(b[0], x0)
            b[1] = min(b[1], y0)
            b[2] = max(b[2], x1)
            b[3] = max(b[3], y1)

    def _sync_map_array_region(self, bbox):
        """ベース地図ピクスマップの指定領域だけを計算用の地図配列へ反映する（高速）。"""
        if self.map_image_array is None or self.pgm_layer.pixmap is None:
            return
        x0, y0, x1, y1 = bbox
        width = x1 - x0
        height = y1 - y0
        if width <= 0 or height <= 0:
            return
        sub = self.pgm_layer.pixmap.copy(x0, y0, width, height).toImage().convertToFormat(
            QImage.Format.Format_Grayscale8)
        bytes_per_line = sub.bytesPerLine()
        buffer = np.frombuffer(sub.constBits(), dtype=np.uint8)
        if buffer.size < bytes_per_line * height:
            return
        rows = buffer[:bytes_per_line * height].reshape(height, bytes_per_line)[:, :width]
        self.map_image_array[y0:y1, x0:x1] = rows

    def _sync_map_array_from_pixmap(self):
        """ベース地図ピクスマップの内容を計算用の地図配列へ反映する。"""
        if self.map_image_array is None or self.pgm_layer.pixmap is None:
            return
        image = self.pgm_layer.pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine()
        buffer = np.frombuffer(image.constBits(), dtype=np.uint8)
        if buffer.size < bytes_per_line * height:
            return
        rows = buffer[:bytes_per_line * height].reshape(height, bytes_per_line)
        self.map_image_array = np.ascontiguousarray(rows[:, :width]).copy()

    def _refresh_pgm_pixmap_from_array(self):
        """計算用の地図配列からベース地図ピクスマップを再生成する（Undo/Redo用）。"""
        array = self.map_image_array
        if array is None:
            return
        height, width = array.shape
        q_img = QImage(array.data, width, height, width, QImage.Format.Format_Grayscale8)
        self.pgm_layer.pixmap = QPixmap.fromImage(q_img)

    def mousePressEvent(self, event):
        if self.drawing_mode != DrawingMode.NONE:
            self.last_point = event.position().toPoint()  # 修正
            self.draw_line(event.position().toPoint(), event.position().toPoint())  # 修正
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_mode != DrawingMode.NONE and self.last_point:
            current_pos = event.position().toPoint()  # 修正
            self.draw_line(self.last_point, current_pos)
            self.last_point = current_pos
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_mode != DrawingMode.NONE:
            self.finish_drawing_stroke()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def finish_drawing_stroke(self):
        """描画/消しゴムの1ストロークを確定する。

        DrawableLabel側でマウスイベントを処理しているため、ストローク終了時は
        ここを呼び出して履歴保存・地図同期・膨張の再計算を行う。
        """
        if not self._is_drawing_stroke:
            self.last_point = None
            return
        if self._stroke_old_pixmap is not None:
            action = {
                'type': 'draw',
                'old_pixmap': self._stroke_old_pixmap,
                'new_pixmap': self.drawing_layer.pixmap.copy()
            }
            # 消しゴムは地図の障害物も消しているため、変更範囲を履歴に残す
            if (self.drawing_mode == DrawingMode.ERASER and self._stroke_old_map is not None
                    and self._stroke_erase_bbox is not None):
                x0, y0, x1, y1 = self._stroke_erase_bbox
                self._sync_map_array_region((x0, y0, x1, y1))
                action['map_bbox'] = (x0, y0, x1, y1)
                action['map_old'] = self._stroke_old_map[y0:y1, x0:x1].copy()
                action['map_new'] = self.map_image_array[y0:y1, x0:x1].copy()
                self._inflation_params_key = None
                if self.inflation_enabled:
                    # 影響範囲だけ再計算するため、消した直後でも高速に反映される
                    self._update_inflation_region((x0, y0, x1, y1))
            self.add_to_history(action)
            self._stroke_old_pixmap = None
            self._stroke_old_map = None
            self._stroke_erase_bbox = None
        self._is_drawing_stroke = False
        self.last_point = None
        self.update_display()

    def load_image(self, img_array, width, height):
        """PGM画像データを読み込んでPGMレイヤーに設定"""
        bytes_per_line = width
        q_img = QImage(img_array.data, width, height, bytes_per_line,
                    QImage.Format.Format_Grayscale8)
        self.pgm_layer.pixmap = QPixmap.fromImage(q_img)
        self.drawing_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
        self.drawing_layer.pixmap.fill(Qt.GlobalColor.transparent)
        # 障害物膨張の計算用にグレースケール配列を保持する
        self.map_image_array = np.ascontiguousarray(img_array, dtype=np.uint8).copy()
        self.inflation_layer.pixmap = None
        self._inflation_params_key = None
        self._inflation_rgba = None
        self._inflation_cost = None
        self._inflation_cost_key = None
        self.update_display()
        self.coord_label.show()  # 画像読み込み時に座標表示を有効化
        if self.inflation_enabled:
            # YAMLのresolution等が設定された後に再計算されるようデバウンスする
            self._inflation_timer.start()

    def set_inflation(self, enabled, radius, cost_scaling, inscribed, opacity_percent):
        """RightPanelから膨張設定を受け取り、必要なら再計算する。"""
        self.inflation_enabled = bool(enabled)
        self.inflation_radius = max(0.0, float(radius))
        self.inflation_cost_scaling = max(0.0, float(cost_scaling))
        self.inflation_inscribed_radius = max(0.0, float(inscribed))
        self.inflation_layer.opacity = max(0.0, min(1.0, float(opacity_percent) / 100.0))

        if not self.inflation_enabled:
            self._inflation_timer.stop()
            self.inflation_layer.pixmap = None
            self.update_display()
            return

        new_key = (
            round(self.inflation_radius, 4),
            round(self.inflation_cost_scaling, 4),
            round(self.inflation_inscribed_radius, 4),
            round(float(self.resolution or 0.0), 6),
            None if self.map_image_array is None else self.map_image_array.shape,
        )
        if self.inflation_layer.pixmap is not None and new_key == self._inflation_params_key:
            # パラメータが同じ（不透明度のみ変更）なら再計算せず再描画のみ
            self.update_display()
            return
        self._inflation_params_key = new_key
        self._inflation_timer.start()

    def recompute_inflation(self):
        """Nav2のinflation_layer相当の膨張マップを生成する。"""
        self._inflation_timer.stop()
        if not self.inflation_enabled or self.map_image_array is None:
            self.inflation_layer.pixmap = None
            self.update_display()
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.inflation_layer.pixmap = self._build_inflation_pixmap()
        except Exception as exc:  # 予期せぬデータでもアプリを落とさない
            print(f"Inflation error: {exc}")
            import traceback
            traceback.print_exc()
            self.inflation_layer.pixmap = None
        finally:
            QApplication.restoreOverrideCursor()
        self.update_display()

    def _occupied_mask(self, image):
        """ROS map規約(negate対応)で占有セルのマスクを作る。"""
        pixels = image.astype(np.float32) / 255.0
        occupied_prob = pixels if self.inflation_negate else (1.0 - pixels)
        return occupied_prob >= float(self.inflation_occupied_thresh)

    def _compute_inflation_cost(self, occupied, resolution, radius_m, cost_scaling, inscribed_m):
        """Nav2 inflation_layer と同じコスト値(0-254)を計算する。"""
        height, width = occupied.shape
        max_cells = int(np.ceil(radius_m / resolution)) if radius_m > 0 else 0

        # 水平方向の距離（同一行内の最近傍障害物までのセル数）を厳密に求める
        inf = np.float32(np.inf)
        idx = np.arange(width, dtype=np.float32)
        left_src = np.where(occupied, idx, np.float32(-1.0))
        nearest_left = np.maximum.accumulate(left_src, axis=1)
        right_src = np.where(occupied, idx, np.float32(width))
        nearest_right = np.minimum.accumulate(right_src[:, ::-1], axis=1)[:, ::-1]
        d_left = np.where(nearest_left >= 0.0, idx - nearest_left, inf)
        d_right = np.where(nearest_right < width, nearest_right - idx, inf)
        horizontal = np.minimum(d_left, d_right).astype(np.float32)

        # 2Dユークリッド距離変換（分離可能）。膨張半径分だけ走査すれば十分。
        if max_cells > 0:
            padded = np.full((height + 2 * max_cells, width), inf, dtype=np.float32)
            padded[max_cells:max_cells + height, :] = horizontal
            dist_sq = np.full((height, width), inf, dtype=np.float32)
            for dy in range(-max_cells, max_cells + 1):
                block = padded[max_cells + dy:max_cells + dy + height, :]
                np.minimum(dist_sq, block * block + np.float32(dy * dy), out=dist_sq)
            dist_cells = np.sqrt(dist_sq)
        else:
            dist_cells = horizontal

        dist_m = dist_cells * resolution

        # Nav2 inflation_layer と同じコスト計算
        cost = np.zeros((height, width), dtype=np.uint8)
        inflated = (~occupied) & (dist_m <= radius_m)
        if inflated.any():
            if cost_scaling > 0.0:
                decay = np.exp(-cost_scaling * (dist_m[inflated] - inscribed_m))
            else:
                decay = np.ones(int(inflated.sum()), dtype=np.float32)
            cost[inflated] = np.clip((decay * 252.0).astype(np.int32), 1, 252).astype(np.uint8)
        cost[(~occupied) & (dist_m <= inscribed_m)] = 253
        cost[occupied] = 254
        return cost

    def _cost_to_rgba(self, cost):
        """RVizのcostmap配色でコスト値をRGBAへ変換する。"""
        height, width = cost.shape
        #   1-252(膨張): 青(低コスト/外側) -> 赤(高コスト/障害物付近)
        #   253(内接): シアン, 254(致死): 紫
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        inflated_mask = (cost >= 1) & (cost <= 252)
        if inflated_mask.any():
            v = (255.0 * cost[inflated_mask].astype(np.float32) / 252.0).astype(np.uint8)
            rgba[inflated_mask, 0] = v
            rgba[inflated_mask, 1] = 0
            rgba[inflated_mask, 2] = (255 - v).astype(np.uint8)
            rgba[inflated_mask, 3] = 255
        rgba[cost == 253] = (0, 255, 255, 255)   # 内接: シアン
        rgba[cost == 254] = (255, 0, 255, 255)   # 致死: 紫
        return rgba

    @staticmethod
    def _rgba_to_pixmap(rgba):
        height, width = rgba.shape[:2]
        buffer = np.ascontiguousarray(rgba).tobytes()
        q_img = QImage(buffer, width, height, 4 * width, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(q_img)

    def _build_inflation_pixmap(self):
        """地図全体の膨張オーバーレイを計算し、コスト/RGBAキャッシュも更新する。"""
        image = self.map_image_array
        if image is None or image.ndim != 2:
            self._inflation_rgba = None
            self._inflation_cost = None
            return None
        resolution = float(self.resolution) if self.resolution and self.resolution > 0 else 0.05
        occupied = self._occupied_mask(image)
        if not occupied.any():
            self._inflation_rgba = None
            self._inflation_cost = None
            return None
        radius_m = self.inflation_radius
        inscribed_m = min(self.inflation_inscribed_radius, radius_m)
        cost = self._compute_inflation_cost(
            occupied, resolution, radius_m, self.inflation_cost_scaling, inscribed_m
        )
        self._inflation_cost = cost
        self._inflation_cost_key = self._inflation_cache_key()
        rgba = self._cost_to_rgba(cost)
        self._inflation_rgba = rgba
        return self._rgba_to_pixmap(rgba)

    def _inflation_cache_key(self):
        """膨張コストのキャッシュが有効かを判定するためのキー。"""
        return (
            None if self.map_image_array is None else self.map_image_array.shape,
            round(float(self.resolution or 0.0), 6),
            round(float(self.inflation_radius), 4),
            round(float(self.inflation_cost_scaling), 4),
            round(float(self.inflation_inscribed_radius), 4),
            round(float(self.inflation_occupied_thresh), 4),
            int(self.inflation_negate),
        )

    def _ensure_cost_grid(self):
        """パス計画用の膨張コストグリッド(0-254)を取得する（必要なら計算）。"""
        if self.map_image_array is None:
            return None
        key = self._inflation_cache_key()
        if self._inflation_cost is not None and self._inflation_cost_key == key:
            return self._inflation_cost
        resolution = float(self.resolution) if self.resolution and self.resolution > 0 else 0.05
        occupied = self._occupied_mask(self.map_image_array)
        radius_m = self.inflation_radius
        inscribed_m = min(self.inflation_inscribed_radius, radius_m)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            cost = self._compute_inflation_cost(
                occupied, resolution, radius_m, self.inflation_cost_scaling, inscribed_m
            )
        finally:
            QApplication.restoreOverrideCursor()
        self._inflation_cost = cost
        self._inflation_cost_key = key
        return cost

    def _update_inflation_region(self, bbox):
        """消去などで変化した局所領域だけ膨張オーバーレイを再計算する。

        膨張の影響は半径ぶん広がるため、更新領域を半径で外側に広げて計算し、
        境界誤差が出ない内側部分だけをキャッシュとピクスマップへ反映する。
        """
        if self.map_image_array is None:
            return
        resolution = float(self.resolution) if self.resolution and self.resolution > 0 else 0.05
        radius_m = self.inflation_radius
        inscribed_m = min(self.inflation_inscribed_radius, radius_m)
        r_cells = int(np.ceil(radius_m / resolution)) if radius_m > 0 else 0
        height, width = self.map_image_array.shape

        x0, y0, x1, y1 = bbox
        ix0 = max(0, x0 - r_cells); iy0 = max(0, y0 - r_cells)
        ix1 = min(width, x1 + r_cells); iy1 = min(height, y1 + r_cells)
        wx0 = max(0, ix0 - r_cells); wy0 = max(0, iy0 - r_cells)
        wx1 = min(width, ix1 + r_cells); wy1 = min(height, iy1 + r_cells)
        if wx1 <= wx0 or wy1 <= wy0:
            return

        sub_image = self.map_image_array[wy0:wy1, wx0:wx1]
        occupied = self._occupied_mask(sub_image)
        sub_cost = self._compute_inflation_cost(
            occupied, resolution, radius_m, self.inflation_cost_scaling, inscribed_m
        )
        inner_cost = sub_cost[iy0 - wy0:iy1 - wy0, ix0 - wx0:ix1 - wx0]

        if self._inflation_rgba is None or self._inflation_rgba.shape != (height, width, 4):
            # キャッシュが無い場合は全体を計算し直す
            self.inflation_layer.pixmap = self._build_inflation_pixmap()
            return

        self._inflation_rgba[iy0:iy1, ix0:ix1] = self._cost_to_rgba(inner_cost)
        if self._inflation_cost is not None and self._inflation_cost.shape == (height, width):
            self._inflation_cost[iy0:iy1, ix0:ix1] = inner_cost
        if self.inflation_layer.pixmap is None:
            self.inflation_layer.pixmap = self._rgba_to_pixmap(self._inflation_rgba)
        else:
            inner_rgba = np.ascontiguousarray(self._inflation_rgba[iy0:iy1, ix0:ix1])
            inner_bytes = inner_rgba.tobytes()
            q_img = QImage(inner_bytes, ix1 - ix0, iy1 - iy0,
                           4 * (ix1 - ix0), QImage.Format.Format_RGBA8888)
            painter = QPainter(self.inflation_layer.pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.drawImage(ix0, iy0, q_img)
            painter.end()

    def zoom_in(self):
        self.scale_factor *= 1.2
        self.update_display()

    def zoom_out(self):
        self.scale_factor /= 1.2
        self.update_display()

    def zoom_reset(self):
        self.scale_factor = 1.0
        self.update_display()

    def handle_scale_change(self, factor):
        """ジェスチャーやホイールによるスケール変更を処理"""
        new_scale = self.scale_factor * factor
        if MIN_SCALE <= new_scale <= MAX_SCALE:
            self.scale_factor = new_scale
            self.update_display()
            self.scale_changed.emit(self.scale_factor)
            # スケール変更時にカーソルを更新
            if self.drawing_mode != DrawingMode.NONE:
                self.pgm_display.updateCursor()

    def add_waypoint(self, pos):
        """ウェイポイントを追加"""
        if not self.pgm_layer.pixmap:
            return

        # 表示座標 -> 画像上のピクセル座標に変換
        im_pos = self.display_to_image_coords(pos)
        if im_pos is None:
            return  # 画像外クリックは無視
        x = im_pos.x()
        y = im_pos.y()
        
        waypoint = Waypoint(x, y)
        
        # 原点が設定されている場合は、メートル座標を計算
        if self.origin_point:
            origin_x, origin_y = self.origin_point
            waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
            
        self.waypoints.append(waypoint)
        self.pgm_display.temp_waypoint = waypoint
        
        # ウェイポイントレイヤーの初期化（必要な場合）
        if not self.waypoint_layer.pixmap:
            self.waypoint_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
            self.waypoint_layer.pixmap.fill(Qt.GlobalColor.transparent)
        
        self.waypoint_added.emit(waypoint)
        self.update_display()

        # 履歴に追加
        self.add_to_history({
            'type': 'waypoint_add',
            'waypoint': waypoint
        })

    def update_waypoint(self, waypoint):
        """ウェイポイントの更新（角度変更時）"""
        self.update_display()
        # 対応するラベルを更新するためにシグナルを再発行
        self.waypoint_added.emit(waypoint)

    def add_landmark(self, pos):
        """ランドマークを追加"""
        if not self.pgm_layer.pixmap:
            return

        im_pos = self.display_to_image_coords(pos)
        if im_pos is None:
            return

        landmark = Landmark(im_pos.x(), im_pos.y())
        if self.origin_point:
            origin_x, origin_y = self.origin_point
            landmark.update_metric_coordinates(origin_x, origin_y, self.resolution)

        self.landmarks.append(landmark)
        self.pgm_display.temp_landmark = landmark

        if not self.landmark_layer.pixmap:
            self.landmark_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
            self.landmark_layer.pixmap.fill(Qt.GlobalColor.transparent)

        self.landmark_added.emit(landmark)
        self.update_display()
        self.add_to_history({
            'type': 'landmark_add',
            'landmark': landmark
        })

    def update_landmark(self, landmark):
        """ランドマークの更新（角度変更時）"""
        if self.origin_point:
            origin_x, origin_y = self.origin_point
            landmark.update_metric_coordinates(origin_x, origin_y, self.resolution)
        self.update_display()
        self.landmark_edited.emit(landmark)

    def render_composite_pixmap(self):
        """全レイヤーを実寸（元地図サイズ）で合成したピクスマップを生成する。

        表示と画像保存（地図全体の写真）で共用する。地図・路面マッピング・
        描画・パス・ウェイポイント・ランドマーク・原点を含む。
        """
        if not self.pgm_layer.pixmap:
            return None

        # 合成用の新しいピクスマップを作成
        result = QPixmap(self.pgm_layer.pixmap.size())
        result.fill(Qt.GlobalColor.white)
        
        painter = QPainter(result)
        
        # 0. 路面マップレイヤーを描画（最下層・原点合わせ）
        if self.roadmap_layer.visible and self.roadmap_layer.pixmap:
            self._draw_roadmap(painter, result.size())

        # 1. PGMレイヤーを描画
        if (self.pgm_layer.visible and self.pgm_layer.pixmap):
            painter.setOpacity(self.pgm_layer.opacity)
            painter.drawPixmap(0, 0, self.pgm_layer.pixmap)

        # 1b. 障害物膨張レイヤー（Nav2 global costmap相当・赤=致死/内接、青=膨張）
        if (self.inflation_enabled and self.inflation_layer.visible
                and self.inflation_layer.pixmap):
            painter.setOpacity(self.inflation_layer.opacity)
            painter.drawPixmap(0, 0, self.inflation_layer.pixmap)

        # 2. グリッドの描画
        if self.show_grid:
            painter.setOpacity(0.3)
            pen = QPen(Qt.GlobalColor.gray)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            for x in range(0, result.width(), self.grid_size):
                painter.drawLine(x, 0, x, result.height())
            for y in range(0, result.height(), self.grid_size):
                painter.drawLine(0, y, result.width(), y)

        # 3. 描画レイヤーを描画
        if self.drawing_layer.visible and self.drawing_layer.pixmap:
            painter.setOpacity(self.drawing_layer.opacity)
            painter.drawPixmap(0, 0, self.drawing_layer.pixmap)

        # 4. パスレイヤーを描画
        if self.path_layer.visible and self.path_layer.pixmap:
            painter.setOpacity(self.path_layer.opacity)
            painter.drawPixmap(0, 0, self.path_layer.pixmap)

        # 5. ウェイポイントレイヤーを描画
        if self.waypoints and self.waypoint_layer.visible:
            painter.setOpacity(self.waypoint_layer.opacity)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            for waypoint in self.waypoints:
                x, y = waypoint.pixel_x, waypoint.pixel_y
                base_size = WAYPOINT_SETTINGS['BASE_SIZE']
                
                # 編集中のウェイポイントは特別な表示
                is_editing = (self.pgm_display.edit_mode and 
                            self.pgm_display.editing_waypoint and 
                            self.pgm_display.editing_waypoint.number == waypoint.number)
                
                # 編集中は青、手動記録(manual)は緑、それ以外は赤で表示
                is_manual = bool(waypoint.get_attribute('manual', False))
                if is_editing:
                    color = QColor(0, 120, 255, 255)
                elif is_manual:
                    color = QColor(0, 170, 0, 255)
                else:
                    color = QColor(255, 0, 0, 255)
                size_multiplier = WAYPOINT_SETTINGS['EDIT_SIZE_MULT'] if is_editing else 1.0
                
                # 矢印の描画
                pen = QPen(color)
                pen.setWidth(3)
                painter.setPen(pen)
                
                adjusted_size = base_size * size_multiplier
                angle_line_length = adjusted_size * WAYPOINT_SETTINGS['ARROW_LENGTH_MULT'] # 矢印の長さ
                end_x = x + int(angle_line_length * np.cos(waypoint.angle))
                end_y = y - int(angle_line_length * np.sin(waypoint.angle))
                painter.drawLine(x, y, end_x, end_y)

                # 矢印の先端
                arrow_size = adjusted_size * WAYPOINT_SETTINGS['ARROW_WIDTH_MULT']
                arrow_angle1 = waypoint.angle + np.pi * 3/4
                arrow_angle2 = waypoint.angle - np.pi * 3/4
                
                arrow_x1 = end_x + int(arrow_size * np.cos(arrow_angle1))
                arrow_y1 = end_y - int(arrow_size * np.sin(arrow_angle1))
                arrow_x2 = end_x + int(arrow_size * np.cos(arrow_angle2))
                arrow_y2 = end_y - int(arrow_size * np.sin(arrow_angle2))
                
                painter.drawLine(end_x, end_y, arrow_x1, arrow_y1)
                painter.drawLine(end_x, end_y, arrow_x2, arrow_y2)
                
                # 円を描画
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(x - adjusted_size, y - adjusted_size, 
                                  adjusted_size * 2, adjusted_size * 2)
                
                # 番号を描画
                painter.setPen(QColor(255, 255, 255, 230))
                font = self.font()
                font.setPointSize(WAYPOINT_SETTINGS['FONT_SIZE_MAIN_MULT'] * WAYPOINT_SETTINGS['BASE_SIZE'])
                font.setBold(True)
                painter.setFont(font)
                number_text = str(waypoint.number)
                font_metrics = painter.fontMetrics()
                text_width = font_metrics.horizontalAdvance(number_text)
                text_height = font_metrics.height()
                text_x = x - text_width // 2
                text_y = y + text_height // 3
                painter.drawText(text_x, text_y, number_text)

                # 属性の数を描画（右上に小さく表示）
                num_attributes = count_configured_waypoint_actions(waypoint.attributes)
                if (num_attributes > 0):
                    painter.setPen(QColor(255, 255, 255))
                    font.setPointSize(WAYPOINT_SETTINGS['FONT_SIZE_ATTR_MULT'] * WAYPOINT_SETTINGS['BASE_SIZE'])
                    font.setBold(True)
                    painter.setFont(font)
                    attr_text = str(num_attributes)
                    attr_x = x + adjusted_size - 5
                    attr_y = y - adjusted_size + 5
                    # 背景円を描画
                    painter.setBrush(QColor(50, 50, 50, 200))
                    painter.drawEllipse(attr_x - 8, attr_y - 12, 16, 16)
                    # 数字を描画
                    painter.drawText(attr_x - 3, attr_y, attr_text)

                # ホバー時のツールチップ領域を設定
                hover_rect = QRect(
                    x - adjusted_size,
                    y - adjusted_size,
                    adjusted_size * 2,
                    adjusted_size * 2
                )
                waypoint.hover_rect = hover_rect  # 後でホバー判定に使用

        # 6. ランドマークレイヤーを描画
        if self.landmarks and self.landmark_layer.visible:
            painter.setOpacity(self.landmark_layer.opacity)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            font = self.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)

            for landmark in self.landmarks:
                x, y = landmark.pixel_x, landmark.pixel_y
                size = 9
                is_editing = (self.pgm_display.edit_mode and
                              self.pgm_display.editing_landmark and
                              self.pgm_display.editing_landmark.number == landmark.number)
                color = QColor(255, 152, 0, 255) if is_editing else QColor(46, 160, 67, 255)

                pen = QPen(color)
                pen.setWidth(3)
                painter.setPen(pen)
                end_x = x + int(size * 2.2 * np.cos(landmark.angle))
                end_y = y - int(size * 2.2 * np.sin(landmark.angle))
                painter.drawLine(x, y, end_x, end_y)

                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.setBrush(color)
                diamond = QPolygon([
                    QPoint(x, y - size),
                    QPoint(x + size, y),
                    QPoint(x, y + size),
                    QPoint(x - size, y),
                ])
                painter.drawPolygon(diamond)

                painter.setPen(QColor(20, 20, 20, 230))
                painter.drawText(x + size + 4, y - size - 2, landmark.name)

                landmark.hover_rect = QRect(x - size, y - size, size * 2, size * 2)

        # 7. 原点レイヤーを描画（最上層）
        if self.origin_layer.visible and self.origin_layer.pixmap:
            painter.setOpacity(self.origin_layer.opacity)
            painter.drawPixmap(0, 0, self.origin_layer.pixmap)
        
        painter.end()
        return result

    def update_display(self):
        """複数レイヤーを合成して表示"""
        result = self.render_composite_pixmap()
        if result is None:
            return

        # スケーリングして表示（巨大画像の場合はFastTransformationを使用）
        new_size = QSize(
            int(result.width() * self.scale_factor),
            int(result.height() * self.scale_factor)
        )
        
        # 画像サイズに応じて変換品質を切り替え（パフォーマンス最適化）
        # 巨大画像（2000x2000以上）や描画中はFastTransformationを使用
        use_fast = (result.width() > 2000 or result.height() > 2000 or 
                    self._is_drawing_stroke or self._edit_dragging or self.scale_factor < 0.5)
        transform_mode = (Qt.TransformationMode.FastTransformation if use_fast 
                         else Qt.TransformationMode.SmoothTransformation)
        
        scaled_pixmap = result.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            transform_mode
        )
        
        self.pgm_display.setPixmap(scaled_pixmap)
        self.pgm_display.adjustSize()

    def get_displayed_pixmap_info(self):
        """戻り値: (disp_w, disp_h, offset_x, offset_y, displayed_pixmap)
        label 内に表示されているピクスマップの表示サイズとオフセットを返す
        """
        if not self.pgm_display or not self.pgm_display.pixmap() or not self.pgm_layer.pixmap:
            return None

        displayed_pm = self.pgm_display.pixmap()
        disp_w = displayed_pm.width()
        disp_h = displayed_pm.height()
        label_w = self.pgm_display.width()
        label_h = self.pgm_display.height()
        offset_x = max(0, (label_w - disp_w) // 2)
        offset_y = max(0, (label_h - disp_h) // 2)
        return disp_w, disp_h, offset_x, offset_y, displayed_pm

    def display_to_image_coords(self, pos: QPoint):
        """ラベル上（表示）座標 -> 元画像（pixmap）ピクセル座標に変換
        pos は QLabel のローカル座標（イベントの pos）
        None を返す場合は画像外
        """
        info = self.get_displayed_pixmap_info()
        if not info:
            return None
        disp_w, disp_h, offset_x, offset_y, displayed_pm = info
        x_disp = pos.x() - offset_x
        y_disp = pos.y() - offset_y
        if x_disp < 0 or y_disp < 0 or x_disp >= disp_w or y_disp >= disp_h:
            return None
        orig_pm = self.pgm_layer.pixmap
        orig_w = orig_pm.width()
        orig_h = orig_pm.height()
        img_x = int(x_disp * (orig_w / disp_w))
        img_y = int(y_disp * (orig_h / disp_h))
        return QPoint(img_x, img_y)

    def image_to_display_coords(self, image_pos: QPoint):
        """元画像（pixmap）ピクセル座標 -> ラベル上（表示）座標に変換"""
        info = self.get_displayed_pixmap_info()
        if not info:
            return None
        disp_w, disp_h, offset_x, offset_y, displayed_pm = info
        orig_pm = self.pgm_layer.pixmap
        orig_w = orig_pm.width()
        orig_h = orig_pm.height()
        x_disp = int(image_pos.x() * (disp_w / orig_w))
        y_disp = int(image_pos.y() * (disp_h / orig_h))
        return QPoint(x_disp + offset_x, y_disp + offset_y)

    def on_layer_changed(self):
        """レイヤーの状態が変更された時の処理"""
        self.update_display()
        self.layer_changed.emit()

    def remove_waypoint(self, number):
        """ウェイポイントを削除"""
        # 削除対象のウェイポイントを除外
        self.waypoints = [wp for wp in self.waypoints if wp.number != number]
        
        # ナンバリングを振り直し
        Waypoint.reset_counter()
        
        # 一旦右パネルのリストをクリア
        self.waypoint_removed.emit(number)
        
        # ウェイポイントを順番に振り直してUIを更新
        for wp in self.waypoints:
            Waypoint.counter += 1
            wp.renumber(Waypoint.counter)
            self.waypoint_added.emit(wp)
        
        self.update_display()

    def remove_all_waypoints(self):
        """全てのウェイポイントを削除"""
        self.waypoints.clear()
        Waypoint.reset_counter()
        self.waypoint_removed.emit(-1)  # 特別な値-1で全削除を通知
        self.update_display()

    def remove_landmark(self, number, record_history=True):
        """ランドマークを削除"""
        target = next((lm for lm in self.landmarks if lm.number == number), None)
        if not target:
            return

        self.landmarks = [lm for lm in self.landmarks if lm.number != number]
        self.landmark_removed.emit(number)
        self.update_display()
        if record_history:
            self.add_to_history({
                'type': 'landmark_remove',
                'landmark': target
            })

    def remove_all_landmarks(self):
        """全てのランドマークを削除"""
        self.landmarks.clear()
        Landmark.reset_counter()
        self.landmark_removed.emit(-1)
        self.update_display()

    def reorder_waypoints(self, source_number, target_number):
        """ウェイポイントの順序を変更"""
        if not self.waypoints:
            return
            
        # 対象のウェイポイントを見つける
        source_wp = next((wp for wp in self.waypoints if wp.number == source_number), None)
        if not source_wp:
            return
            
        # 現在のインデックスを取得
        source_index = self.waypoints.index(source_wp)
        target_index = next((i for i, wp in enumerate(self.waypoints) 
                           if wp.number == target_number), -1)
        
        if target_index == -1:
            return
            
        # リストから削除して新しい位置に挿入
        self.waypoints.pop(source_index)
        
        # ターゲットの位置に挿入
        if source_index < target_index:
            # 上から下にドラッグする場合
            self.waypoints.insert(target_index, source_wp)
        else:
            # 下から上にドラッグする場合
            self.waypoints.insert(target_index, source_wp)
        
        # 番号を振り直し
        Waypoint.reset_counter()
        
        # UIを更新するために一旦全てのウェイポイントを削除
        self.waypoint_removed.emit(-1)
        
        # ウェイポイントを順番に振り直してUIを更新
        for wp in self.waypoints:
            Waypoint.counter += 1
            wp.renumber(Waypoint.counter)
            self.waypoint_added.emit(wp)
            
        self.update_display()

    def toggle_grid(self):
        """グリッド表示の切り替え"""
        self.show_grid = not self.show_grid
        self.update_display()

    def update_mouse_position(self, pos):
        """マウス位置の更新とラベル表示"""
        if not self.pgm_layer.pixmap or not self.origin_point:
            return
        # 表示座標からピクセル座標に変換
        im_pos = self.display_to_image_coords(pos)
        if im_pos is None:
            self.coord_label.hide()
            return
        pixel_x = im_pos.x()
        pixel_y = im_pos.y()

        # 原点からの相対位置を計算
        origin_x, origin_y = self.origin_point
        rel_x = (pixel_x - origin_x) / 20
        rel_y = (origin_y - pixel_y) / 20
        
        # 座標を表示（ピクセル座標と相対座標）
        self.coord_label.setText(f"Pixel: ({pixel_x}, {pixel_y})\nMetric: ({rel_x:.2f}, {rel_y:.2f})")
        self.coord_label.show()

    def load_yaml_file(self, file_path):
        """YAMLファイルを読み込みorigin点を設定"""
        try:
            with open(file_path, 'r') as f:
                yaml_data = yaml.safe_load(f)

            self.current_map_yaml_path = file_path

            # 障害物膨張の占有判定に使うROS map YAMLの閾値を反映する
            if 'occupied_thresh' in yaml_data:
                self.inflation_occupied_thresh = float(yaml_data['occupied_thresh'])
            if 'negate' in yaml_data:
                self.inflation_negate = int(yaml_data['negate'])
            self._inflation_params_key = None
            if self.inflation_enabled:
                self._inflation_timer.start()
                
            # YAMLファイルから直接originとresolutionを読み取る
            if 'origin' in yaml_data:
                origin = yaml_data['origin']
                if len(origin) >= 2:
                    # 解像度を保存
                    self.resolution = float(yaml_data.get('resolution', 0.05))
                    # ワールド原点を保存（路面マップとの原点合わせに使用）
                    self.map_origin = (float(origin[0]), float(origin[1]))
                    x_pixel = int(-origin[0] / self.resolution)
                    y_pixel = int(-origin[1] / self.resolution)
                    
                    if self.pgm_layer.pixmap:
                        height = self.pgm_layer.pixmap.height()
                        y_pixel = height - y_pixel
                    
                    self.origin_point = (x_pixel, y_pixel)
                    self.draw_origin_point()
                    
                    # 既存のウェイポイントの座標を更新
                    self.update_all_waypoint_coordinates()
                    print(f"Origin point set to: {self.origin_point} (resolution: {self.resolution})")
                    print(f"Original coordinates: x={origin[0]}, y={origin[1]} meters")
                
        except Exception as e:
            print(f"Error loading YAML file: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_all_waypoint_coordinates(self):
        """全てのウェイポイントの座標を更新"""
        if not self.origin_point:
            return
            
        origin_x, origin_y = self.origin_point
        for waypoint in self.waypoints:
            waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
            self.waypoint_added.emit(waypoint)  # UIを更新
        for landmark in self.landmarks:
            landmark.update_metric_coordinates(origin_x, origin_y, self.resolution)
            self.landmark_edited.emit(landmark)

    def draw_origin_point(self):
        """原点マーカーを描画"""
        if not self.origin_point or not self.pgm_layer.pixmap:
            return

        # origin_layerのピクスマップを初期化
        if not self.origin_layer.pixmap or self.origin_layer.pixmap.size() != self.pgm_layer.pixmap.size():
            self.origin_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
            self.origin_layer.pixmap.fill(Qt.GlobalColor.transparent)

        # 既存の描画をクリア
        self.origin_layer.pixmap.fill(Qt.GlobalColor.transparent)
        
        # 原点マーカーを描画
        painter = QPainter(self.origin_layer.pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 原点の位置を取得
        x, y = self.origin_point
        
        # クロスマーカーを描画
        marker_size = 20
        pen = QPen(QColor(255, 0, 0))  # 赤色
        pen.setWidth(3)
        painter.setPen(pen)
        
        # 十字マーカー
        painter.drawLine(x - marker_size, y, x + marker_size, y)
        painter.drawLine(x, y - marker_size, x, y + marker_size)
        
        # 円を描画
        painter.drawEllipse(x - marker_size//2, y - marker_size//2, marker_size, marker_size)
        
        painter.end()
        
        self.update_display()

    def load_roadmap_file(self, file_path):
        """路面マッピングの色付き地図を下レイヤーとして読み込む。

        .colored.pgm + .colored.json（パレット復元、resolution/origin）と
        .png/.jpg/.jpeg に対応。JSON の resolution/origin で SLAM 地図と原点合わせする。
        """
        try:
            base = file_path
            lower = base.lower()
            if lower.endswith('.colored.json'):
                stem = base[:-len('.colored.json')]
            elif lower.endswith('.json'):
                stem = base[:-5]
            elif lower.endswith('.colored.pgm'):
                stem = base[:-len('.colored.pgm')]
            elif lower.endswith('.color.png'):
                stem = base[:-len('.color.png')]
            elif lower.endswith('.texture.png'):
                stem = base[:-len('.texture.png')]
            elif lower.endswith('.pgm'):
                stem = base[:-4]
            elif lower.endswith('.png'):
                stem = base[:-4]
            elif lower.endswith(('.jpg', '.jpeg')):
                stem = base.rsplit('.', 1)[0]
            else:
                stem = os.path.splitext(base)[0]

            # 画像本体の選択:
            #   実写色の .color.png / .texture.png を優先する。既存の .colored.pgm は
            #   パレット割当に不具合があり実色と大きく異なるため、PNGがあればそちらを使う。
            if lower.endswith(('.png', '.jpg', '.jpeg')):
                candidates = [file_path]
            else:
                candidates = [
                    stem + '.color.png',
                    stem + '.texture.png',
                    stem + '.colored.pgm',
                    stem + '.pgm',
                    stem + '.png',
                    stem + '.jpg',
                ]
            image_path = next((p for p in candidates if os.path.exists(p)), None)
            if image_path is None:
                raise FileNotFoundError(f'road map image not found for {file_path}')

            # JSONメタ（パレット / resolution / origin）
            json_candidates = [stem + '.colored.json', stem + '.json']
            if lower.endswith('.json'):
                json_candidates.insert(0, file_path)
            json_path = next((p for p in json_candidates if os.path.exists(p)), None)
            meta = None
            if json_path:
                with open(json_path, 'r') as f:
                    meta = json.load(f)

            q_img = self._load_roadmap_image(image_path, meta)
            if q_img is None or q_img.isNull():
                raise ValueError(f'failed to load road map image: {image_path}')

            self.roadmap_layer.pixmap = QPixmap.fromImage(q_img)
            self.roadmap_layer.visible = True

            if meta and 'resolution' in meta and meta.get('origin') and len(meta['origin']) >= 2:
                self.roadmap_resolution = float(meta['resolution'])
                self.roadmap_origin = (float(meta['origin'][0]), float(meta['origin'][1]))
            else:
                self.roadmap_resolution = None
                self.roadmap_origin = None

            # 下レイヤーが見えるように SLAM 地図を半透明にする
            if self.pgm_layer.opacity > 0.7:
                self.pgm_layer.set_opacity(0.6)

            print(f'Loaded road map: {image_path} size={q_img.width()}x{q_img.height()} '
                  f'res={self.roadmap_resolution} origin={self.roadmap_origin}')
            self.update_display()
            self.layer_changed.emit()
        except Exception as e:
            print(f'Error loading road map: {str(e)}')
            import traceback
            traceback.print_exc()

    def _load_roadmap_image(self, image_path, meta):
        """路面マップ画像を QImage に変換する（.colored.pgm は palette でRGB化）。"""
        lower = image_path.lower()
        if lower.endswith('.pgm'):
            arr, width, height = read_pgm_file(image_path)
            if arr is None:
                return None
            palette = meta.get('palette') if meta else None
            if palette:
                palette_arr = np.array(palette, dtype=np.uint8)
                n_colors = palette_arr.shape[0]
                rgb = np.zeros((height, width, 3), dtype=np.uint8)
                valid = arr < n_colors
                rgb[valid] = palette_arr[arr[valid]][:, :3]
                alpha = np.where(valid, 255, 0).astype(np.uint8)
                alpha[arr == 0] = 0  # index 0（unknown/背景）は透明
                rgba = np.ascontiguousarray(np.dstack([rgb, alpha]))
                q_img = QImage(rgba.tobytes(), width, height, width * 4,
                               QImage.Format.Format_RGBA8888)
                return q_img.copy()
            # パレット無しはグレースケール
            arr = np.ascontiguousarray(arr)
            q_img = QImage(arr.tobytes(), width, height, width,
                           QImage.Format.Format_Grayscale8)
            return q_img.copy()
        # png/jpg はそのまま読み込み
        return QImage(image_path)

    def _draw_roadmap(self, painter, target_size):
        """路面マップをベース地図のピクセル座標へ原点合わせして描画する。"""
        pm = self.roadmap_layer.pixmap
        if pm is None or pm.isNull():
            return
        painter.setOpacity(self.roadmap_layer.opacity)
        if (self.roadmap_origin and self.roadmap_resolution
                and self.map_origin and self.resolution and self.pgm_layer.pixmap):
            ox_b, oy_b = self.map_origin
            r_b = self.resolution
            ox_r, oy_r = self.roadmap_origin
            r_r = self.roadmap_resolution
            w_r = pm.width()
            h_r = pm.height()
            base_h = self.pgm_layer.pixmap.height()
            # ROS規約: origin=左下, 画像row0=上
            px0 = (ox_r - ox_b) / r_b
            px1 = (ox_r + w_r * r_r - ox_b) / r_b
            py0 = base_h - (oy_r + h_r * r_r - oy_b) / r_b
            py1 = base_h - (oy_r - oy_b) / r_b
            target = QRectF(px0, py0, px1 - px0, py1 - py0)
            painter.drawPixmap(target, pm, QRectF(0, 0, w_r, h_r))
        else:
            # 位置合わせ情報が無い場合はベースサイズにフィット
            painter.drawPixmap(
                QRectF(0, 0, target_size.width(), target_size.height()),
                pm, QRectF(0, 0, pm.width(), pm.height()))

    def generate_path(self):
        """ウェイポイント間のパスを生成または非表示（Nav2同様、膨張コスト上でA*探索）"""
        if self.waypoints and len(self.waypoints) >= 2:
            if not self.path_layer.pixmap or self.path_layer.pixmap.size() != self.pgm_layer.pixmap.size():
                self.path_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())

            # パスレイヤーをクリア
            self.path_layer.pixmap.fill(Qt.GlobalColor.transparent)

            # パス生成ボタンがチェックされている場合のみパスを描画
            parent = self.parent()
            while parent and not isinstance(parent, MainWindow):
                parent = parent.parent()
                
            if parent and parent.right_panel.generate_path_button.isChecked():
                if self.waypoints and len(self.waypoints) >= 2:
                    cost = self._ensure_cost_grid()
                    points = self._plan_waypoint_path(cost)

                    painter = QPainter(self.path_layer.pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                    # パスのスタイル設定
                    pen = QPen(Qt.GlobalColor.green, 3)
                    pen.setStyle(Qt.PenStyle.SolidLine)
                    painter.setPen(pen)

                    for i in range(len(points) - 1):
                        painter.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])

                    painter.end()

            self.update_display()

    def _plan_waypoint_path(self, cost):
        """ウェイポイント間を膨張コスト上でA*計画し、描画用の点列を返す。"""
        points = []
        for i in range(len(self.waypoints) - 1):
            start = (self.waypoints[i].pixel_x, self.waypoints[i].pixel_y)
            goal = (self.waypoints[i + 1].pixel_x, self.waypoints[i + 1].pixel_y)
            segment = self._plan_segment(cost, start, goal) if cost is not None else None
            if not segment:
                segment = [start, goal]
            if points:
                segment = segment[1:]
            points.extend(segment)
        return points

    def _plan_segment(self, cost, start, goal):
        """1区間をNav2 NavFn同様に計画する（ポテンシャル場＋勾配降下＋SimpleSmoother）。"""
        height, width = cost.shape
        sx, sy = int(start[0]), int(start[1])
        gx, gy = int(goal[0]), int(goal[1])
        sx = min(max(sx, 0), width - 1); sy = min(max(sy, 0), height - 1)
        gx = min(max(gx, 0), width - 1); gy = min(max(gy, 0), height - 1)
        if (sx, sy) == (gx, gy):
            return [(sx, sy)]

        # 探索窓（ウェイポイント近傍のみ探索して高速化）。見つからなければ広げる。
        base_margin = max(64, int(np.hypot(gx - sx, gy - sy) * 0.5))
        for margin in (base_margin, base_margin * 3, max(width, height)):
            x0 = max(0, min(sx, gx) - margin)
            x1 = min(width, max(sx, gx) + margin + 1)
            y0 = max(0, min(sy, gy) - margin)
            y1 = min(height, max(sy, gy) + margin + 1)
            window = cost[y0:y1, x0:x1]

            # 巨大な窓はダウンサンプルして探索量を抑える（障害物は最大値で保持）
            area = window.shape[0] * window.shape[1]
            step = 1
            if area > 250000:
                step = int(np.ceil(np.sqrt(area / 250000.0)))

            if step > 1:
                grid, cstart, cgoal = self._downsample_window(
                    window, (sx - x0, sy - y0), (gx - x0, gy - y0), step)
            else:
                grid = window
                cstart = (sx - x0, sy - y0)
                cgoal = (gx - x0, gy - y0)

            # NavFn: ゴールからのポテンシャル場を計算し、勾配降下で経路抽出
            path = self._navfn_path(grid, cstart, cgoal)
            if path is None:
                # 勾配降下が失敗した場合はA*の親チェーンへフォールバック
                raw = self._astar_window(grid, cstart, cgoal)
                if raw is None:
                    continue
                path = [(float(px), float(py)) for px, py in raw]

            if step > 1:
                full = [(x0 + px * step + step // 2, y0 + py * step + step // 2)
                        for px, py in path]
            else:
                full = [(x0 + px, y0 + py) for px, py in path]
            full[0] = (sx, sy)
            full[-1] = (gx, gy)

            # Nav2 SimpleSmoother相当で平滑化（障害物へ食い込む場合は元パスを使う）
            smoothed = self._simple_smooth(full, cost)
            return smoothed if self._path_is_free(smoothed, cost) else full
        return None

    def _navfn_path(self, grid, start, goal):
        """NavFn同様、ゴールからのポテンシャル場を勾配降下して経路を得る。"""
        potential = self._astar_potential(grid, goal)
        return self._gradient_path(potential, start, goal)

    def _astar_potential(self, grid, goal):
        """ゴールからのポテンシャル（コスト）場をA*(g+ヒューリスティック)で計算する。"""
        import heapq

        h, w = grid.shape
        gx = min(max(int(goal[0]), 0), w - 1)
        gy = min(max(int(goal[1]), 0), h - 1)
        blocked = grid >= 253
        blocked[gy, gx] = False

        cost_neutral = 50.0
        cost_factor = 0.8
        step_cost = (cost_neutral + grid.astype(np.float32) * cost_factor).astype(np.float32)
        ys, xs = np.mgrid[0:h, 0:w]
        heuristic = (np.hypot(xs - gx, ys - gy) * cost_neutral).astype(np.float32)

        n = h * w
        pot = np.full(n, np.float32(1.0e10), dtype=np.float32)
        closed = np.zeros(n, dtype=bool)
        gidx = gy * w + gx
        pot[gidx] = 0.0
        heap = [(0.0, gidx)]
        neighbors = ((-1, -1, 1.41421356), (-1, 0, 1.0), (-1, 1, 1.41421356),
                     (0, -1, 1.0), (0, 1, 1.0),
                     (1, -1, 1.41421356), (1, 0, 1.0), (1, 1, 1.41421356))
        while heap:
            _, idx = heapq.heappop(heap)
            if closed[idx]:
                continue
            closed[idx] = True
            cy, cx = divmod(idx, w)
            base = pot[idx]
            for dy, dx, dist in neighbors:
                ny = cy + dy
                nx = cx + dx
                if ny < 0 or nx < 0 or ny >= h or nx >= w:
                    continue
                nidx = ny * w + nx
                if closed[nidx] or blocked[ny, nx]:
                    continue
                tentative = base + dist * step_cost[ny, nx]
                if tentative < pot[nidx]:
                    pot[nidx] = tentative
                    heapq.heappush(heap, (float(tentative) + float(heuristic[ny, nx]), nidx))
        return pot.reshape(h, w)

    def _gradient_path(self, potential, start, goal):
        """NavFn calcPath 相当: ポテンシャル場を勾配降下してサブピクセル経路を抽出。"""
        h, w = potential.shape
        if h < 3 or w < 3:
            return None
        pot = potential.reshape(-1)
        POT_HIGH = 1.0e10
        COST_NEUTRAL = 50.0
        path_step = 0.5

        sx = min(max(int(start[0]), 1), w - 2)
        sy = min(max(int(start[1]), 1), h - 2)
        stc = sy * w + sx
        dx = dy = 0.0
        path = [(float(sx), float(sy))]

        for _ in range(200000):
            nearest = stc + int(round(dx)) + w * int(round(dy))
            nearest = min(max(nearest, 0), h * w - 1)
            if pot[nearest] < COST_NEUTRAL:
                path.append((float(goal[0]), float(goal[1])))
                return path
            if stc < w or stc >= (h - 1) * w:
                return path if len(path) > 1 else None

            path.append((float(stc % w) + dx, float(stc // w) + dy))

            stcnx = stc + w
            stcpx = stc - w
            nbrs = (stc, stc + 1, stc - 1, stcnx, stcnx + 1, stcnx - 1,
                    stcpx, stcpx + 1, stcpx - 1)
            if any(pot[i] >= POT_HIGH for i in nbrs) or self._path_oscillates(path):
                minc = stc
                minp = pot[stc]
                for i in nbrs:
                    if pot[i] < minp:
                        minp = pot[i]
                        minc = i
                stc = minc
                dx = dy = 0.0
                if pot[stc] >= POT_HIGH:
                    return None
            else:
                gx = self._interp_grad(pot, stc, stc + 1, stcnx, stcnx + 1, dx, dy, w, h, True)
                gy = self._interp_grad(pot, stc, stc + 1, stcnx, stcnx + 1, dx, dy, w, h, False)
                if gx == 0.0 and gy == 0.0:
                    return None
                ss = path_step / np.hypot(gx, gy)
                dx += gx * ss
                dy += gy * ss
                if dx > 1.0:
                    stc += 1; dx -= 1.0
                if dx < -1.0:
                    stc -= 1; dx += 1.0
                if dy > 1.0:
                    stc += w; dy -= 1.0
                if dy < -1.0:
                    stc -= w; dy += 1.0
        return path if len(path) > 1 else None

    @staticmethod
    def _path_oscillates(path):
        return len(path) > 2 and path[-1] == path[-3]

    def _interp_grad(self, pot, a, b, c, d, dx, dy, w, h, x_axis):
        """4点(a,b,c,d)の勾配を双線形補間する。a=stc, b=stc+1, c=stc+w, d=stc+w+1"""
        ga = self._grad_at(pot, a, w, h, x_axis)
        gb = self._grad_at(pot, b, w, h, x_axis)
        gc = self._grad_at(pot, c, w, h, x_axis)
        gd = self._grad_at(pot, d, w, h, x_axis)
        x1 = (1.0 - dx) * ga + dx * gb
        x2 = (1.0 - dx) * gc + dx * gd
        return (1.0 - dy) * x1 + dy * x2

    @staticmethod
    def _grad_at(pot, n, w, h, x_axis):
        """NavFn gradCell 相当: ポテンシャルの勾配（ゴールへ向かう向き）。"""
        POT_HIGH = 1.0e10
        x = n % w
        y = n // w
        if x <= 0 or x >= w - 1 or y <= 0 or y >= h - 1:
            return 0.0
        cv = pot[n]
        if cv >= POT_HIGH:
            if x_axis:
                if pot[n - 1] < POT_HIGH:
                    return -1.0
                if pot[n + 1] < POT_HIGH:
                    return 1.0
            else:
                if pot[n - w] < POT_HIGH:
                    return -1.0
                if pot[n + w] < POT_HIGH:
                    return 1.0
            return 0.0
        dx = 0.0
        dy = 0.0
        if pot[n - 1] < POT_HIGH:
            dx += pot[n - 1] - cv
        if pot[n + 1] < POT_HIGH:
            dx += cv - pot[n + 1]
        if pot[n - w] < POT_HIGH:
            dy += pot[n - w] - cv
        if pot[n + w] < POT_HIGH:
            dy += cv - pot[n + w]
        norm = np.hypot(dx, dy)
        if norm <= 0.0:
            return 0.0
        return (dx if x_axis else dy) / norm

    def _simple_smooth(self, points, cost, data_w=0.2, smooth_w=0.3,
                       tolerance=1e-10, max_its=1000, refinement=2):
        """Nav2 SimpleSmoother相当（w_data=0.2, w_smooth=0.3, do_refinement=2）。"""
        if len(points) <= 2:
            return points
        h, w = cost.shape
        y = np.array(points, dtype=np.float64)
        for _ in range(refinement + 1):
            x = y.copy()
            for _it in range(max_its):
                y_prev = y.copy()
                y[1:-1] = (y[1:-1] + data_w * (x[1:-1] - y[1:-1])
                           + smooth_w * (y[2:] + y[:-2] - 2.0 * y[1:-1]))
                change = float(np.abs(y[1:-1] - y_prev[1:-1]).sum())
                xs = np.clip(np.round(y[:, 0]).astype(np.int64), 0, w - 1)
                ys = np.clip(np.round(y[:, 1]).astype(np.int64), 0, h - 1)
                if np.any(cost[ys, xs] >= 253):
                    y = y_prev
                    break
                if change < tolerance:
                    break
        return [(float(p[0]), float(p[1])) for p in y]

    @staticmethod
    def _path_is_free(points, cost):
        """パス上のサンプル点が致死/内接セル(>=253)を通っていないか確認する。"""
        height, width = cost.shape
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
            for t in range(steps + 1):
                x = int(round(x0 + (x1 - x0) * t / steps))
                y = int(round(y0 + (y1 - y0) * t / steps))
                if 0 <= x < width and 0 <= y < height and cost[y, x] >= 253:
                    return False
        return True

    @staticmethod
    def _downsample_window(window, start, goal, step):
        """コスト窓を最大値プーリングで縮小し、始点/終点も粗座標へ変換する。"""
        h, w = window.shape
        ch = (h + step - 1) // step
        cw = (w + step - 1) // step
        padded = np.pad(window, ((0, ch * step - h), (0, cw * step - w)), constant_values=0)
        coarse = padded.reshape(ch, step, cw, step).max(axis=(1, 3))
        return coarse, (start[0] // step, start[1] // step), (goal[0] // step, goal[1] // step)

    def _astar_window(self, grid, start, goal):
        """8近傍A*。コストはNavFn同様 COST_NEUTRAL + COST_FACTOR*cost を用いる。"""
        import heapq

        h, w = grid.shape
        sx, sy = start
        gx, gy = goal
        blocked = grid >= 253
        blocked[sy, sx] = False
        blocked[gy, gx] = False

        cost_neutral = 50.0
        cost_factor = 0.8
        # コストが高すぎる領域を避けるため、距離に応じた重みを掛ける
        step_cost = np.zeros((h, w), dtype=np.float32)
        np.add(cost_neutral, grid.astype(np.float32) * cost_factor, out=step_cost)
        step_cost /= cost_neutral

        ys, xs = np.mgrid[0:h, 0:w]
        heuristic = np.hypot(xs - gx, ys - gy).astype(np.float32)

        n = h * w
        g_score = np.full(n, np.inf, dtype=np.float32)
        parent = np.full(n, -1, dtype=np.int32)
        closed = np.zeros(n, dtype=bool)
        sidx = sy * w + sx
        gidx = gy * w + gx
        g_score[sidx] = 0.0

        neighbors = ((-1, -1, 1.41421356), (-1, 0, 1.0), (-1, 1, 1.41421356),
                     (0, -1, 1.0), (0, 1, 1.0),
                     (1, -1, 1.41421356), (1, 0, 1.0), (1, 1, 1.41421356))
        heap = [(float(heuristic[sy, sx]), sidx)]
        found = False
        while heap:
            _, idx = heapq.heappop(heap)
            if idx == gidx:
                found = True
                break
            if closed[idx]:
                continue
            closed[idx] = True
            cy, cx = divmod(idx, w)
            base_g = g_score[idx]
            for dy, dx, dist in neighbors:
                ny = cy + dy
                nx = cx + dx
                if ny < 0 or nx < 0 or ny >= h or nx >= w:
                    continue
                nidx = ny * w + nx
                if closed[nidx] or blocked[ny, nx]:
                    continue
                tentative = base_g + dist * step_cost[ny, nx]
                if tentative < g_score[nidx]:
                    g_score[nidx] = tentative
                    parent[nidx] = idx
                    heapq.heappush(heap, (tentative + float(heuristic[ny, nx]), nidx))

        if not found:
            return None
        path = []
        cur = gidx
        while cur != -1:
            cy, cx = divmod(cur, w)
            path.append((cx, cy))
            if cur == sidx:
                break
            cur = parent[cur]
        path.reverse()
        return path

    @staticmethod
    def _smooth_path(points, iterations=1):
        """計画パスを軽く平滑化する（Nav2のsmoother相当の簡易処理）。"""
        if len(points) <= 2:
            return points
        pts = [(float(p[0]), float(p[1])) for p in points]
        for _ in range(iterations):
            new_pts = [pts[0]]
            for i in range(1, len(pts) - 1):
                x = (pts[i - 1][0] + 2 * pts[i][0] + pts[i + 1][0]) / 4.0
                y = (pts[i - 1][1] + 2 * pts[i][1] + pts[i + 1][1]) / 4.0
                new_pts.append((x, y))
            new_pts.append(pts[-1])
            pts = new_pts
        return pts

    def handle_waypoint_edited(self, waypoint):
        """ウェイポイント編集時の処理"""
        # 編集前の状態を保存
        old_state = {
            'pixel_x': waypoint.pixel_x,
            'pixel_y': waypoint.pixel_y,
            'angle': waypoint.angle
        }

        if self.origin_point:  # 原点が設定されている場合
            origin_x, origin_y = self.origin_point
            waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
        self.waypoint_edited.emit(waypoint)
        self.update_display()

        # 編集後の状態を履歴に追加
        new_state = {
            'pixel_x': waypoint.pixel_x,
            'pixel_y': waypoint.pixel_y,
            'angle': waypoint.angle
        }

        self.add_to_history({
            'type': 'waypoint_edit',
            'waypoint': waypoint,
            'old_state': old_state,
            'new_state': new_state
        })

    def handle_landmark_edited(self, landmark):
        """ランドマーク編集時の処理"""
        if self.origin_point:
            origin_x, origin_y = self.origin_point
            landmark.update_metric_coordinates(origin_x, origin_y, self.resolution)
        self.landmark_edited.emit(landmark)
        self.update_display()

    def enter_edit_mode(self, waypoint):
        """ウェイポイントの編集モードに入る"""
        self.pgm_display.edit_mode = True
        self.pgm_display.editing_waypoint = waypoint
        self.pgm_display.setCursor(Qt.CursorShape.SizeAllCursor)

    def exit_edit_mode(self):
        """編集モードを終了"""
        self.pgm_display.edit_mode = False
        self.pgm_display.editing_waypoint = None
        self.pgm_display.setCursor(Qt.CursorShape.ArrowCursor)

    def get_combined_pixmap(self):
        """全レイヤーを合成したピクスマップを取得（エクスポート用）"""
        if not self.pgm_layer.pixmap:
            return None

        # 合成用の新しいピクスマップを作成
        result = QPixmap(self.pgm_layer.pixmap.size())
        result.fill(Qt.GlobalColor.white)
        
        painter = QPainter(result)
        
        # エクスポートに含めるレイヤーのみを描画
        # origin_layerを除外し、他のレイヤーのみを描画
        export_layers = [
            self.pgm_layer,
            self.drawing_layer,
        ]
        
        for layer in export_layers:
            if layer.visible and layer.pixmap:
                painter.setOpacity(layer.opacity)
                painter.drawPixmap(0, 0, layer.pixmap)
        
        painter.end()
        return result

    def import_waypoints_from_yaml(self, yaml_data):
        """YAMLデータからウェイポイントをインポート"""
        if 'waypoints' not in yaml_data:
            return

        # 既存のウェイポイントをクリア
        self.waypoints.clear()
        Waypoint.reset_counter()
        
        for wp_data in yaml_data['waypoints']:
            try:
                # ピクセル座標を計算
                if self.origin_point and hasattr(self, 'resolution'):
                    origin_x, origin_y = self.origin_point
                    x_meters = wp_data['x'] * 20
                    y_meters = wp_data['y'] * 20
                    
                    # メートル座標からピクセル座標に変換
                    pixel_x = int(origin_x + x_meters)
                    pixel_y = int(origin_y - y_meters)
                    
                    # 角度の取得
                    angle = wp_data['angle_radians']
                    
                    # 新しいウェイポイントを作成
                    waypoint = Waypoint(pixel_x, pixel_y, angle)
                    waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
                    
                    # 追加の属性をインポート
                    for key, value in wp_data.items():
                        if key not in ['number', 'x', 'y', 'angle_degrees', 'angle_radians']:
                            waypoint.set_attribute(key, value)
                    
                    self.waypoints.append(waypoint)
                    self.waypoint_added.emit(waypoint)
            except KeyError as e:
                print(f"Error importing waypoint: Missing key {e}")
                continue
            except Exception as e:
                print(f"Error importing waypoint: {e}")
                continue
        
        self.update_display()

    def export_landmarks_data(self):
        """ランドマークをYAML/JSON向けの辞書に変換"""
        data = {
            'format_version': '1.0',
            'landmarks': [
                {
                    'name': landmark.name,
                    'x': round(float(landmark.x), 3),
                    'y': round(float(landmark.y), 3),
                    'yaw': round(float(landmark.angle), 3),
                    'aliases': list(landmark.aliases),
                }
                for landmark in self.landmarks
            ]
        }
        if self.current_map_yaml_path:
            map_yaml = os.path.basename(self.current_map_yaml_path)
            data['map'] = {
                'name': os.path.splitext(map_yaml)[0],
                'yaml': map_yaml,
            }
        return data

    def import_landmarks_from_data(self, data):
        """YAML/JSONデータからランドマークをインポート"""
        if not data or 'landmarks' not in data:
            return
        if not self.origin_point:
            QMessageBox.warning(self, "Origin Required", "先に地図YAMLを読み込んで原点を設定してください。")
            return

        self.landmarks.clear()
        Landmark.reset_counter()
        self.landmark_removed.emit(-1)
        origin_x, origin_y = self.origin_point

        for lm_data in data.get('landmarks', []):
            try:
                x_meters = float(lm_data['x']) * 20
                y_meters = float(lm_data['y']) * 20
                pixel_x = int(origin_x + x_meters)
                pixel_y = int(origin_y - y_meters)
                angle = float(lm_data.get('yaw', lm_data.get('angle_radians', 0.0)))
                name = str(lm_data.get('name', '')).strip() or None

                landmark = Landmark(pixel_x, pixel_y, angle, name)
                landmark.aliases = list(lm_data.get('aliases', []))
                landmark.update_metric_coordinates(origin_x, origin_y, self.resolution)
                self.landmarks.append(landmark)
                self.landmark_added.emit(landmark)
            except (KeyError, TypeError, ValueError) as e:
                print(f"Error importing landmark: {e}")
                continue

        self.update_display()

    def mouseMoveEvent(self, event):
        """マウス移動時のイベント処理"""
        # 既存のmouseMoveEventの処理を維持
        super().mouseMoveEvent(event)
        
        # ウェイポイントのホバー判定とツールチップ表示
        if self.pgm_layer.pixmap:
            # イベントは ImageViewer のローカル座標なので QLabel のローカル座標へ変換
            label_pos = self.pgm_display.mapFrom(self, event.pos())
            im_pos = self.display_to_image_coords(label_pos)
            if not im_pos:
                QToolTip.hideText()
                return
            for waypoint in self.waypoints:
                if hasattr(waypoint, 'hover_rect') and waypoint.hover_rect.contains(im_pos):
                    # 属性情報のツールチップを作成
                    if waypoint.attributes:
                        tooltip = "Attributes:\n"
                        for key, value in waypoint.attributes.items():
                            tooltip += f"{key}: {value}\n"
                        QToolTip.showText(event.globalPos(), tooltip.strip())
                        return
            
            QToolTip.hideText()

    def add_to_history(self, action):
        """履歴に操作を追加"""
        # 現在位置より後の履歴を削除
        self.history = self.history[:self.current_index + 1]
        
        # 履歴に追加
        self.history.append(action)
        
        # 最大履歴数を超えた場合、古い履歴を削除
        if len(self.history) > self.max_history:
            self.history.pop(0)
        else:
            self.current_index += 1
            
        # 履歴状態を通知
        self.history_changed.emit(
            self.can_undo(),
            self.can_redo()
        )
    
    def can_undo(self):
        """操作を戻せるかどうか"""
        return self.current_index >= 0
    
    def can_redo(self):
        """操作を進められるかどうか"""
        return self.current_index < len(self.history) - 1
    
    def undo(self):
        """操作を戻す"""
        if not self.can_undo():
            return
            
        action = self.history[self.current_index]
        self.current_index -= 1
        
        if action['type'] == 'waypoint_add':
            self.remove_waypoint(action['waypoint'].number)
        elif action['type'] == 'waypoint_remove':
            # ウェイポイントを復元
            self.waypoints.append(action['waypoint'])
            self.waypoint_added.emit(action['waypoint'])
        elif action['type'] == 'landmark_add':
            self.remove_landmark(action['landmark'].number, record_history=False)
        elif action['type'] == 'landmark_remove':
            self.landmarks.append(action['landmark'])
            self.landmark_added.emit(action['landmark'])
        elif action['type'] == 'waypoint_edit':
            # 以前の状態に戻す
            waypoint = action['waypoint']
            old_state = action['old_state']
            waypoint.pixel_x = old_state['pixel_x']
            waypoint.pixel_y = old_state['pixel_y']
            waypoint.angle = old_state['angle']
            if self.origin_point:
                origin_x, origin_y = self.origin_point
                waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
            self.waypoint_edited.emit(waypoint)
        elif action['type'] == 'draw':
            # 描画レイヤーを以前の状態に戻す
            self.drawing_layer.pixmap = action['old_pixmap']
            self._restore_erased_map_region(action.get('map_bbox'), action.get('map_old'))
            
        self.update_display()
        self.history_changed.emit(self.can_undo(), self.can_redo())
    
    def redo(self):
        """操作を進める"""
        if not self.can_redo():
            return
            
        self.current_index += 1
        action = self.history[self.current_index]
        
        if action['type'] == 'waypoint_add':
            self.waypoints.append(action['waypoint'])
            self.waypoint_added.emit(action['waypoint'])
        elif action['type'] == 'waypoint_remove':
            self.remove_waypoint(action['waypoint'].number)
        elif action['type'] == 'landmark_add':
            self.landmarks.append(action['landmark'])
            self.landmark_added.emit(action['landmark'])
        elif action['type'] == 'landmark_remove':
            self.remove_landmark(action['landmark'].number, record_history=False)
        elif action['type'] == 'waypoint_edit':
            # 新しい状態に進める
            waypoint = action['waypoint']
            new_state = action['new_state']
            waypoint.pixel_x = new_state['pixel_x']
            waypoint.pixel_y = new_state['pixel_y']
            waypoint.angle = new_state['angle']
            if self.origin_point:
                origin_x, origin_y = self.origin_point
                waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
            self.waypoint_edited.emit(waypoint)
        elif action['type'] == 'draw':
            # 描画レイヤーを新しい状態に進める
            self.drawing_layer.pixmap = action['new_pixmap']
            self._restore_erased_map_region(action.get('map_bbox'), action.get('map_new'))
            
        self.update_display()
        self.history_changed.emit(self.can_undo(), self.can_redo())

    def _restore_erased_map_region(self, bbox, region):
        """消しゴムで消した地図領域をUndo/Redo用に復元する。"""
        if not bbox or region is None or self.map_image_array is None:
            return
        x0, y0, x1, y1 = bbox
        if (x1 - x0) != region.shape[1] or (y1 - y0) != region.shape[0]:
            return
        self.map_image_array[y0:y1, x0:x1] = region
        self._refresh_pgm_pixmap_from_array()
        self._inflation_params_key = None
        if self.inflation_enabled:
            self._update_inflation_region((x0, y0, x1, y1))

class MenuPanel(QWidget):
    """メニューパネル
    ファイル操作とズーム制御のUIを提供"""
    
    # シグナルの定義
    file_selected = Signal(str)  # ファイル選択時のシグナル
    zoom_value_changed = Signal(int)  # ズーム値変更時のシグナル
    yaml_selected = Signal(str)  # YAMLファイル選択用のシグナルを追加
    roadmap_selected = Signal(str)  # 路面マップ（色付き地図）選択用シグナル
    undo_requested = Signal()  # 戻るボタン用シグナル
    redo_requested = Signal()  # 進むボタン用シグナル
    map_image_requested = Signal()  # 地図全体の画像保存用シグナル
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """UIコンポーネントの初期化と配置"""
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #e8e8e8;")
        self.setFixedHeight(120)

        # メニューバー
        menu_bar = QMenuBar()
        file_menu = QMenu("File", self)
        edit_menu = QMenu("Edit", self)
        
        # 戻る/進むボタンの追加
        button_layout = QHBoxLayout()
        
        self.undo_button = QPushButton("↩ Undo")
        self.undo_button.setEnabled(False)  # 初期状態は無効
        self.undo_button.clicked.connect(self.undo_requested.emit)
        self.undo_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px 10px;
                min-width: 80px;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #999;
            }
        """)
        
        self.redo_button = QPushButton("Redo ↪")
        self.redo_button.setEnabled(False)  # 初期状態は無効
        self.redo_button.clicked.connect(self.redo_requested.emit)
        self.redo_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px 10px;
                min-width: 80px;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #999;
            }
        """)
        
        # button_layout.addWidget(self.undo_button)
        # button_layout.addWidget(self.redo_button)
        # button_layout.addStretch()  # 残りのスペースを埋める
        
        # ファイルメニューのアクションを作成
        open_action = file_menu.addAction("Open PGM")
        save_action = file_menu.addAction("Save PGM")
        save_image_action = file_menu.addAction("Save Map Image")
        save_image_action.setToolTip(
            "地図全体を1枚の画像として保存（地図＋ウェイポイント＋路面マッピング＋パス）"
        )
        save_image_action.triggered.connect(self.map_image_requested.emit)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        
        # 編集メニューにUndo/Redoアクションを追加
        undo_action = edit_menu.addAction("Undo")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.undo_requested.emit)
        
        redo_action = edit_menu.addAction("Redo")
        redo_action.setShortcut("Ctrl+Shift+Z")
        redo_action.triggered.connect(self.redo_requested.emit)
        
        menu_bar.addMenu(file_menu)
        menu_bar.addMenu(edit_menu)

        # ファイル選択部分のレイアウト
        file_layout = QHBoxLayout()
        self.select_button = QPushButton("Select PGM File")
        self.select_button.clicked.connect(self.open_file_dialog)
        
        # YAMLファイル選択ボタンを追加
        self.yaml_button = QPushButton("Select YAML File")
        self.yaml_button.clicked.connect(self.open_yaml_dialog)

        # 路面マッピング色付き地図（下レイヤー）選択ボタン
        self.roadmap_button = QPushButton("Select Road Map")
        self.roadmap_button.clicked.connect(self.open_roadmap_dialog)
        
        self.file_name_label = QLabel("No file selected")  # ファイル名表示用ラベル
        self.file_name_label.setStyleSheet("color: #666; padding: 0 10px;")
        
        file_layout.addWidget(self.select_button)
        file_layout.addWidget(self.yaml_button)  # YAMLボタンを追加
        file_layout.addWidget(self.roadmap_button)  # 路面マップボタンを追加
        file_layout.addWidget(self.file_name_label, stretch=1)  # stretchを1に設定して余白を埋める
        
        # ズームコントロールをメソッドに分離
        zoom_widget = self.create_zoom_controls()
        
        layout.addWidget(menu_bar)
        # layout.addLayout(button_layout)  # 戻る/進むボタンを追加
        layout.addLayout(file_layout)  # ファイル選択部分を追加
        layout.addWidget(zoom_widget)

        # グリッドボタンを追加
        self.grid_button = QPushButton("Toggle Grid")
        self.grid_button.setCheckable(True)  # トグルボタンとして設定
        self.grid_button.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QPushButton:checked {
                background-color: #e0e0e0;
                border: 2px solid #999;
            }
        """)
        file_layout.addWidget(self.grid_button)  # file_layoutにグリッドボタンを追加
        
        file_layout.addWidget(self.undo_button)
        file_layout.addWidget(self.redo_button)

        self.setLayout(layout)

    def create_zoom_controls(self):
        """ズームコントロールの作成を集約"""
        zoom_widget = QWidget()
        zoom_layout = QHBoxLayout()
        
        # ズームスライダーの設定
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(1, 100)
        self.zoom_slider.setValue(50)
        
        # ズーム率表示用ラベル
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(50)  # ラベルの最小幅を設定
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # スライダー値変更時の処理を更新
        def update_zoom(value):
            zoom_percent = int((value / 50.0) * 100)
            self.zoom_label.setText(f"{zoom_percent}%")
            self.zoom_value_changed.emit(value)
        
        self.zoom_slider.valueChanged.connect(update_zoom)
        
        reset_button = QPushButton("Reset Zoom")
        reset_button.clicked.connect(lambda: self.zoom_slider.setValue(50))
        
        # レイアウトにコンポーネントを追加
        zoom_layout.addWidget(self.zoom_slider, stretch=1)  # スライダーを伸縮可能に
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(reset_button)
        zoom_widget.setLayout(zoom_layout)
        return zoom_widget

    def open_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open PGM File",
            "",
            "PGM Files (*.pgm);;All Files (*)"
        )
        if file_name:
            # ファイルのベース名（パスを除いた部分）を表示
            self.file_name_label.setText(file_name.split('/')[-1])
            self.file_selected.emit(file_name)

    def open_yaml_dialog(self):
        """YAMLファイル選択ダイアログを開く"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open YAML File",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if file_name:
            self.yaml_selected.emit(file_name)

    def open_roadmap_dialog(self):
        """路面マッピング色付き地図の選択ダイアログを開く"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Road Map (colored)",
            "",
            "Road Map (*.colored.pgm *.pgm *.png *.jpg *.jpeg *.json);;All Files (*)"
        )
        if file_name:
            self.roadmap_selected.emit(file_name)

    def update_undo_redo_actions(self, can_undo, can_redo):
        """Undo/Redoボタンの状態を更新"""
        self.undo_button.setEnabled(can_undo)
        self.redo_button.setEnabled(can_redo)

class LayerControl(QWidget):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)  # ウィジェット間のスペースを設定
        
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-radius: 3px;
                padding: 5px;
            }
            QCheckBox {
                min-width: 120px;  /* チェックボックスの最小幅を設定 */
                max-width: 120px;  /* チェックボックスの最大幅を設定 */
            }
            QSlider {
                min-width: 100px;  /* スライダーの最小幅を設定 */
            }
        """)
        
        # チェックボックスの設定
        self.visibility_cb = QCheckBox(self.layer.name)
        self.visibility_cb.setChecked(self.layer.visible)
        self.visibility_cb.stateChanged.connect(self._on_visibility_changed)
        
        # 不透明度スライダーの設定
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(int(self.layer.opacity * 100))
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        
        # レイアウトに追加
        layout.addWidget(self.visibility_cb)
        layout.addWidget(self.opacity_slider, stretch=1)  # スライダーを伸縮可能に設定

    def _on_visibility_changed(self, state):
        """表示/非表示の切り替え"""
        self.layer.set_visible(state == Qt.CheckState.Checked.value)
    
    def _on_opacity_changed(self, value):
        """不透明度の変更"""
        self.layer.set_opacity(value / 100.0)

class _CollapsibleHeader(QWidget):
    """クリックで開閉を通知するヘッダーウィジェット。"""

    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class CollapsibleSection(QWidget):
    """ヘッダーをクリックすると本文を折りたたみ/展開できるセクション。

    既存のパネル（タイトル＋本文）を置き換える形で使う。
    ヘッダーには `add_header_widget`、本文には `add_content_widget` で
    ウィジェットを追加する。
    """

    toggled = Signal(bool)  # 展開状態が変化したときに発火 (True=展開)

    def __init__(self, title, expanded=True, parent=None):
        super().__init__(parent)
        self._expanded = bool(expanded)
        self.setObjectName("CollapsibleSection")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(5)

        # ヘッダー
        self.header = _CollapsibleHeader()
        self.header.setObjectName("CollapsibleHeader")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.setStyleSheet("""
            QWidget#CollapsibleHeader {
                background-color: #e0e0e0;
                border-radius: 3px;
            }
        """)
        self.header.clicked.connect(self.toggle)

        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(5, 5, 5, 5)
        self.header_layout.setSpacing(5)

        # 開閉矢印
        self.toggle_button = QPushButton()
        self.toggle_button.setFixedSize(20, 20)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #333333;
                font-size: 11px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #cfcfcf;
                border-radius: 3px;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle)

        # タイトル
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 0;
                background-color: transparent;
                color: #000000;
            }
        """)

        self.header_layout.addWidget(self.toggle_button)
        self.header_layout.addWidget(self.title_label)

        # 本文
        self.content = QWidget()
        self.content.setObjectName("CollapsibleContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(5)

        outer.addWidget(self.header)
        outer.addWidget(self.content)

        self._apply_state()

    def add_header_widget(self, widget, stretch=0):
        """ヘッダー右側にウィジェットを追加する。"""
        self.header_layout.addWidget(widget, stretch)

    def add_header_stretch(self):
        """ヘッダーに伸縮スペーサーを追加する。"""
        self.header_layout.addStretch()

    def add_content_widget(self, widget, stretch=0):
        """本文にウィジェットを追加する。"""
        self.content_layout.addWidget(widget, stretch)

    def add_content_layout(self, layout):
        """本文にレイアウトを追加する。"""
        self.content_layout.addLayout(layout)

    def is_expanded(self):
        return self._expanded

    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded):
        self._expanded = bool(expanded)
        self._apply_state()
        self.toggled.emit(self._expanded)

    def _apply_state(self):
        # シグナルの再入を防ぐためボタン更新中は通知を止める
        self.toggle_button.blockSignals(True)
        self.toggle_button.setText("▼" if self._expanded else "▶")
        self.toggle_button.blockSignals(False)
        self.content.setVisible(self._expanded)


class RightPanel(QWidget):
    """右側のパネル"""
    waypoint_delete_requested = Signal(int)  # 新しいシグナルを追加
    all_waypoints_delete_requested = Signal()  # 新しいシグナル
    waypoint_reorder_requested = Signal(int, int)  # 順序変更シグナルを追加
    generate_path_requested = Signal()  # パス生成用シグナル
    export_requested = Signal(bool, bool)  # (export_pgm, export_waypoints)
    waypoint_import_requested = Signal(str)  # YAMLファイルパスを送信
    landmark_delete_requested = Signal(int)
    all_landmarks_delete_requested = Signal()
    landmark_name_changed = Signal(int, str)
    landmark_import_requested = Signal(str)
    landmark_export_requested = Signal()
    map_image_requested = Signal()  # 地図全体の画像保存用シグナル
    # 障害物膨張(Nav2): (enabled, inflation_radius, cost_scaling_factor, inscribed_radius, opacity%)
    inflation_changed = Signal(bool, float, float, float, int)
    
    def __init__(self):
        super().__init__()
        self.waypoint_widgets = {}  # ウェイポイントウィジェットを保持する辞書を追加
        self.landmark_widgets = {}
        self.setup_ui()

    def setup_ui(self):
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setStyleSheet("QWidget { background-color: #f5f5f5; border-radius: 5px; }")

        # レイヤーパネルを追加
        self.layer_widget = self.create_layer_panel()
        layout.addWidget(self.layer_widget)

        # 障害物膨張パネルを追加
        self.inflation_widget = self.create_inflation_panel()
        layout.addWidget(self.inflation_widget)
        
        # ウェイポイントリストパネルを追加
        self.waypoint_widget = self.create_waypoint_panel()
        layout.addWidget(self.waypoint_widget)

        # ランドマークリストパネルを追加
        self.landmark_widget = self.create_landmark_panel()
        layout.addWidget(self.landmark_widget)
        
        # Format Editor (旧Panel 2)を追加
        self.format_editor = FormatEditorPanel()
        layout.addWidget(self.format_editor)
        
        # エクスポートパネルを追加
        self.export_widget = self.create_export_panel()
        layout.addWidget(self.export_widget)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)
        self.setLayout(outer_layout)

    def create_layer_panel(self):
        """レイヤーパネルを作成"""
        section = CollapsibleSection("Layers")
        
        # スクロールエリアを追加
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)
        
        # レイヤーリストのコンテナ
        self.layer_list = QWidget()
        self.layer_list.setStyleSheet("""
            QWidget {
                background-color: white;
                padding: 5px;
            }
        """)
        self.layer_list_layout = QVBoxLayout(self.layer_list)
        self.layer_list_layout.setSpacing(5)
        self.layer_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # スクロールエリアにレイヤーリストを設定
        scroll_area.setWidget(self.layer_list)
        
        # 高さの設定
        scroll_area.setMinimumHeight(150)
        scroll_area.setMaximumHeight(200)
        
        section.add_content_widget(scroll_area)
        
        return section

    def create_inflation_panel(self):
        """障害物膨張(Nav2 global costmap)の設定パネルを作成"""
        section = CollapsibleSection("Obstacle Inflation (Nav2)")

        content = QWidget()
        content.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 10px;
            }
        """)
        content_layout = QVBoxLayout(content)

        self.inflation_enable_cb = QCheckBox("Enable inflation (Nav2 costmap colors)")
        self.inflation_enable_cb.setChecked(False)
        self.inflation_enable_cb.setToolTip(
            "Nav2 global_costmap の inflation_layer と同じ膨張を表示します"
        )
        content_layout.addWidget(self.inflation_enable_cb)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)

        self.inflation_radius_spin = QDoubleSpinBox()
        self.inflation_radius_spin.setRange(0.0, 10.0)
        self.inflation_radius_spin.setSingleStep(0.05)
        self.inflation_radius_spin.setDecimals(2)
        self.inflation_radius_spin.setValue(0.75)
        self.inflation_radius_spin.setSuffix(" m")
        form.addWidget(QLabel("Inflation radius"), 0, 0)
        form.addWidget(self.inflation_radius_spin, 0, 1)

        self.inflation_cost_scaling_spin = QDoubleSpinBox()
        self.inflation_cost_scaling_spin.setRange(0.0, 50.0)
        self.inflation_cost_scaling_spin.setSingleStep(0.5)
        self.inflation_cost_scaling_spin.setDecimals(1)
        self.inflation_cost_scaling_spin.setValue(3.0)
        form.addWidget(QLabel("Cost scaling factor"), 1, 0)
        form.addWidget(self.inflation_cost_scaling_spin, 1, 1)

        self.inflation_inscribed_spin = QDoubleSpinBox()
        self.inflation_inscribed_spin.setRange(0.0, 5.0)
        self.inflation_inscribed_spin.setSingleStep(0.05)
        self.inflation_inscribed_spin.setDecimals(2)
        self.inflation_inscribed_spin.setValue(0.35)
        self.inflation_inscribed_spin.setSuffix(" m")
        self.inflation_inscribed_spin.setToolTip(
            "内接半径。ロボットfootprintから自動算出（手動で上書きも可）"
        )
        form.addWidget(QLabel("Inscribed radius"), 2, 0)
        form.addWidget(self.inflation_inscribed_spin, 2, 1)

        # ロボットの幾何サイズ（footprint）。内接半径はこの4値の最小値から自動算出する。
        form.addWidget(QLabel("Robot footprint (m)"), 3, 0)

        self.footprint_front_spin = QDoubleSpinBox()
        self.footprint_back_spin = QDoubleSpinBox()
        self.footprint_left_spin = QDoubleSpinBox()
        self.footprint_right_spin = QDoubleSpinBox()
        footprint_specs = (
            (self.footprint_front_spin, "Front (+x)", 0.50),
            (self.footprint_back_spin, "Back (-x)", 0.70),
            (self.footprint_left_spin, "Left (+y)", 0.35),
            (self.footprint_right_spin, "Right (-y)", 0.35),
        )
        for row, (spin, label, default) in enumerate(footprint_specs, start=4):
            spin.setRange(0.0, 5.0)
            spin.setSingleStep(0.05)
            spin.setDecimals(2)
            spin.setValue(default)
            spin.setSuffix(" m")
            form.addWidget(QLabel(label), row, 0)
            form.addWidget(spin, row, 1)

        content_layout.addLayout(form)

        # 不透明度
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Opacity"))
        self.inflation_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.inflation_opacity_slider.setRange(0, 100)
        self.inflation_opacity_slider.setValue(20)
        self.inflation_opacity_label = QLabel("20%")
        self.inflation_opacity_label.setMinimumWidth(40)
        self.inflation_opacity_slider.valueChanged.connect(
            lambda value: self.inflation_opacity_label.setText(f"{value}%")
        )
        opacity_row.addWidget(self.inflation_opacity_slider, stretch=1)
        opacity_row.addWidget(self.inflation_opacity_label)
        content_layout.addLayout(opacity_row)

        reset_button = QPushButton("Reset to Sirius Nav2 defaults")
        reset_button.setToolTip("inflation_radius=0.75, cost_scaling_factor=3.0, inscribed=0.35")
        reset_button.clicked.connect(self.reset_inflation_defaults)
        content_layout.addWidget(reset_button)

        section.add_content_widget(content)

        # 変更をまとめて通知
        self.inflation_enable_cb.toggled.connect(self._emit_inflation_changed)
        self.inflation_radius_spin.valueChanged.connect(self._emit_inflation_changed)
        self.inflation_cost_scaling_spin.valueChanged.connect(self._emit_inflation_changed)
        self.inflation_inscribed_spin.valueChanged.connect(self._emit_inflation_changed)
        self.inflation_opacity_slider.valueChanged.connect(self._emit_inflation_changed)

        # footprint変更時は内接半径を自動算出（シリウスfootprintなら0.35m）
        for spin, _label, _default in footprint_specs:
            spin.valueChanged.connect(self._update_inscribed_from_footprint)

        return section

    @staticmethod
    def sirius_footprint_defaults():
        """シリウスのfootprint [front, back, left, right] (m)。params/nav2_params.yaml 由来。"""
        return (0.50, 0.70, 0.35, 0.35)

    def _update_inscribed_from_footprint(self, *args):
        """footprintの4値の最小値を内接半径として反映する。"""
        inscribed = min(
            float(self.footprint_front_spin.value()),
            float(self.footprint_back_spin.value()),
            float(self.footprint_left_spin.value()),
            float(self.footprint_right_spin.value()),
        )
        self.inflation_inscribed_spin.setValue(round(inscribed, 3))

    def _emit_inflation_changed(self, *args):
        """膨張設定の変更を1つのシグナルで通知する。"""
        self.inflation_changed.emit(
            self.inflation_enable_cb.isChecked(),
            float(self.inflation_radius_spin.value()),
            float(self.inflation_cost_scaling_spin.value()),
            float(self.inflation_inscribed_spin.value()),
            int(self.inflation_opacity_slider.value()),
        )

    def reset_inflation_defaults(self):
        """シリウスのNav2 global_costmapと同じ膨張設定・footprintへ戻す。"""
        front, back, left, right = self.sirius_footprint_defaults()
        self.footprint_front_spin.setValue(front)
        self.footprint_back_spin.setValue(back)
        self.footprint_left_spin.setValue(left)
        self.footprint_right_spin.setValue(right)
        self.inflation_radius_spin.setValue(0.75)
        self.inflation_cost_scaling_spin.setValue(3.0)
        self.inflation_inscribed_spin.setValue(min(front, back, left, right))
        self.inflation_opacity_slider.setValue(20)

    def create_waypoint_panel(self):
        """ウェイポイントリストパネルを作成"""
        section = CollapsibleSection("Waypoints")
        
        # パス生成ボタン（トグルボタンに変更）
        self.generate_path_button = QPushButton("Generate Path")
        self.generate_path_button.setCheckable(True)  # トグルボタンに設定
        self.generate_path_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:checked {
                background-color: #45a049;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.generate_path_button.clicked.connect(self.handle_path_toggle)
        
        # 全削除ボタン
        clear_button = QPushButton("×")
        clear_button.setFixedSize(20, 20)
        clear_button.setToolTip("すべてのウェイポイントを削除")
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ff5252;
            }
        """)
        clear_button.clicked.connect(self.all_waypoints_delete_requested.emit)
        
        # パス生成ボタンと全削除ボタンの間にインポートボタンを追加
        import_button = QPushButton("Import Waypoints")
        import_button.setToolTip("Import Waypoints from YAML")
        import_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 12px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        import_button.clicked.connect(self.handle_import_waypoints)
        
        section.add_header_widget(import_button)  # インポートボタンを追加
        section.add_header_stretch()
        section.add_header_widget(self.generate_path_button)
        section.add_header_widget(clear_button)
        
        # スクロールエリアの作成と設定を更新
        self.scroll_area = QScrollArea()  # インスタンス変数として保存
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)

        # ウェイポイントリストのコンテナウィジェット
        self.waypoint_list = QWidget()
        self.waypoint_list.setStyleSheet("""
            QWidget {
                background-color: white;
                padding: 5px;
            }
        """)
        
        self.waypoint_list_layout = QVBoxLayout(self.waypoint_list)
        self.waypoint_list_layout.setSpacing(2)
        self.waypoint_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # スクロールエリアにウェイポイントリストを設定
        self.scroll_area.setWidget(self.waypoint_list)
        
        # 固定の高さを設定
        self.scroll_area.setMinimumHeight(150)
        self.scroll_area.setMaximumHeight(300)
        
        section.add_content_widget(self.scroll_area)
        
        return section

    def create_landmark_panel(self):
        """ランドマークリストパネルを作成"""
        section = CollapsibleSection("Landmarks")

        import_button = QPushButton("Import")
        import_button.setToolTip("Import Landmarks YAML/JSON")
        import_button.clicked.connect(self.handle_import_landmarks)

        export_button = QPushButton("Export")
        export_button.setToolTip("Export Landmarks YAML/JSON")
        export_button.clicked.connect(self.landmark_export_requested.emit)

        clear_button = QPushButton("×")
        clear_button.setFixedSize(20, 20)
        clear_button.setToolTip("すべてのランドマークを削除")
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        clear_button.clicked.connect(self.all_landmarks_delete_requested.emit)

        section.add_header_widget(import_button)
        section.add_header_widget(export_button)
        section.add_header_stretch()
        section.add_header_widget(clear_button)

        self.landmark_scroll_area = QScrollArea()
        self.landmark_scroll_area.setWidgetResizable(True)
        self.landmark_scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)

        self.landmark_list = QWidget()
        self.landmark_list.setStyleSheet("""
            QWidget {
                background-color: white;
                padding: 5px;
            }
        """)
        self.landmark_list_layout = QVBoxLayout(self.landmark_list)
        self.landmark_list_layout.setSpacing(2)
        self.landmark_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.landmark_scroll_area.setWidget(self.landmark_list)
        self.landmark_scroll_area.setMinimumHeight(120)
        self.landmark_scroll_area.setMaximumHeight(220)

        section.add_content_widget(self.landmark_scroll_area)

        return section

    def create_export_panel(self):
        """エクスポートパネルを作成"""
        section = CollapsibleSection("Export")
        
        # コンテンツエリア
        content = QWidget()
        content.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 10px;
            }
        """)
        content_layout = QVBoxLayout(content)
        
        # チェックボックス
        self.export_pgm_cb = QCheckBox("Export PGM with drawings")
        self.export_waypoints_cb = QCheckBox("Export Waypoints YAML")
        self.export_landmarks_cb = QCheckBox("Export Landmarks YAML")
        
        # ボタンのレイアウト
        button_layout = QHBoxLayout()
        
        # エクスポートボタン
        export_button = QPushButton("Export Selected")
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 3px;
                padding: 8px;
                font-size: 12px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        export_button.clicked.connect(self.handle_export)

        # 地図全体（地図＋ウェイポイント＋路面マッピング＋パス）を1枚の画像で保存
        save_image_button = QPushButton("Save Map Image")
        save_image_button.setToolTip(
            "地図全体を1枚の画像として保存（地図＋ウェイポイント＋路面マッピング＋パス）"
        )
        save_image_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 3px;
                padding: 8px;
                font-size: 12px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        save_image_button.clicked.connect(self.map_image_requested.emit)
        
        # レイアウトに追加（インポートボタン関連の行を削除）
        content_layout.addWidget(self.export_pgm_cb)
        content_layout.addWidget(self.export_waypoints_cb)
        content_layout.addWidget(self.export_landmarks_cb)
        button_layout.addWidget(export_button)
        content_layout.addLayout(button_layout)
        content_layout.addWidget(save_image_button)
        
        section.add_content_widget(content)
        
        return section

    def handle_import_waypoints(self):
        """Waypointのインポート処理"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Import Waypoints YAML",
            "",
            "YAML Files (*.yaml);;All Files (*)"
        )
        if file_name:
            self.waypoint_import_requested.emit(file_name)

    def handle_import_landmarks(self):
        """Landmarkのインポート処理"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Import Landmarks",
            "",
            "Landmark Files (*.yaml *.yml *.json);;YAML Files (*.yaml *.yml);;JSON Files (*.json);;All Files (*)"
        )
        if file_name:
            self.landmark_import_requested.emit(file_name)

    def handle_export(self):
        """エクスポートボタンクリック時の処理"""
        export_pgm = self.export_pgm_cb.isChecked()
        export_waypoints = self.export_waypoints_cb.isChecked()
        export_landmarks = self.export_landmarks_cb.isChecked()
        if export_pgm or export_waypoints:
            self.export_requested.emit(export_pgm, export_waypoints)
        if export_landmarks:
            self.landmark_export_requested.emit()

    # スクロールタイマーの設定用メソッドを追加
    def start_auto_scroll(self):
        if not hasattr(self, 'scroll_timer'):
            self.scroll_timer = QTimer()
            self.scroll_timer.timeout.connect(self.auto_scroll)
            self.scroll_timer.start(50)  # 50ミリ秒ごとにスクロール

    def stop_auto_scroll(self):
        if hasattr(self, 'scroll_timer'):
            self.scroll_timer.stop()
            delattr(self, 'scroll_timer')
            self.scroll_region = None

    def auto_scroll(self):
        """自動スクロールの処理 - スクロール速度を動的に調整"""
        if not hasattr(self, 'scroll_region') or not hasattr(self, 'scroll_area'):
            return
        
        scroll_bar = self.scroll_area.verticalScrollBar()
        current = scroll_bar.value()
        
        # スクロール速度を計算
        # マウス位置に基づいて速度を調整（0.0 〜 1.0の範囲）
        cursor_pos = self.scroll_area.mapFromGlobal(QCursor.pos())
        viewport_height = self.scroll_area.height()
        
        # スクロール領域のマージン（この範囲でスクロール速度が変化）
        margin = 50
        
        if self.scroll_region == 'up':
            # 上端からの距離に基づいて速度を計算
            distance = max(0, cursor_pos.y())
            speed_factor = 1.0 - (distance / margin)
        else:  # 'down'
            # 下端からの距離に基づいて速度を計算
            distance = max(0, viewport_height - cursor_pos.y())
            speed_factor = 1.0 - (distance / margin)
            
        # 速度係数を0.0から1.0の範囲に制限
        speed_factor = max(0.0, min(1.0, speed_factor))
        
        # 基本スクロール速度と最大スクロール速度
        base_speed = 5
        max_speed = 30
        
        # 実際のスクロール速度を計算
        scroll_speed = int(base_speed + (max_speed - base_speed) * speed_factor)
        
        if self.scroll_region == 'up':
            new_value = max(scroll_bar.minimum(), current - scroll_speed)
            scroll_bar.setValue(new_value)
        elif self.scroll_region == 'down':
            new_value = min(scroll_bar.maximum(), current + scroll_speed)
            scroll_bar.setValue(new_value)

        # スクロールが最端に達したら停止
        if (self.scroll_region == 'up' and scroll_bar.value() == scroll_bar.minimum()) or \
           (self.scroll_region == 'down' and scroll_bar.value() == scroll_bar.maximum()):
            self.stop_auto_scroll()

    def handle_path_toggle(self):
        """パスの表示/非表示を切り替え"""
        if self.generate_path_button.isChecked():
            self.generate_path_requested.emit()  # パスを生成
        else:
            # パスを非表示にする
            self.generate_path_requested.emit()  # パスをクリア

    def add_waypoint_to_list(self, waypoint):
        """ウェイポイントリストに新しいウェイポイントを追加"""
        # 既存のウィジェットを更新または新規作成
        if waypoint.number in self.waypoint_widgets:
            self.waypoint_widgets[waypoint.number].update_label(waypoint.display_name)
            return

        # 新しいウェイポイントアイテムを作成
        waypoint_item = WaypointListItem(waypoint)
        self.waypoint_widgets[waypoint.number] = waypoint_item
        # 削除シグナルを親パネルのシグナルに接続
        waypoint_item.delete_clicked.connect(self.waypoint_delete_requested.emit)
        self.waypoint_list_layout.addWidget(waypoint_item)

    def add_landmark_to_list(self, landmark):
        """ランドマークリストにランドマークを追加または更新"""
        if landmark.number in self.landmark_widgets:
            self.landmark_widgets[landmark.number].update_landmark(landmark)
            return

        landmark_item = LandmarkListItem(landmark)
        self.landmark_widgets[landmark.number] = landmark_item
        landmark_item.delete_clicked.connect(self.landmark_delete_requested.emit)
        landmark_item.name_changed.connect(self.landmark_name_changed.emit)
        self.landmark_list_layout.addWidget(landmark_item)

    def remove_waypoint_from_list(self, number):
        """ウェイポイントをリストから削除"""
        if number == -1:  # 全削除の場合
            self.clear_waypoint_list()
            return
            
        if number in self.waypoint_widgets:
            # 古いウィジェットを削除
            widget = self.waypoint_widgets.pop(number)
            self.waypoint_list_layout.removeWidget(widget)
            widget.deleteLater()
            
            # 残りのウィジェットを全て削除（再ナンバリングのため）
            for widget in self.waypoint_widgets.values():
                self.waypoint_list_layout.removeWidget(widget)
                widget.deleteLater()
            self.waypoint_widgets.clear()

    def clear_waypoint_list(self):
        """ウェイポイントリストをクリア"""
        while self.waypoint_list_layout.count():
            item = self.waypoint_list_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        self.waypoint_widgets.clear()

    def remove_landmark_from_list(self, number):
        """ランドマークをリストから削除"""
        if number == -1:
            self.clear_landmark_list()
            return

        if number in self.landmark_widgets:
            widget = self.landmark_widgets.pop(number)
            self.landmark_list_layout.removeWidget(widget)
            widget.deleteLater()

    def clear_landmark_list(self):
        """ランドマークリストをクリア"""
        while self.landmark_list_layout.count():
            item = self.landmark_list_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        self.landmark_widgets.clear()

    def update_layer_list(self, layers):
        """レイヤーリストを更新"""
        # 既存のウィジェットをクリア
        for i in reversed(range(self.layer_list_layout.count())): 
            widget = self.layer_list_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        
        # 各レイヤーのコントロールを追加
        for layer in layers:
            layer_control = LayerControl(layer, self)
            self.layer_list_layout.addWidget(layer_control)

    def handle_waypoint_reorder(self, source_number, target_number):
        """ウェイポイントの順序変更を処理"""
        self.waypoint_reorder_requested.emit(source_number, target_number)

class WaypointListItem(QWidget):
    """ウェイポイントリストの各アイテム用ウィジェット"""
    delete_clicked = Signal(int)
    
    def __init__(self, waypoint):
        super().__init__()
        self.waypoint_number = waypoint.number
        self.waypoint = waypoint
        
        self.setAcceptDrops(True)
        
        # レイアウト設定
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        # カード風のフレーム
        self.frame = QFrame()
        self.frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
            QFrame:focus {
                border: 1px solid #e0e0e0;
                outline: none;
            }
        """)
        
        # フレーム内のレイアウト
        frame_layout = QHBoxLayout(self.frame)
        frame_layout.setContentsMargins(8, 4, 8, 4)
        frame_layout.setSpacing(12)
        
        # ドラッグハンドル
        drag_handle = QLabel("⋮")
        drag_handle.setStyleSheet("""
            QLabel {
                color: #9e9e9e;
                font-size: 16px;
                padding: 0 2px;
            }
        """)
        
        # ウェイポイント番号（青いバッジ風）
        number_badge = QLabel(f"{waypoint.number:02d}")
        number_badge.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #f44336;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
                text-align: center;
            }
        """)
        number_badge.setFixedWidth(40)

        # 手動記録ステータス（manual=true のときだけ「手動」バッジを表示）
        manual_badge = None
        if bool(waypoint.get_attribute('manual', False)):
            manual_badge = QLabel("手動")
            manual_badge.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    background-color: #2e7d32;
                    border-radius: 3px;
                    padding: 2px 6px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)

        # 座標情報（モノスペースフォントで整列）
        self.coord_label = QLabel(f"({waypoint.x:.2f}, {waypoint.y:.2f})")  # インスタンス変数として保存
        self.coord_label.setStyleSheet("""
            QLabel {
                color: #424242;
                font-size: 12px;
            }
            QLabel:focus {
                font-weight: normal;
            }
        """)
        
        # 角度表示（丸いバッジ風）
        degrees = int(waypoint.angle * 180 / np.pi)
        self.angle_label = QLabel(f"{degrees}°")  # インスタンス変数として保存
        self.angle_label.setStyleSheet("""
            QLabel {
                color: #666666;
                background-color: #f5f5f5;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
                min-width: 35px;
                text-align: center;
            }
        """)

        # 削除ボタン
        delete_button = QPushButton("×")
        delete_button.setFixedSize(20, 20)
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666666;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ff5252;
                color: white;
            }
        """)
        delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.waypoint_number))
        
        # フレームにウィジェットを追加
        frame_layout.addWidget(drag_handle)
        frame_layout.addWidget(number_badge)
        if manual_badge is not None:
            frame_layout.addWidget(manual_badge)
        frame_layout.addWidget(self.coord_label, 1)
        frame_layout.addWidget(self.angle_label)
        frame_layout.addWidget(delete_button)
        
        # メインレイアウトにフレームを追加
        layout.addWidget(self.frame)
        
        # ホバー効果とスペーシングのスタイルを修正
        self.setStyleSheet("""
            WaypointListItem {
                background-color: transparent;
                margin: 1px 0;
            }
            WaypointListItem:hover QFrame {
                border: 1px solid #2196F3;
                background-color: #f8f9fa;
            }
            WaypointListItem:focus {
                outline: none;
            }
        """)
        
        # フォーカスポリシーを設定
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.frame.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.coord_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def update_label(self, text):
        """ラベルテキストを更新"""
        # waypoint情報を更新
        if hasattr(self, 'waypoint'):
            degrees = int(self.waypoint.angle * 180 / np.pi)
            self.coord_label.setText(f"({self.waypoint.x:.2f}, {self.waypoint.y:.2f})")
            self.angle_label.setText(f"{degrees}°")

    def mousePressEvent(self, event):
        if not self.isVisible():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                # ドラッグ開始時にタイマーをリセット
                right_panel = self.get_right_panel()
                if (right_panel):
                    right_panel.stop_auto_scroll()
                
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(str(self.waypoint_number))
                drag.setMimeData(mime_data)
                
                # ドラッグ中のイベントを監視
                drag.exec(Qt.DropAction.MoveAction)
            except RuntimeError:
                pass
        # マウスイベントの伝播を停止（super呼び出しを削除）

    def mouseMoveEvent(self, event):
        # ドラッグ中のマウス位置を取得して自動スクロールの判定
        right_panel = self.get_right_panel()
        if right_panel and hasattr(right_panel, 'scroll_area'):
            scroll_area = right_panel.scroll_area
            pos_in_scroll = scroll_area.mapFromGlobal(self.mapToGlobal(event.position().toPoint()))
            
            # スクロール領域の上下端から20ピクセルの範囲を自動スクロール領域とする
            scroll_margin = 20
            
            if pos_in_scroll.y() < scroll_margin:
                right_panel.scroll_region = 'up'
                right_panel.start_auto_scroll()
            elif pos_in_scroll.y() > scroll_area.height() - scroll_margin:
                right_panel.scroll_region = 'down'
                right_panel.start_auto_scroll()
            else:
                right_panel.stop_auto_scroll()
        
        super().mouseMoveEvent(event)

    def dragMoveEvent(self, event):
        """ドラッグ中の自動スクロール制御を改善"""
        right_panel = self.get_right_panel()
        if right_panel and hasattr(right_panel, 'scroll_area'):
            scroll_area = right_panel.scroll_area
            pos_in_scroll = scroll_area.mapFromGlobal(QCursor.pos())
            
            # スクロール領域のマージンを広げる
            scroll_margin = 50
            
            if pos_in_scroll.y() < scroll_margin:
                right_panel.scroll_region = 'up'
                right_panel.start_auto_scroll()
            elif pos_in_scroll.y() > scroll_area.height() - scroll_margin:
                right_panel.scroll_region = 'down'
                right_panel.start_auto_scroll()

        event.accept()

    def mouseReleaseEvent(self, event):
        # ドラッグ終了時に自動スクロールを停止
        right_panel = self.get_right_panel()
        if right_panel:
            right_panel.stop_auto_scroll()
        super().mouseReleaseEvent(event)

    def get_right_panel(self):
        """親のRightPanelウィジェットを取得"""
        parent = self.parent()
        while parent and not isinstance(parent, RightPanel):
            parent = parent.parent()
        return parent

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.source() != self:
            event.accept()
            # ドラッグ時のスタイル変更を抑制
            self.frame.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border: 1px solid #2196F3;
                    border-radius: 4px;
                }
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        # ドラッグ離脱時のスタイルを元に戻す
        self.frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        source_number = int(event.mimeData().text())
        target_number = self.waypoint_number
        
        # 同じ項目へのドロップは無視
        if source_number != target_number:
            parent = self.parent()
            while parent and not isinstance(parent, RightPanel):
                parent = parent.parent()
            if parent:
                # ドロップ位置に基づいて順序を変更
                parent.handle_waypoint_reorder(source_number, target_number)
        
        # frameのスタイルを元に戻す
        self.frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        event.accept()

class LandmarkListItem(QWidget):
    """ランドマークリストの各アイテム用ウィジェット"""
    delete_clicked = Signal(int)
    name_changed = Signal(int, str)

    def __init__(self, landmark):
        super().__init__()
        self.landmark_number = landmark.number
        self.landmark = landmark

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.frame = QFrame()
        self.frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)

        frame_layout = QHBoxLayout(self.frame)
        frame_layout.setContentsMargins(8, 4, 8, 4)
        frame_layout.setSpacing(8)

        number_badge = QLabel(f"{landmark.number:02d}")
        number_badge.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #2ea043;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        number_badge.setFixedWidth(40)

        self.name_edit = QLineEdit(landmark.name)
        self.name_edit.setMinimumWidth(90)
        self.name_edit.editingFinished.connect(self.emit_name_changed)

        self.coord_label = QLabel()
        self.coord_label.setStyleSheet("color: #424242; font-size: 11px;")

        delete_button = QPushButton("×")
        delete_button.setFixedSize(20, 20)
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666666;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ff5252;
                color: white;
            }
        """)
        delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.landmark_number))

        frame_layout.addWidget(number_badge)
        frame_layout.addWidget(self.name_edit, 1)
        frame_layout.addWidget(self.coord_label)
        frame_layout.addWidget(delete_button)
        layout.addWidget(self.frame)

        self.update_landmark(landmark)

    def update_landmark(self, landmark):
        self.landmark = landmark
        self.landmark_number = landmark.number
        if self.name_edit.text() != landmark.name:
            self.name_edit.blockSignals(True)
            self.name_edit.setText(landmark.name)
            self.name_edit.blockSignals(False)
        degrees = int(landmark.angle * 180 / np.pi)
        self.coord_label.setText(f"({landmark.x:.2f}, {landmark.y:.2f}) {degrees}°")

    def emit_name_changed(self):
        self.name_changed.emit(self.landmark_number, self.name_edit.text())

class MainWindow(QMainWindow):
    """メインウィンドウ
    アプリケーションの主要なUIと機能を統合"""
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet(COMMON_STYLES)
        self.setWindowTitle("Map and Waypoint Editor")  # ウィンドウタイトルを日本語に
        self.setGeometry(100, 100, 1200, 1000)
        
        # メインウィジェットとレイアウト
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左側パネル
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(5) # スペースを追加
        left_layout.setContentsMargins(5, 5, 5, 5) # マージンを追加
        
        # メニューパネル
        self.menu_panel = MenuPanel()
        
        # 画像ビューア
        self.image_viewer = ImageViewer()
        
        # シグナルの接続（シグナルが発生したときにスロットを呼び出す）
        self.menu_panel.file_selected.connect(self.load_pgm_file)
        self.menu_panel.zoom_value_changed.connect(self.handle_zoom_value_changed)
        # ImageViewerからのスケール変更通知を処理
        self.image_viewer.scale_changed.connect(self.handle_scale_changed)
        
        # グリッドボタンのシグナルを接続
        self.menu_panel.grid_button.clicked.connect(self.image_viewer.toggle_grid)

        # YAMLファイル選択時の処理を接続
        self.menu_panel.yaml_selected.connect(self.load_yaml_file)

        # 路面マップ選択時の処理を接続
        self.menu_panel.roadmap_selected.connect(self.load_roadmap_file)

        # 戻る/進むボタンのシグナルを接続
        self.menu_panel.undo_requested.connect(self.image_viewer.undo)
        self.menu_panel.redo_requested.connect(self.image_viewer.redo)

        # 地図全体の画像保存を接続
        self.menu_panel.map_image_requested.connect(self.export_map_image)
        
        # 履歴状態の変更を監視
        self.image_viewer.history_changed.connect(self.update_history_buttons)

        # 左側レイアウトの構成
        left_layout.addWidget(self.menu_panel)
        left_layout.addWidget(self.image_viewer)
        left_widget.setLayout(left_layout)
        
        # 右側パネル
        self.right_panel = RightPanel()
        
        # スプリッタの設定
        splitter.addWidget(left_widget)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([600, 400])
        
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # レイヤー状態変更時の更新処理を接続
        self.image_viewer.layer_changed.connect(self.update_layer_panel)
        
        # 初期レイヤーパネルの更新を追加
        self.update_layer_panel()  # この行を追加

        # ウェイポイント追加時の処理を接続
        self.image_viewer.waypoint_added.connect(self.right_panel.add_waypoint_to_list)

        # ウェイポイント削除時の処理を接続
        self.image_viewer.waypoint_removed.connect(self.right_panel.remove_waypoint_from_list)
        
        # 削除ボタンクリック時の処理を接続（修正版）
        self.right_panel.waypoint_delete_requested.connect(self.image_viewer.remove_waypoint)

        # 全ウェイポイント削除時の処理を接続
        self.right_panel.all_waypoints_delete_requested.connect(self.image_viewer.remove_all_waypoints)

        # ウェイポイントの順序変更時の処理を接続
        self.right_panel.waypoint_reorder_requested.connect(
            self.image_viewer.reorder_waypoints)

        # パス生成時の処理を接続
        self.right_panel.generate_path_requested.connect(
            self.image_viewer.generate_path)

        # ウェイポイント編集時の処理を接続
        self.image_viewer.waypoint_edited.connect(self.right_panel.add_waypoint_to_list)

        # エクスポート時の処理を接続
        self.right_panel.export_requested.connect(self.handle_export)

        # 地図全体の画像保存時の処理を接続
        self.right_panel.map_image_requested.connect(self.export_map_image)

        # 障害物膨張(Nav2)設定の変更を接続
        self.right_panel.inflation_changed.connect(self.handle_inflation_changed)

        # インポート時の処理を接続
        self.right_panel.waypoint_import_requested.connect(self.import_waypoints_yaml)

        # ランドマーク関連の処理を接続
        self.image_viewer.landmark_added.connect(self.right_panel.add_landmark_to_list)
        self.image_viewer.landmark_edited.connect(self.right_panel.add_landmark_to_list)
        self.image_viewer.landmark_removed.connect(self.right_panel.remove_landmark_from_list)
        self.right_panel.landmark_delete_requested.connect(self.image_viewer.remove_landmark)
        self.right_panel.all_landmarks_delete_requested.connect(self.image_viewer.remove_all_landmarks)
        self.right_panel.landmark_name_changed.connect(self.handle_landmark_name_changed)
        self.right_panel.landmark_import_requested.connect(self.import_landmarks_file)
        self.right_panel.landmark_export_requested.connect(self.export_landmarks_file)

    def keyPressEvent(self, event):
        """F11で全画面切替、Escで全画面解除"""
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            event.accept()
            return
        super().keyPressEvent(event)

    def toggle_fullscreen(self):
        """全画面表示を切り替え"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def update_layer_panel(self):
        """レイヤーパネルの表示を更新"""
        if hasattr(self, 'right_panel') and hasattr(self, 'image_viewer'):
            self.right_panel.update_layer_list(self.image_viewer.layers)

    def load_pgm_file(self, file_path):
        """PGMファイルを読み込む
        Parameters:
            file_path (str): 読み込むPGMファイルのパス
        """
        try:
            with open(file_path, 'rb') as f:
                magic = f.readline().decode('ascii').strip()
                if (magic != 'P5'):
                    raise ValueError('Not a P5 PGM file')

                while True:
                    line = f.readline().decode('ascii').strip()
                    if not line.startswith('#'):
                        break
                width, height = map(int, line.split())
                max_val = int(f.readline().decode('ascii').strip())
                
                data = f.read()
                img_array = np.frombuffer(data, dtype=np.uint8)
                img_array = img_array.reshape((height, width))
                
                self.image_viewer.load_image(img_array, width, height)
                print(f"Successfully loaded image: {width}x{height}, max value: {255}")

        except Exception as e:
            print(f"Error loading PGM file: {str(e)}")
            import traceback
            traceback.print_exc()

    def load_roadmap_file(self, file_path):
        """路面マッピング色付き地図を読み込む（原点合わせはJSONのresolution/origin）"""
        self.image_viewer.load_roadmap_file(file_path)
        self.update_layer_panel()

    def handle_zoom_value_changed(self, value):
        """ズームスライダーの値変更を処理
        Parameters:
            value (int): スライダーの現在値（1-100）
        """
        scale_factor = value / 50.0
        self.image_viewer.scale_factor = scale_factor
        self.image_viewer.update_display()

    def handle_scale_changed(self, scale_factor):
        """ImageViewerからのスケール変更通知を処理"""
        # スライダー値を更新（シグナルの発行を防ぐためにblockSignals使用）
        slider_value = int(scale_factor * 50)
        self.menu_panel.zoom_slider.blockSignals(True)
        self.menu_panel.zoom_slider.setValue(slider_value)
        self.menu_panel.zoom_slider.blockSignals(False)
        # ズーム率表示を更新
        zoom_percent = int(scale_factor * 100)
        self.menu_panel.zoom_label.setText(f"{zoom_percent}%")

    def load_yaml_file(self, file_path):
        """YAMLファイルの読み込みとPGMファイルの自動読み込み"""
        try:
            # YAMLファイルを読み込む
            with open(file_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
            
            # YAMLファイルのディレクトリパスを取得
            yaml_dir = os.path.dirname(file_path)
            
            # 画像ファイルのパスを取得し、関連するPGMファイルを読み込む
            if 'image' in yaml_data:
                pgm_filename = yaml_data['image']
                # 相対パスの場合はYAMLファイルのディレクトリを基準に絶対パスを構築
                if not os.path.isabs(pgm_filename):  # !を notに修正
                    pgm_path = os.path.join(yaml_dir, pgm_filename)
                else:
                    pgm_path = pgm_filename
                
                # PGMファイルが存在する場合は読み込む
                if os.path.exists(pgm_path):
                    # ファイル名ラベルを更新
                    self.menu_panel.file_name_label.setText(os.path.basename(pgm_path))
                    # PGMファイルを読み込む
                    self.load_pgm_file(pgm_path)
                else:
                    print(f"PGM file not found: {pgm_path}")
            
            # 原点情報などのYAMLデータを読み込む
            self.image_viewer.load_yaml_file(file_path)
            
        except Exception as e:
            print(f"Error loading YAML file: {str(e)}")
            import traceback
            traceback.print_exc()

    def handle_export(self, export_pgm, export_waypoints):
        """エクスポート処理"""
        if export_pgm:
            # PGM & YAMLのエクスポート
            self.export_pgm_with_drawings()
        if export_waypoints:
            self.export_waypoints_yaml()

    def handle_inflation_changed(self, enabled, radius, cost_scaling, inscribed, opacity):
        """障害物膨張(Nav2)設定の変更をImageViewerへ反映する。"""
        self.image_viewer.set_inflation(enabled, radius, cost_scaling, inscribed, opacity)

    def export_pgm_with_drawings(self):
        """描画込みのPGMファイルをエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export PGM with drawings",
            "",
            "PGM Files (*.pgm);;All Files (*)"
        )
        if file_name:
            # ImageViewerの現在の表示内容をPGMとして保存
            pixmap = self.image_viewer.get_combined_pixmap()
            if (pixmap):
                image = pixmap.toImage()
                # グレースケールに変換して保存
                gray_image = image.convertToFormat(QImage.Format.Format_Grayscale8)
                gray_image.save(file_name, "PGM")

                # 関連するYAMLファイルを作成
                yaml_file_name = os.path.splitext(file_name)[0] + '.yaml'
                pgm_file_name = os.path.basename(file_name)

                # YAMLデータの作成
                yaml_data = {
                    'image': pgm_file_name,
                    'mode': 'trinary',
                    'resolution': self.image_viewer.resolution,
                    'origin': [0, 0, 0],  # デフォルト値
                    'negate': 0,
                    'occupied_thresh': 0.65,
                    'free_thresh': 0.25
                }

                # 原点情報が存在する場合は更新
                if self.image_viewer.origin_point:
                    origin_x = -self.image_viewer.origin_point[0] * self.image_viewer.resolution
                    origin_y = -(self.image_viewer.pgm_layer.pixmap.height() - 
                               self.image_viewer.origin_point[1]) * self.image_viewer.resolution
                    yaml_data['origin'] = [origin_x, origin_y, 0]

                # YAMLファイルを保存
                try:
                    with open(yaml_file_name, 'w') as f:
                        yaml.dump(yaml_data, f, default_flow_style=None)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Error saving YAML file: {str(e)}")

    def export_map_image(self):
        """地図全体（地図＋ウェイポイント＋路面マッピング＋パス）を1枚の画像として保存する。"""
        if not self.image_viewer.pgm_layer.pixmap:
            QMessageBox.warning(self, "No Map", "先に地図を読み込んでください。")
            return

        file_name, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Map Image",
            "",
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;BMP Image (*.bmp);;All Files (*)"
        )
        if not file_name:
            return

        # 拡張子が無い場合は選択したフィルタから補完
        _, ext = os.path.splitext(file_name)
        if not ext:
            lowered = selected_filter.lower()
            if "jpg" in lowered or "jpeg" in lowered:
                file_name += ".jpg"
            elif "bmp" in lowered:
                file_name += ".bmp"
            else:
                file_name += ".png"

        pixmap = self.image_viewer.render_composite_pixmap()
        if pixmap is None:
            QMessageBox.warning(self, "Error", "地図画像を生成できませんでした。")
            return

        if pixmap.save(file_name):
            QMessageBox.information(
                self, "Saved", f"地図全体の画像を保存しました:\n{file_name}"
            )
        else:
            QMessageBox.critical(self, "Error", f"画像の保存に失敗しました:\n{file_name}")

    def export_waypoints_yaml(self):
        """ウェイポイントをYAMLファイルとしてエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Waypoints YAML",
            "",
            "YAML Files (*.yaml);;All Files (*)"
        )
        if file_name:
            # OrderedDictの特別なシリアライザを定義
            def ordered_dict_representer(dumper, data):
                return dumper.represent_mapping('tag:yaml.org,2002:map', dict(data.items()))
            yaml.add_representer(OrderedDict, ordered_dict_representer)
            
            waypoints_data = []
            current_format = format_manager.get_format() # 現在のフォーマットを取得
            
            for wp in self.image_viewer.waypoints:
                waypoint_data = {}
                for key in current_format['format'].keys():
                    value = self.get_waypoint_value(wp, key, current_format['format'][key])
                    if value is not None:
                        waypoint_data[key] = value
                waypoints_data.append(waypoint_data)
            
            data = {
                'format_version': current_format['version'],
                'waypoints': waypoints_data
            }
            
            try:
                with open(file_name, 'w') as f:
                    # boolとstringが正しく出力されるようにカスタムダンパーを設定
                    class CleanDumper(yaml.SafeDumper):
                        pass
                    
                    # boolはtrue/falseで出力（クォートなし）
                    CleanDumper.add_representer(bool, 
                        lambda dumper, data: dumper.represent_bool(data))
                    
                    # 文字列は必要な場合のみクォート（通常はクォートなし）
                    def str_representer(dumper, data):
                        # 空文字列や特殊文字を含む場合のみクォート
                        if data == '' or any(c in data for c in ':{}[]&*#?|-<>=!%@\\'):
                            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")
                        return dumper.represent_scalar('tag:yaml.org,2002:str', data)
                    CleanDumper.add_representer(str, str_representer)
                    
                    yaml.dump(data, f, 
                            default_flow_style=False,
                            sort_keys=False,
                            allow_unicode=True,
                            Dumper=CleanDumper)
            except Exception as e:
                print(f"Error saving waypoints YAML: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to save waypoints: {str(e)}")

    def import_waypoints_yaml(self, file_path):
        """Waypointの設定をYAMLファイルからインポート"""
        try:
            with open(file_path, 'r') as f:
                # 順序を保持してYAMLを読み込む
                data = yaml.safe_load(f)
                # データをOrderedDictに変換
                ordered_data = OrderedDict()
                for key in data:
                    if key == 'waypoints':
                        ordered_data[key] = [OrderedDict(wp) for wp in data[key]]
                    else:
                        ordered_data[key] = data[key]
            
            current_format = format_manager.get_format()
            
            if 'format_version' in ordered_data:
                if ordered_data['format_version'] != current_format['version']:
                    response = QMessageBox.question(
                        self,
                        "Version Mismatch",
                        f"File format version ({ordered_data['format_version']}) differs from current version ({current_format['version']}). Continue?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if response == QMessageBox.StandardButton.No:
                        return
            
            self.image_viewer.import_waypoints_from_yaml(ordered_data)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error importing waypoints: {str(e)}")

    def handle_landmark_name_changed(self, number, name):
        """右パネルでランドマーク名が変更されたときの処理"""
        landmark = next((lm for lm in self.image_viewer.landmarks if lm.number == number), None)
        if not landmark:
            return
        landmark.set_name(name)
        self.image_viewer.landmark_edited.emit(landmark)
        self.image_viewer.update_display()

    def export_landmarks_file(self):
        """ランドマークをYAML/JSONとしてエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Landmarks",
            "",
            "YAML Files (*.yaml *.yml);;JSON Files (*.json);;All Files (*)"
        )
        if not file_name:
            return
        if not os.path.splitext(file_name)[1]:
            file_name += ".yaml"

        data = self.image_viewer.export_landmarks_data()
        try:
            with open(file_name, 'w') as f:
                if file_name.lower().endswith('.json'):
                    json.dump(data, f, ensure_ascii=False, indent=2)
                else:
                    yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save landmarks: {str(e)}")

    def import_landmarks_file(self, file_path):
        """ランドマークをYAML/JSONからインポート"""
        try:
            with open(file_path, 'r') as f:
                if file_path.lower().endswith('.json'):
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
            self.image_viewer.import_landmarks_from_data(data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error importing landmarks: {str(e)}")

    def update_history_buttons(self, can_undo, can_redo):
        """戻る/進むボタンの状態を更新"""
        self.menu_panel.update_undo_redo_actions(can_undo, can_redo)

    def get_waypoint_value(self, waypoint, key, type_info):
        """ウェイポイントから指定されたキーの値を取得し、適切な型に変換"""
        if key == 'number':
            return waypoint.number
        elif key == 'x':
            return round(float(waypoint.x), 3)
        elif key == 'y':
            return round(float(waypoint.y), 3)
        elif key == 'angle_radians':
            return round(float(waypoint.angle), 3) 
        else:
            # カスタム属性の場合
            default_value = WAYPOINT_ATTRIBUTE_DEFAULTS.get(key, None)
            value = waypoint.get_attribute(key, default_value)
            if value is not None:
                converted = self.convert_value(value, type_info)
                # デフォルト値のアクションは未設定としてYAMLから省略する
                if (key in WAYPOINT_ATTRIBUTE_DEFAULTS and
                        converted == WAYPOINT_ATTRIBUTE_DEFAULTS[key]):
                    return None
                # 文字列が空の場合は出力しない（None返す）
                # boolはtrue/false両方出力する
                if ((type_info == 'string' or type_info == 'str') and
                        converted == '' and key not in WAYPOINT_ATTRIBUTE_DEFAULTS):
                    return None
                return converted
        return None

    def convert_value(self, value, type_info):
        """値を指定された型に変換"""
        try:
            if type_info == 'int':
                return int(value)
            elif type_info == 'float':
                return float(value)
            elif type_info == 'str' or type_info == 'string':
                # 文字列として返す（YAMLでクォートなしで出力される）
                return str(value)
            elif type_info == 'bool':
                # 文字列の場合は適切にboolに変換
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            else:
                return value
        except (ValueError, TypeError):
            return value

class FormatManager:
    def __init__(self):
        self._format = WAYPOINT_FORMAT
        self._observers = []

    def get_format(self):
        return self._format

    def set_format(self, new_format):
        # 辞書をOrderedDictに変換
        if isinstance(new_format, dict):
            ordered_format = OrderedDict()
            for key in new_format:
                if key == 'format' and isinstance(new_format[key], dict):
                    ordered_format[key] = OrderedDict(new_format[key])
                else:
                    ordered_format[key] = new_format[key]
            self._format = ordered_format
        else:
            self._format = new_format
        self._notify_observers()

    def add_observer(self, observer):
        self._observers.append(observer)

    def _notify_observers(self):
        for observer in self._observers:
            observer(self._format)

# FormatManagerのグローバルインスタンス
format_manager = FormatManager()

class FormatEditorPanel(QFrame):
    format_updated = Signal(dict)  # フォーマット更新時のシグナル

    def __init__(self):
        super().__init__()
        self.setAutoFillBackground(True)
        # デフォルトのフォーマットを保存
        self.default_format = WAYPOINT_FORMAT
        self.setup_ui()
        format_manager.add_observer(self.on_format_changed)

    def setup_ui(self):
        # パネル自体のスタイルを設定
        self.setStyleSheet("""
            FormatEditorPanel {
                background-color: #f5f5f5;
                border-radius: 5px;
            }
            QWidget#contentWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 10px;
            }
            QTextEdit {
                font-family: monospace;
                font-size: 13pt;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px;
                background-color: white;
                min-height: 150px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)  # マージンを追加
        
        # 折りたたみ可能なセクション（Format Editor + パラメータ解説ボタン）
        self.section = CollapsibleSection("Format Editor")
        self.help_button = QPushButton("パラメータ解説")
        self.help_button.setCheckable(True)
        self.help_button.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                padding: 4px 10px;
                border-radius: 3px;
                min-width: 110px;
            }
            QPushButton:hover { background-color: #546E7A; }
            QPushButton:checked { background-color: #37474F; }
        """)
        self.help_button.toggled.connect(self.toggle_help)
        self.section.add_header_stretch()
        self.section.add_header_widget(self.help_button)

        # コンテンツエリア
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")  # スタイルシートで参照するためのID
        content_widget.setMinimumHeight(200)
        
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # エディタ
        self.editor = QTextEdit()
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # ボタンレイアウト
        button_layout = QHBoxLayout()
        
        # 更新ボタン
        update_button = QPushButton("Update Format")
        update_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        update_button.clicked.connect(self.update_format)

        # リセットボタン
        reset_button = QPushButton("Reset to Default")
        reset_button.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        reset_button.clicked.connect(self.reset_to_default)
        
        # エクスポートボタン
        export_button = QPushButton("Export Format")
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        export_button.clicked.connect(self.export_format)
        
        # インポートボタン
        import_button = QPushButton("Import Format")
        import_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        import_button.clicked.connect(self.import_format)

        # ボタンをレイアウトに追加
        button_layout.addWidget(update_button)
        button_layout.addWidget(reset_button)
        button_layout.addWidget(export_button)
        button_layout.addWidget(import_button)
        
        # コンテンツレイアウトに要素を追加
        content_layout.addWidget(self.editor)
        content_layout.addLayout(button_layout)

        # セクション本文にコンテンツを追加
        self.section.add_content_widget(content_widget)

        # デフォルトパラメータの解説（ボタンで開閉・既定は折りたたみ）
        self.help_box = QTextEdit()
        self.help_box.setReadOnly(True)
        self.help_box.setPlainText(WAYPOINT_PARAM_HELP)
        self.help_box.setStyleSheet("""
            QTextEdit {
                font-family: sans-serif;
                font-size: 11px;
                background-color: #fafafa;
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 6px;
                min-height: 150px;
            }
        """)
        self.help_box.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.help_box.setVisible(False)  # 既定は折りたたみ
        self.section.add_content_widget(self.help_box)

        # メインレイアウトにセクションを追加
        layout.addWidget(self.section)

        # 初期フォーマットを表示
        self.show_current_format()

    def toggle_help(self, checked):
        """パラメータ解説の表示/非表示を切り替える（既定は非表示）。"""
        self.help_box.setVisible(bool(checked))
        self.help_button.setText("パラメータ解説を閉じる" if checked else "パラメータ解説")

    def reset_to_default(self):
        """フォーマットをデフォルトに戻す"""
        # デフォルトのフォーマットを設定
        format_manager.set_format(self.default_format)
        self.show_current_format()
        QMessageBox.information(self, "Success", "Format reset to default")

    def show_current_format(self):
        """現在のフォーマットを表示"""
        # カスタムYAML表示形式を使用
        format_data = format_manager.get_format()
        formatted_text = (
            f"version: '{format_data['version']}'\n"
            f"format:\n"
        )
        
        # format内の各項目を整形
        for key, value in format_data['format'].items():
            formatted_text += f"  {key}: {value}\n"
        
        self.editor.setText(formatted_text)

    def update_format(self):
        try:
            # テキストをYAMLとしてパース
            new_format = yaml.safe_load(self.editor.toPlainText())
            # OrderedDictに変換して順序を保持
            ordered_format = OrderedDict([
                ('version', new_format['version']),
                ('format', OrderedDict())
            ])
            
            # format内の項目を順序を保持して変換
            for key, value in new_format['format'].items():
                ordered_format['format'][key] = value
            
            # 必要なキーの存在チェック
            if 'version' not in ordered_format or 'format' not in ordered_format:
                raise ValueError("Format must contain 'version' and 'format' keys")
            
            # フォーマットを更新
            format_manager.set_format(ordered_format)
            self.format_updated.emit(ordered_format)
            
            # 成功メッセージを表示
            QMessageBox.information(self, "Success", "Format updated successfully")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Invalid format: {str(e)}")
            
    def export_format(self):
        """フォーマットをYAMLファイルとしてエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Format",
            "",
            "YAML Files (*.yaml);;All Files (*)"
        )
        if file_name:
            try:
                # カスタム形式でフォーマットを書き出し
                format_data = format_manager.get_format()
                with open(file_name, 'w') as f:
                    f.write(f"version: '{format_data['version']}'\n")
                    f.write("format:\n")
                    for key, value in format_data['format'].items():
                        f.write(f"  {key}: {value}\n")
                QMessageBox.information(self, "Success", "Format exported successfully")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error exporting format: {str(e)}")
                
    def import_format(self):
        """フォーマットをYAMLファイルからインポート"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Import Format",
            "",
            "YAML Files (*.yaml);;All Files (*)"
        )
        if file_name:
            try:
                with open(file_name, 'r') as f:
                    new_format = yaml.safe_load(f)
                format_manager.set_format(new_format)
                self.show_current_format()
                QMessageBox.information(self, "Success", "Format imported successfully")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error importing format: {str(e)}")

    def on_format_changed(self, new_format):
        self.show_current_format()

class AttributeDialog(QDialog):
    def __init__(self, waypoint, format_data, parent=None):
        super().__init__(parent)
        self.waypoint = waypoint
        self.format_data = format_data
        self.setup_ui()
        self.parent_viewer = None
        # 親ウィンドウを遡って ImageViewer を探す
        current_parent = parent
        while current_parent:
            if isinstance(current_parent, ImageViewer):
                self.parent_viewer = current_parent
                break
            current_parent = current_parent.parent()
        
    def setup_ui(self):
        self.setWindowTitle("Add Actions")
        layout = QVBoxLayout(self)
        
        # 属性リスト
        self.attribute_list = QWidget()
        self.attribute_layout = QVBoxLayout(self.attribute_list)
        
        # フォーマットから利用可能な属性を取得
        available_attrs = [key for key in self.format_data['format'].keys()
                         if key not in ['number', 'x', 'y', 'angle_degrees', 'angle_radians']]
        
        # 既存の属性を表示
        for key in available_attrs:
            default_value = WAYPOINT_ATTRIBUTE_DEFAULTS.get(key, "")
            self.add_attribute_row(
                key, self.waypoint.get_attribute(key, default_value)
            )
        
        scroll = QScrollArea()
        scroll.setWidget(self.attribute_list)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        # ボタン
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
    
    def add_attribute_row(self, key, value):
        """属性入力行を追加"""
        row = QHBoxLayout()
        
        # キーのラベル
        key_label = QLabel(key)
        key_label.setMinimumWidth(100)
        
        # 値の入力フィールド
        value_edit = QLineEdit(str(value))
        value_edit.setProperty('key', key)  # キーを保存
        
        row.addWidget(key_label)
        row.addWidget(value_edit)
        self.attribute_layout.addLayout(row)
    
    def get_attributes(self):
        """ダイアログから属性を取得"""
        attributes = {}
        for i in range(self.attribute_layout.count()):
            layout_item = self.attribute_layout.itemAt(i)
            if layout_item and isinstance(layout_item, QHBoxLayout):
                value_edit = layout_item.itemAt(1).widget()
                if value_edit:
                    key = value_edit.property('key')
                    text = value_edit.text()
                    if text or key in WAYPOINT_ATTRIBUTE_DEFAULTS:
                        attributes[key] = (
                            text if text else WAYPOINT_ATTRIBUTE_DEFAULTS[key]
                        )
        return attributes

    def accept(self):
        """OKボタンが押された時の処理"""
        # 属性を更新
        self.waypoint.attributes = self.get_attributes()
        
        # ImageViewerの表示を更新
        if self.parent_viewer:
            self.parent_viewer.update_display()
        
        super().accept()

def main():
    """アプリケーションのメインエントリーポイント"""
    # HiDPI / Wayland 対応: アプリケーションの属性を設定してスケーリングを有効化
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    
    # 常にライトモード（Fusionスタイル＋ライトパレット）を強制
    app.setStyle('Fusion')
    from PySide6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(233, 233, 233))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(33, 150, 243))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
