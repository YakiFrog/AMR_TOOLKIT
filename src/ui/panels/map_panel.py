from PySide6.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QLabel)
from PySide6.QtCore import Qt, Signal, QPoint, QSize, QObject
from PySide6.QtGui import (QPixmap, QImage, QPainter, QPen, QColor)
import numpy as np
import yaml

class Waypoint:
    """ウェイポイントを管理するクラス"""
    counter = 0
    
    def __init__(self, pixel_x, pixel_y, angle=0, name=None):
        Waypoint.counter += 1
        self.number = Waypoint.counter
        self.pixel_x = pixel_x
        self.pixel_y = pixel_y
        self.x = 0
        self.y = 0
        self.angle = angle
        self.name = name if name else f"Waypoint {self.number}"
        self.resolution = 0.05
        self.update_display_name()

    def update_display_name(self):
        """表示名を更新"""
        degrees = int(self.angle * 180 / np.pi)
        self.display_name = f"#{self.number:02d} ({self.x:.2f}, {self.y:.2f}) {degrees}°"

    def update_metric_coordinates(self, origin_x, origin_y, resolution):
        """ピクセル座標からメートル座標を計算"""
        self._origin_x = origin_x
        self._origin_y = origin_y
        self.resolution = resolution
        
        rel_x = self.pixel_x - origin_x
        rel_y = origin_y - self.pixel_y
        
        self.x = rel_x * resolution
        self.y = rel_y * resolution
        self.update_display_name()

class CustomScrollArea(QScrollArea):
    """カスタムスクロールエリアクラス"""
    scale_changed = Signal(float)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.last_pos = None
        self.mouse_pressed = False
        self.drawing_mode_enabled = False
        
        for attr in [self, self.viewport()]:
            attr.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)

class DrawableLabel(QLabel):
    """描画可能なラベルクラス"""
    waypoint_clicked = Signal(QPoint)
    waypoint_updated = Signal(object) # Waypointオブジェクト
    waypoint_completed = Signal(QPoint)
    mouse_position_changed = Signal(QPoint)
    waypoint_edited = Signal(object) # Waypointオブジェクト

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        # ...existing DrawableLabel initialization...

    # ...existing DrawableLabel methods...

class ImageViewer(QWidget):
    """画像表示用ウィジェット"""
    scale_changed = Signal(float)
    layer_changed = Signal()
    waypoint_added = Signal(object) # Waypointオブジェクト
    waypoint_removed = Signal(int)
    waypoint_edited = Signal(object) # Waypointオブジェクト

    def __init__(self):
        super().__init__()
        self.setup_basic_attributes()
        self.setup_ui()

    def setup_basic_attributes(self):
        """基本的な属性の初期化"""
        self.scale_factor = 1.0
        self.show_grid = False
        self.grid_size = 50
        self.waypoint_size = 15
        self.waypoints = []
        self.origin_point = None
        self.resolution = 0.05
        
        # レイヤーの初期化
        self.pgm_layer = Layer("PGM Layer")
        self.drawing_layer = Layer("Drawing Layer")
        self.waypoint_layer = Layer("Waypoint Layer")
        self.origin_layer = Layer("Origin Layer")
        self.path_layer = Layer("Path Layer")
        
        self.layers = [
            self.pgm_layer,
            self.drawing_layer,
            self.path_layer,
            self.waypoint_layer,
            self.origin_layer
        ]
        
        for layer in self.layers:
            layer.changed.connect(self.on_layer_changed)

    def setup_ui(self):
        """UIコンポーネントの初期化"""
        layout = QVBoxLayout(self)
        
        # スクロールエリアの設定
        self.scroll_area = CustomScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.scale_changed.connect(self.handle_scale_change)
        
        # 描画可能なラベルの設定
        self.pgm_display = DrawableLabel()
        self.pgm_display.parent_viewer = self
        self.pgm_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pgm_display.waypoint_clicked.connect(self.add_waypoint)
        self.pgm_display.waypoint_updated.connect(self.update_waypoint)
        self.pgm_display.waypoint_edited.connect(self.handle_waypoint_edited)
        
        self.scroll_area.setWidget(self.pgm_display)
        layout.addWidget(self.scroll_area)

    def handle_scale_change(self, factor):
        """スケール変更時の処理"""
        self.scale_factor *= factor
        self.update_display()
        self.scale_changed.emit(self.scale_factor)

    def on_layer_changed(self):
        """レイヤーの状態が変更された時の処理"""
        self.update_display()
        self.layer_changed.emit()

    # ...existing methods...

    def toggle_grid(self):
        """グリッド表示の切り替え"""
        self.show_grid = not self.show_grid
        self.update_display()

    def update_display(self):
        """画像の表示を更新"""
        if not self.pgm_layer.pixmap:
            return

        # 合成用の新しいピクスマップを作成
        result = QPixmap(self.pgm_layer.pixmap.size())
        result.fill(Qt.GlobalColor.white)
        
        painter = QPainter(result)
        
        # レイヤーの描画
        for layer in self.layers:
            if layer.visible and layer.pixmap:
                painter.setOpacity(layer.opacity)
                painter.drawPixmap(0, 0, layer.pixmap)

        # グリッドの描画
        if self.show_grid:
            self.draw_grid(painter)

        # ウェイポイントの描画
        if self.waypoint_layer.visible and self.waypoints:
            self.draw_waypoints(painter)

        painter.end()
        self.update_scaled_display(result)

    def draw_grid(self, painter):
        """グリッドの描画"""
        painter.setOpacity(0.3)
        pen = QPen(Qt.GlobalColor.gray)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        for x in range(0, self.pgm_layer.pixmap.width(), self.grid_size):
            painter.drawLine(x, 0, x, self.pgm_layer.pixmap.height())

        for y in range(0, self.pgm_layer.pixmap.height(), self.grid_size):
            painter.drawLine(0, y, self.pgm_layer.pixmap.width(), y)

    def draw_waypoints(self, painter):
        """ウェイポイントの描画"""
        painter.setOpacity(self.waypoint_layer.opacity)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        for waypoint in self.waypoints:
            is_editing = (self.pgm_display.edit_mode and 
                         self.pgm_display.editing_waypoint and 
                         self.pgm_display.editing_waypoint.number == waypoint.number)
            
            color = QColor(0, 120, 255) if is_editing else QColor(255, 0, 0)
            pen = QPen(color, 3)
            painter.setPen(pen)
            
            # 矢印の描画
            self.draw_waypoint_arrow(painter, waypoint, is_editing)
            
            # 番号の描画
            self.draw_waypoint_number(painter, waypoint)

    def draw_waypoint_arrow(self, painter, waypoint, is_editing):
        """ウェイポイントの矢印を描画"""
        size = self.waypoint_size
        size_multiplier = 1.2 if is_editing else 1.0
        adjusted_size = size * size_multiplier
        
        # 矢印の線を描画
        angle_line_length = adjusted_size * 3
        end_x = waypoint.pixel_x + int(angle_line_length * np.cos(waypoint.angle))
        end_y = waypoint.pixel_y - int(angle_line_length * np.sin(waypoint.angle))
        painter.drawLine(waypoint.pixel_x, waypoint.pixel_y, end_x, end_y)

        # 矢印の先端を描画
        arrow_size = adjusted_size // 2
        arrow_angle1 = waypoint.angle + np.pi * 3/4
        arrow_angle2 = waypoint.angle - np.pi * 3/4
        
        arrow_x1 = end_x + int(arrow_size * np.cos(arrow_angle1))
        arrow_y1 = end_y - int(arrow_size * np.sin(arrow_angle1))
        arrow_x2 = end_x + int(arrow_size * np.cos(arrow_angle2))
        arrow_y2 = end_y - int(arrow_size * np.sin(arrow_angle2))
        
        painter.drawLine(end_x, end_y, arrow_x1, arrow_y1)
        painter.drawLine(end_x, end_y, arrow_x2, arrow_y2)

    def draw_waypoint_number(self, painter, waypoint):
        """ウェイポイントの番号を描画"""
        painter.setPen(QColor(255, 255, 255, 230))
        font = painter.font()
        font.setPointSize(19)
        font.setBold(True)
        painter.setFont(font)
        
        number_text = str(waypoint.number)
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.horizontalAdvance(number_text)
        text_height = font_metrics.height()
        
        text_x = waypoint.pixel_x - text_width // 2
        text_y = waypoint.pixel_y + text_height // 3
        painter.drawText(text_x, text_y, number_text)

    def remove_waypoint(self, number):
        """ウェイポイントを削除"""
        # 削除対象のウェイポイントを除外
        self.waypoints = [wp for wp in self.waypoints if wp.number != number]
        
        # ナンバリングを振り直し
        Waypoint.counter = 0
        
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
        Waypoint.counter = 0
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
        self.waypoints.insert(target_index, source_wp)
        
        # 番号を振り直し
        Waypoint.counter = 0
        
        # UIを更新するために一旦全てのウェイポイントを削除
        self.waypoint_removed.emit(-1)
        
        # ウェイポイントを順番に振り直してUIを更新
        for wp in self.waypoints:
            Waypoint.counter += 1
            wp.renumber(Waypoint.counter)
            self.waypoint_added.emit(wp)
            
        self.update_display()

    def generate_path(self):
        """ウェイポイント間のパスを生成または非表示"""
        if not self.waypoints or len(self.waypoints) < 2:
            return

        # パスレイヤーの初期化
        if not self.path_layer.pixmap or self.path_layer.pixmap.size() != self.pgm_layer.pixmap.size():
            self.path_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())

        # パスレイヤーをクリア
        self.path_layer.pixmap.fill(Qt.GlobalColor.transparent)

        # パス生成ボタンがチェックされている場合のみパスを描画
        parent = self.parent()
        while parent:
            if hasattr(parent, 'analysis_panel'):
                if parent.analysis_panel.generate_path_button.isChecked():
                    painter = QPainter(self.path_layer.pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    
                    # パスのスタイル設定
                    pen = QPen(QColor(76, 175, 80), 3)  # 緑色、太さ3
                    pen.setStyle(Qt.PenStyle.SolidLine)
                    painter.setPen(pen)
                    
                    # ウェイポイントを順番に接続
                    for i in range(len(self.waypoints) - 1):
                        start = self.waypoints[i]
                        end = self.waypoints[i + 1]
                        painter.drawLine(start.pixel_x, start.pixel_y, 
                                      end.pixel_x, end.pixel_y)
                    
                    painter.end()
                break
            parent = parent.parent()

        self.update_display()

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
        
        # 新しいウェイポイントを作成
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

    def handle_waypoint_edited(self, waypoint):
        """ウェイポイント編集時の処理"""
        if self.origin_point:  # 原点が設定されている場合
            origin_x, origin_y = self.origin_point
            waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
        self.waypoint_edited.emit(waypoint)
        self.update_display()

    def update_scaled_display(self, pixmap):
        """スケーリングされた画像を表示"""
        new_size = QSize(
            int(pixmap.width() * self.scale_factor),
            int(pixmap.height() * self.scale_factor)
        )
        
        scaled_pixmap = pixmap.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.pgm_display.setPixmap(scaled_pixmap)
        self.pgm_display.adjustSize()

    # ...remaining ImageViewer methods...

class Layer(QObject):
    """レイヤークラス"""
    changed = Signal()  # レイヤーの状態変更通知用シグナル
    
    def __init__(self, name, visible=True):
        super().__init__()
        self.name = name
        self.visible = visible
        self.pixmap = None
        self.opacity = 1.0

    def set_visible(self, visible):
        """表示/非表示を設定"""
        if self.visible != visible:
            self.visible = visible
            self.changed.emit()

    def set_opacity(self, opacity):
        """不透明度を設定"""
        new_opacity = max(0.0, min(1.0, opacity))
        if self.opacity != new_opacity:
            self.opacity = new_opacity
            self.changed.emit()
