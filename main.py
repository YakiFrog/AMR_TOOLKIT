import sys
import numpy as np
import yaml  # PyYAMLをインポート
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QMenuBar, QMenu, QLabel, QPushButton,
                              QFileDialog, QScrollArea, QSplitter, QGesture, 
                              QPinchGesture, QSlider, QCheckBox, QFrame)
from PySide6.QtCore import Qt, QPoint, Signal, QEvent, QSize, QMimeData
from PySide6.QtGui import (QPixmap, QImage, QWheelEvent, QPainter, QPen, QCursor,
                          QDrag)  # QDragをQtGuiからインポート
from enum import Enum

# 共通のスタイル定義
COMMON_STYLES = """
    QWidget {
        font-size: 11px;
    }
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

# 描画モードの定数
class DrawingMode(Enum):
    NONE = 0
    PEN = 1
    ERASER = 2
    WAYPOINT = 3  # ウェイポイントモードを追加

class Waypoint:
    """ウェイポイントを管理するクラス"""
    counter = 0
    
    def __init__(self, pixel_x, pixel_y, angle=0, name=None):
        Waypoint.counter += 1
        self.number = Waypoint.counter
        # ピクセル座標
        self.pixel_x = pixel_x
        self.pixel_y = pixel_y
        # メートル座標（初期値は0）
        self.x = 0
        self.y = 0
        self.angle = angle
        self.name = name if name else f"Waypoint {self.number}"
        self.update_display_name()

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
        # 原点からの相対位置をピクセルで計算
        rel_x = self.pixel_x - origin_x
        rel_y = origin_y - self.pixel_y  # y軸は反転

        # メートル単位に変換
        self.x = rel_x * resolution
        self.y = rel_y * resolution
        self.update_display_name()

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
                self.last_pos = event.pos()
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
                delta = event.pos() - self.last_pos
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() - delta.y())
                self.last_pos = event.pos()
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
    mouse_position_changed = Signal(QPoint)  # マウス位置シグナルを追加

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drawing_enabled = False
        self.last_pos = None
        self.parent_viewer = None
        self.cursor_pixmap = None  # カーソル用のピクスマップ
        self.current_cursor_size = 0  # 現在のカーソルサイズ
        self.setMouseTracking(True)
        self.temp_waypoint = None  # 一時的なウェイポイント保存用
        self.is_setting_angle = False  # 角度設定中フラグ
        self.click_pos = None  # クリック位置を保存

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
        
        # スケールに応じてカーソルサイズを調整（実際の描画サイズと同じになるように計算）
        pixmap_geometry = self.geometry()
        if self.parent_viewer.drawing_layer.pixmap:
            scale_x = pixmap_geometry.width() / self.parent_viewer.drawing_layer.pixmap.width()
            scaled_size = int(size * scale_x)
        else:
            scaled_size = size
            
        # サイズが変更された場合のみ新しいカーソルを作成
        if scaled_size != self.current_cursor_size:
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

    def mousePressEvent(self, event):
        if self.drawing_enabled and self.parent_viewer:
            if self.parent_viewer.drawing_mode == DrawingMode.WAYPOINT:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.click_pos = event.pos()  # クリック位置を保存
                    self.is_setting_angle = True
                    self.waypoint_clicked.emit(event.pos())
            else:
                pos = event.pos()
                self.last_pos = pos
                self.parent_viewer.draw_line(pos, pos)  # 点を描画
        # elif event.button() == Qt.MouseButton.RightButton:
        #     # 右クリックでウェイポイントを追加
        #     self.waypoint_clicked.emit(event.pos())
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # マウス位置を通知
        self.mouse_position_changed.emit(event.pos())
        # 既存の処理を継続
        if self.drawing_enabled and self.parent_viewer:
            if self.is_setting_angle and self.parent_viewer.drawing_mode == DrawingMode.WAYPOINT:
                if self.temp_waypoint and self.click_pos:
                    # プレビュー用の角度計算（Y軸を反転）
                    dx = event.pos().x() - self.click_pos.x()
                    dy = -(event.pos().y() - self.click_pos.y())  # Y軸を反転
                    angle = np.arctan2(dy, dx)
                    self.temp_waypoint.set_angle(angle)
                    self.waypoint_updated.emit(self.temp_waypoint)
            elif self.last_pos:
                pos = event.pos()
                self.parent_viewer.draw_line(self.last_pos, pos)  # 線を描画
                self.last_pos = pos
                self.updateCursor()  # マウス移動時にカーソルを更新
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_enabled:
            if self.is_setting_angle and self.click_pos:
                # 最終的な角度計算（Y軸を反転）
                dx = event.pos().x() - self.click_pos.x()
                dy = -(event.pos().y() - self.click_pos.y())  # Y軸を反転
                if self.temp_waypoint:
                    final_angle = np.arctan2(dy, dx)
                    self.temp_waypoint.set_angle(final_angle)
                    self.waypoint_updated.emit(self.temp_waypoint)
                self.is_setting_angle = False
                self.click_pos = None
                self.temp_waypoint = None
            self.last_pos = None
        else:
            super().mouseReleaseEvent(event)

class Layer(QWidget):  # QObjectを継承してシグナルを使用可能に
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
    
    def __init__(self):
        super().__init__()
        self.scale_factor = 1.0  # 画像の拡大率
        self.drawing_mode = DrawingMode.NONE
        self.last_point = None
        self.pen_color = Qt.GlobalColor.black
        self.pen_size = 2       # デフォルトのペンサイズ
        self.eraser_size = 10   # デフォルトの消しゴムサイズ
        
        # 座標表示用ラベルを最初に初期化（この1箇所だけにする）
        self.coord_label = QLabel()
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
        
        # レイヤー管理
        self.layers = []
        self.active_layer = None
        
        # 基本レイヤーの作成とシグナル接続
        self.pgm_layer = Layer("PGM Layer")
        self.drawing_layer = Layer("Drawing Layer")
        self.waypoint_layer = Layer("Waypoint Layer")  # ウェイポイントレイヤーを追加
        self.origin_layer = Layer("Origin Layer")  # originレイヤーを追加
        self.layers = [self.pgm_layer, self.waypoint_layer, self.drawing_layer, self.origin_layer]  # 順序を変更
        self.active_layer = self.drawing_layer
        
        # レイヤーの変更通知を接続
        for layer in self.layers:
            layer.changed.connect(self.on_layer_changed)
        
        self.waypoints = []  # ウェイポイントのリスト
        self.waypoint_size = 15  # ウェイポイントのサイズを大きく

        self.show_grid = False  # グリッド表示フラグを追加
        self.grid_size = 50     # グリッドサイズ（ピクセル単位）

        self.origin_point = None  # origin点の座標を保存
        self.resolution = 0.05  # デフォルトの解像度（m/pixel）

        self.setup_display()
        self.setup_scroll_area()
        self.setup_drawing_tools()

    def setup_display(self):
        """画像表示用ラベルの設定を集約"""
        self.pgm_display = DrawableLabel()
        self.pgm_display.parent_viewer = self  # 親ビューアへの参照を設定
        self.pgm_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pgm_display.setStyleSheet("background-color: white;")
        self.pgm_display.waypoint_clicked.connect(self.add_waypoint)
        self.pgm_display.waypoint_updated.connect(self.update_waypoint)
        self.pgm_display.mouse_position_changed.connect(self.update_mouse_position)

    def setup_scroll_area(self):
        """スクロールエリアの設定を集約"""
        self.scroll_area = CustomScrollArea()
        self.scroll_area.setWidget(self.pgm_display)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(600, 400)
        self.scroll_area.setStyleSheet("QScrollArea { border: 2px solid #ccc; background-color: white; }")
        self.scroll_area.scale_changed.connect(self.handle_scale_change)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.scroll_area)

        # 座標表示用ラベルをスクロールエリアのビューポートの子として設定
        self.coord_label.setParent(self.scroll_area.viewport())
        self.coord_label.hide()  # 初期状態では非表示

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
            self.coord_label.raise_()  # ラベルを最前面に表示
        self.scroll_area.resizeEvent = new_resize_event

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
        
        buttons_layout.addWidget(self.pen_button)
        buttons_layout.addWidget(self.eraser_button)
        buttons_layout.addWidget(self.waypoint_button)
        
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
            self.pgm_display.set_drawing_mode(False)
            self.scroll_area.set_drawing_mode(False)
            return

        # 異なるモードを選択した場合は描画モードを変更
        self.drawing_mode = mode
        self.pen_button.setChecked(mode == DrawingMode.PEN)
        self.eraser_button.setChecked(mode == DrawingMode.ERASER)
        self.waypoint_button.setChecked(mode == DrawingMode.WAYPOINT)
        
        # ラベルの描画モードを設定
        self.pgm_display.set_drawing_mode(mode != DrawingMode.NONE)
        # スクロールエリアの描画モードを設定
        self.scroll_area.set_drawing_mode(mode != DrawingMode.NONE)
        # カーソルを更新
        if mode != DrawingMode.NONE:
            if mode == DrawingMode.WAYPOINT:
                self.pgm_display.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.pgm_display.updateCursor()

    def draw_line(self, start_pos, end_pos):
        """2点間に線を描画"""
        if not self.drawing_layer.pixmap or self.drawing_mode == DrawingMode.NONE:
            return

        pixmap_geometry = self.pgm_display.geometry()
        scale_x = self.drawing_layer.pixmap.width() / pixmap_geometry.width()
        scale_y = self.drawing_layer.pixmap.height() / pixmap_geometry.height()
        
        scaled_start = QPoint(int(start_pos.x() * scale_x), int(start_pos.y() * scale_y))
        scaled_end = QPoint(int(end_pos.x() * scale_x), int(end_pos.y() * scale_y))

        # スケールに応じて描画サイズを調整
        scaled_pen_size = int(self.pen_size * scale_x)
        scaled_eraser_size = int(self.eraser_size * scale_x)

        painter = QPainter(self.drawing_layer.pixmap)
        if self.drawing_mode == DrawingMode.PEN:
            painter.setPen(QPen(self.pen_color, scaled_pen_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        else:  # ERASER
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.setPen(QPen(Qt.GlobalColor.transparent, scaled_eraser_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        painter.drawLine(scaled_start, scaled_end)
        painter.end()

        self.update_display()

    def mousePressEvent(self, event):
        if self.drawing_mode != DrawingMode.NONE:
            self.last_point = event.pos()
            self.draw_line(event.pos(), event.pos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_mode != DrawingMode.NONE and self.last_point:
            self.draw_line(self.last_point, event.pos())
            self.last_point = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_mode != DrawingMode.NONE:
            self.last_point = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def load_image(self, img_array, width, height):
        """PGM画像データを読み込んでPGMレイヤーに設定"""
        bytes_per_line = width
        q_img = QImage(img_array.data, width, height, bytes_per_line,
                    QImage.Format.Format_Grayscale8)
        self.pgm_layer.pixmap = QPixmap.fromImage(q_img)
        self.drawing_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
        self.drawing_layer.pixmap.fill(Qt.GlobalColor.transparent)
        self.update_display()
        self.coord_label.show()  # 画像読み込み時に座標表示を有効化

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

        # 表示サイズからピクセル座標に変換
        pixmap_geometry = self.pgm_display.geometry()
        if self.pgm_layer.pixmap:
            scale_x = self.pgm_layer.pixmap.width() / pixmap_geometry.width()
            scale_y = self.pgm_layer.pixmap.height() / pixmap_geometry.height()
            x = int(pos.x() * scale_x)
            y = int(pos.y() * scale_y)
        else:
            x = pos.x()
            y = pos.y()
        
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

    def update_waypoint(self, waypoint):
        """ウェイポイントの更新（角度変更時）"""
        self.update_display()
        # 対応するラベルを更新するためにシグナルを再発行
        self.waypoint_added.emit(waypoint)

    def update_display(self):
        """複数レイヤーを合成して表示"""
        if not self.pgm_layer.pixmap:
            return

        # 合成用の新しいピクスマップを作成
        result = QPixmap(self.pgm_layer.pixmap.size())
        result.fill(Qt.GlobalColor.white)
        
        painter = QPainter(result)
        
        # PGMレイヤーを描画
        if self.pgm_layer.visible and self.pgm_layer.pixmap:
            painter.setOpacity(self.pgm_layer.opacity)
            painter.drawPixmap(0, 0, self.pgm_layer.pixmap)

        # グリッドの描画
        if self.show_grid:
            painter.setOpacity(0.3)  # グリッドの透明度
            pen = QPen(Qt.GlobalColor.gray)
            pen.setStyle(Qt.PenStyle.DashLine)  # 破線スタイル
            painter.setPen(pen)

            # 縦線を描画
            for x in range(0, result.width(), self.grid_size):
                painter.drawLine(x, 0, x, result.height())

            # 横線を描画
            for y in range(0, result.height(), self.grid_size):
                painter.drawLine(0, y, result.width(), y)

        # ウェイポイントの描画（Waypointレイヤーの表示状態とopacityを考慮）
        if (self.waypoints and self.waypoint_layer.visible):
            painter.setOpacity(self.waypoint_layer.opacity)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            for waypoint in self.waypoints:
                x, y = waypoint.pixel_x, waypoint.pixel_y
                size = self.waypoint_size
                
                # 矢印の描画
                pen = QPen(Qt.GlobalColor.red)
                pen.setWidth(3)
                painter.setPen(pen)
                
                angle_line_length = size * 3
                # 矢印の方向を修正（Y軸を反転）
                end_x = x + int(angle_line_length * np.cos(waypoint.angle))
                end_y = y - int(angle_line_length * np.sin(waypoint.angle))  # マイナスに変更
                painter.drawLine(x, y, end_x, end_y)
                
                # 矢印の先端の角度を修正
                arrow_size = size // 2
                arrow_angle1 = waypoint.angle + np.pi * 3/4
                arrow_angle2 = waypoint.angle - np.pi * 3/4
                
                # 矢印の先端の座標計算も修正（Y軸を反転）
                arrow_x1 = end_x + int(arrow_size * np.cos(arrow_angle1))
                arrow_y1 = end_y - int(arrow_size * np.sin(arrow_angle1))  # マイナスに変更
                arrow_x2 = end_x + int(arrow_size * np.cos(arrow_angle2))
                arrow_y2 = end_y - int(arrow_size * np.sin(arrow_angle2))  # マイナスに変更
                
                painter.drawLine(end_x, end_y, arrow_x1, arrow_y1)
                painter.drawLine(end_x, end_y, arrow_x2, arrow_y2)
                
                # 番号を表示する円を描画
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(Qt.GlobalColor.red)
                painter.drawEllipse(x - size, y - size, size * 2, size * 2)
                
                # 番号を描画
                painter.setPen(Qt.GlobalColor.white)
                font = self.font()
                font.setPointSize(19)
                font.setBold(True)
                painter.setFont(font)
                number_text = str(waypoint.number)
                font_metrics = painter.fontMetrics()
                text_width = font_metrics.horizontalAdvance(number_text)
                text_height = font_metrics.height()
                text_x = x - text_width // 2
                text_y = y + text_height // 3
                painter.drawText(text_x, text_y, number_text)

        # 残りのレイヤーを描画
        painter.setOpacity(1.0)  # 不透明度をリセット
        for layer in self.layers[1:]:  # PGMレイヤー以外を描画
            if layer.visible and layer.pixmap:
                painter.setOpacity(layer.opacity)
                painter.drawPixmap(0, 0, layer.pixmap)
        
        painter.end()

        # スケーリングして表示
        new_size = QSize(
            int(result.width() * self.scale_factor),
            int(result.height() * self.scale_factor)
        )
        
        scaled_pixmap = result.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation  # スムージングを有効化
        )
        
        self.pgm_display.setPixmap(scaled_pixmap)
        self.pgm_display.adjustSize()

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
        pixmap_geometry = self.pgm_display.geometry()
        scale_x = self.pgm_layer.pixmap.width() / pixmap_geometry.width()
        scale_y = self.pgm_layer.pixmap.height() / pixmap_geometry.height()
        
        pixel_x = int(pos.x() * scale_x)
        pixel_y = int(pos.y() * scale_y)

        # 原点からの相対位置を計算
        origin_x, origin_y = self.origin_point
        rel_x = (pixel_x - origin_x) * self.resolution
        rel_y = (origin_y - pixel_y) * self.resolution  # y軸は反転
        
        # 座標を表示（ピクセル座標と相対座標）
        self.coord_label.setText(f"Pixel: ({pixel_x}, {pixel_y})\nMetric: ({rel_x:.2f}, {rel_y:.2f})")
        self.coord_label.show()

    def load_yaml_file(self, file_path):
        """YAMLファイルを読み込みorigin点を設定"""
        try:
            with open(file_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
                
            # YAMLファイルから直接originとresolutionを読み取る
            if 'origin' in yaml_data:
                origin = yaml_data['origin']
                if len(origin) >= 2:
                    # 解像度を保存
                    self.resolution = float(yaml_data.get('resolution', 0.05))
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

    def draw_origin_point(self):
        """origin点を描画"""
        if not self.origin_point or not self.pgm_layer.pixmap:
            return

        # originレイヤーのピクスマップを初期化
        self.origin_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
        self.origin_layer.pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(self.origin_layer.pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 十字マークを描画
        x, y = self.origin_point
        size = 20  # マーカーのサイズ
        
        # 赤い十字を描画
        pen = QPen(Qt.GlobalColor.red, 3)
        painter.setPen(pen)
        painter.drawLine(x - size, y, x + size, y)  # 水平線
        painter.drawLine(x, y - size, x, y + size)  # 垂直線
        
        # 円を描画
        painter.drawEllipse(x - size/2, y - size/2, size, size)
        
        painter.end()
        self.update_display()

class MenuPanel(QWidget):
    """メニューパネル
    ファイル操作とズーム制御のUIを提供"""
    
    # シグナルの定義
    file_selected = Signal(str)  # ファイル選択時のシグナル
    zoom_value_changed = Signal(int)  # ズーム値変更時のシグナル
    yaml_selected = Signal(str)  # YAMLファイル選択用のシグナルを追加
    
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
        
        # ファイルメニューのアクションを作成
        open_action = file_menu.addAction("Open PGM")
        save_action = file_menu.addAction("Save PGM")
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        
        menu_bar.addMenu(file_menu)
        menu_bar.addMenu(edit_menu)

        # ファイル選択部分のレイアウト
        file_layout = QHBoxLayout()
        self.select_button = QPushButton("Select PGM File")
        self.select_button.clicked.connect(self.open_file_dialog)
        
        # YAMLファイル選択ボタンを追加
        self.yaml_button = QPushButton("Select YAML File")
        self.yaml_button.clicked.connect(self.open_yaml_dialog)
        
        self.file_name_label = QLabel("No file selected")  # ファイル名表示用ラベル
        self.file_name_label.setStyleSheet("color: #666; padding: 0 10px;")
        
        file_layout.addWidget(self.select_button)
        file_layout.addWidget(self.yaml_button)  # YAMLボタンを追加
        file_layout.addWidget(self.file_name_label, stretch=1)  # stretchを1に設定して余白を埋める
        
        # ズームコントロールをメソッドに分離
        zoom_widget = self.create_zoom_controls()
        
        layout.addWidget(menu_bar)
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

# LayerControlウィジェットを追加
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

class RightPanel(QWidget):
    """右側のパネル"""
    waypoint_delete_requested = Signal(int)  # 新しいシグナルを追加
    all_waypoints_delete_requested = Signal()  # 新しいシグナル
    waypoint_reorder_requested = Signal(int, int)  # 順序変更シグナルを追加
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.waypoint_widgets = {}  # ウェイポイントウィジェットを保持する辞書を追加

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setStyleSheet("QWidget { background-color: #f5f5f5; border-radius: 5px; }")

        # レイヤーパネルを追加
        self.layer_widget = self.create_layer_panel()
        layout.addWidget(self.layer_widget)
        
        # ウェイポイントリストパネルを追加
        self.waypoint_widget = self.create_waypoint_panel()
        layout.addWidget(self.waypoint_widget)
        
        # Panel 2, 3を追加
        titles = ["Panel 2", "Panel 3"]
        for title in titles:
            widget = QWidget()
            widget_layout = QVBoxLayout(widget)
            
            title_label = QLabel(title)
            title_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    padding: 5px;
                    background-color: #e0e0e0;
                    border-radius: 3px;
                }
            """)
            
            content = QWidget()
            content.setStyleSheet("""
                QWidget {
                    background-color: white;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                }
            """)
            content.setMinimumHeight(150)
            
            widget_layout.addWidget(title_label)
            widget_layout.addWidget(content)
            layout.addWidget(widget)

        self.setLayout(layout)

    def create_layer_panel(self):
        """レイヤーパネルを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title_label = QLabel("Layers")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
                background-color: #e0e0e0;
                border-radius: 3px;
            }
        """)
        
        self.layer_list = QWidget()
        self.layer_list.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)
        self.layer_list_layout = QVBoxLayout(self.layer_list)
        self.layer_list_layout.setSpacing(5)  # ウィジェット間のスペースを設定
        self.layer_list.setMinimumHeight(100)
        
        layout.addWidget(title_label)
        layout.addWidget(self.layer_list)
        layout.setSpacing(5)  # タイトルとリスト間のスペースを設定
        
        return widget

    def create_waypoint_panel(self):
        """ウェイポイントリストパネルを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)
        
        # ヘッダー部分のレイアウト
        header_layout = QHBoxLayout()
        
        # タイトル
        title_label = QLabel("Waypoints")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
                background-color: #e0e0e0;
                border-radius: 3px;
            }
        """)
        
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
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()  # タイトルとボタンの間にスペースを追加
        header_layout.addWidget(clear_button)
        
        # スクロールエリアの作成
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
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
        scroll_area.setWidget(self.waypoint_list)
        
        # 固定の高さを設定（必要に応じて調整）
        scroll_area.setMinimumHeight(150)
        scroll_area.setMaximumHeight(300)
        
        layout.addLayout(header_layout)  # ヘッダーレイアウトを先頭に追加
        layout.addWidget(scroll_area)
        
        return widget

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
        
        # ドラッグ&ドロップを有効化
        self.setAcceptDrops(True)
        
        # レイアウト設定
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # ドラッグハンドル（三本線）を追加
        drag_handle = QLabel("⋮")  # 縦三点リーダー
        drag_handle.setStyleSheet("""
            QLabel {
                font-size: 20px;
                color: #666;
                padding: 0 5px;
                margin-right: 5px;
            }
        """)
        
        # フレームを作成（ドラッグ時のハイライト用）
        self.frame = QFrame()
        self.frame.setFrameStyle(QFrame.Shape.NoFrame)
        frame_layout = QHBoxLayout(self.frame) 
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(5)
        
        # ラベル
        self.label = QLabel(waypoint.display_name)
        self.label.setFocusPolicy(Qt.FocusPolicy.NoFocus) # フォーカスを無効化
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 500;
            }
        """)
        
        # 削除ボタン
        delete_button = QPushButton("×")
        delete_button.setFixedSize(20, 20)
        delete_button.setStyleSheet("""
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
        delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.waypoint_number))
        
        # フレームにウィジェットを追加
        frame_layout.addWidget(self.label, stretch=1)
        frame_layout.addWidget(delete_button)
        
        # メインレイアウトにウィジェットを追加
        layout.addWidget(drag_handle) # ドラッグハンドルを先頭に追加
        layout.addWidget(self.frame, stretch=1)
        
        # スタイル設定
        self.setStyleSheet("""
            WaypointListItem {
                border-bottom: 1px solid #eee;
                background-color: white;
            }
            WaypointListItem:hover {
                background-color: #f5f5f5;
            }
        """)

    def update_label(self, text):
        """ラベルテキストを更新"""
        self.label.setText(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(str(self.waypoint_number))
            drag.setMimeData(mime_data)
            drag.exec()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        # ドラッグされたデータがテキストなら受け入れる
        if event.mimeData().hasText() and event.source() != self:
            event.accept()
            self.label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: 500;
                    color: #2196F3;
                }
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        # ドラッグが離れたら下線を消す
        # self.frame.setFrameStyle(QFrame.Shape.NoFrame)
        # self.frame.setStyleSheet("")
        self.label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 500;
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
        
        # スタイルを元に戻す
        self.label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 500;
            }
        """)
        event.accept()

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

        # 左側レイアウトの構成
        left_layout.addWidget(self.menu_panel)
        left_layout.addWidget(self.image_viewer)
        left_widget.setLayout(left_layout)
        
        # 右側パネル
        self.analysis_panel = RightPanel()
        
        # スプリッタの設定
        splitter.addWidget(left_widget)
        splitter.addWidget(self.analysis_panel)
        splitter.setSizes([600, 400])
        
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # レイヤー状態変更時の更新処理を接続
        self.image_viewer.layer_changed.connect(self.update_layer_panel)
        
        # 初期レイヤーパネルの更新を追加
        self.update_layer_panel()  # この行を追加

        # ウェイポイント追加時の処理を接続
        self.image_viewer.waypoint_added.connect(self.analysis_panel.add_waypoint_to_list)

        # ウェイポイント削除時の処理を接続
        self.image_viewer.waypoint_removed.connect(self.analysis_panel.remove_waypoint_from_list)
        
        # 削除ボタンクリック時の処理を接続（修正版）
        self.analysis_panel.waypoint_delete_requested.connect(self.image_viewer.remove_waypoint)

        # 全ウェイポイント削除時の処理を接続
        self.analysis_panel.all_waypoints_delete_requested.connect(self.image_viewer.remove_all_waypoints)

        # ウェイポイントの順序変更時の処理を接続
        self.analysis_panel.waypoint_reorder_requested.connect(
            self.image_viewer.reorder_waypoints)

    def update_layer_panel(self):
        """レイヤーパネルの表示を更新"""
        if hasattr(self, 'analysis_panel') and hasattr(self, 'image_viewer'):
            self.analysis_panel.update_layer_list(self.image_viewer.layers)

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
                print(f"Successfully loaded image: {width}x{height}, max value: {max_val}")

        except Exception as e:
            print(f"Error loading PGM file: {str(e)}")
            import traceback
            traceback.print_exc()

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
        """YAMLファイルの読み込みをImageViewerに委譲"""
        self.image_viewer.load_yaml_file(file_path)

def main():
    """アプリケーションのメインエントリーポイント"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
