import numpy as np
import yaml
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
                               QLabel, QPushButton, QSlider, QToolTip)
from PySide6.QtCore import Qt, QPoint, Signal, QEvent, QSize, QTimer, QRect
from PySide6.QtGui import (QPixmap, QImage, QWheelEvent, QPainter, QPen, QCursor,
                           QColor)

from ...core.models import DrawingMode, Waypoint
from ...core.constants import (WAYPOINT_SETTINGS, MIN_SCALE, MAX_SCALE, 
                               DEFAULT_SCALE, SCALE_SENSITIVITY)
from ...utils.format_manager import format_manager
from ..widgets.layer_widget import Layer
from ..dialogs.attribute_dialog import AttributeDialog

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
                self.last_pos = event.position().toPoint()
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
                delta = event.position().toPoint() - self.last_pos
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() - delta.y())
                self.last_pos = event.position().toPoint()
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
    waypoint_clicked = Signal(QPoint)
    waypoint_updated = Signal(Waypoint)
    waypoint_completed = Signal(QPoint)
    mouse_position_changed = Signal(QPoint)
    waypoint_edited = Signal(Waypoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drawing_enabled = False
        self.parent_viewer = None
        self.cursor_pixmap = None
        self.current_cursor_size = 0
        self.setMouseTracking(True)
        self.temp_waypoint = None
        self.is_setting_angle = False
        self.click_pos = None
        self.edit_mode = False
        self.editing_waypoint = None
        self.is_dragging = False
        self.drag_start = None
        self.last_pos = None
        self.is_editing_angle = False

    def set_drawing_mode(self, enabled):
        self.drawing_enabled = enabled
        if enabled:
            self.updateCursor()
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def updateCursor(self):
        """カーソルを更新"""
        if not self.parent_viewer:
            return

        size = self.parent_viewer.pen_size if self.parent_viewer.drawing_mode == DrawingMode.PEN else self.parent_viewer.eraser_size
        scaled_size = int(size)
            
        if (scaled_size != self.current_cursor_size):
            self.current_cursor_size = scaled_size
            cursor_size = max(scaled_size, 8)
            
            self.cursor_pixmap = QPixmap(cursor_size, cursor_size)
            self.cursor_pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(self.cursor_pixmap)
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(0, 0, cursor_size-1, cursor_size-1)
            painter.end()
            
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

        if self.edit_mode and self.editing_waypoint:
            # 編集モードを終了
            self.edit_mode = False
            self.editing_waypoint = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if self.parent_viewer:
                self.parent_viewer.update_display()
        else:
            # クリックされた位置にあるウェイポイントを探す
            for waypoint in self.parent_viewer.waypoints:
                hover_range = max(6, int(WAYPOINT_SETTINGS['BASE_SIZE'] * 1.6))
                if abs(waypoint.pixel_x - x) < hover_range and abs(waypoint.pixel_y - y) < hover_range:
                    self.edit_mode = True
                    self.editing_waypoint = waypoint
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    if self.parent_viewer:
                        self.parent_viewer.show_edit_message("ドラッグで移動、Shift+ドラッグで角度を変更")
                        self.parent_viewer.update_display()
                    break

    def mousePressEvent(self, event):
        if self.drawing_enabled and self.parent_viewer:
            if self.parent_viewer.drawing_mode == DrawingMode.WAYPOINT:
                if event.button() == Qt.MouseButton.LeftButton:
                    pos = event.position().toPoint()
                    self.click_pos = pos
                    self.is_setting_angle = True
                    self.waypoint_clicked.emit(pos)
            else:
                pos = event.position().toPoint()
                self.last_pos = pos
                self.parent_viewer.draw_line(pos, pos)
        elif self.edit_mode and self.editing_waypoint:
            pos = event.position().toPoint()
            im_pos = self.parent_viewer.display_to_image_coords(pos)
            if im_pos is None:
                return
            x = im_pos.x()
            y = im_pos.y()

            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shiftキーが押されている場合は角度編集モード
                self.is_editing_angle = True
                self.editing_start_pos = pos
            else:
                # 通常クリックは位置の移動
                self.editing_waypoint.set_position(x, y)
                if self.parent_viewer:
                    self.parent_viewer.update_display()
                    self.parent_viewer.waypoint_edited.emit(self.editing_waypoint)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """マウス移動時のイベント処理"""
        pos = event.position().toPoint()
        self.mouse_position_changed.emit(pos)

        if self.parent_viewer and self.parent_viewer.waypoints:
            im_pos = self.parent_viewer.display_to_image_coords(pos)
            if im_pos is None:
                QToolTip.hideText()
                return
            x = im_pos.x()
            y = im_pos.y()

            hover_range = max(6, int(WAYPOINT_SETTINGS['BASE_SIZE'] * 1.6))

            for waypoint in self.parent_viewer.waypoints:
                if abs(waypoint.pixel_x - x) < hover_range and abs(waypoint.pixel_y - y) < hover_range:
                        if waypoint.attributes:
                            tooltip = "<b>Actions:</b><br>"
                            for key, value in waypoint.attributes.items():
                                tooltip += f"{key}: {value}"
                                if key != list(waypoint.attributes.keys())[-1]:
                                    tooltip += "<br>"
                            global_pos = QPoint(
                                int(event.globalPosition().x()),
                                int(event.globalPosition().y())
                            )
                            QToolTip.showText(global_pos, tooltip.strip())
                            return
                
                QToolTip.hideText()

        if self.drawing_enabled and self.parent_viewer:
            if self.is_setting_angle and self.parent_viewer.drawing_mode == DrawingMode.WAYPOINT:
                if self.temp_waypoint and self.click_pos:
                    dx = pos.x() - self.click_pos.x()
                    dy = -(pos.y() - self.click_pos.y())
                    angle = np.arctan2(dy, dx)
                    self.temp_waypoint.set_angle(angle)
                    self.waypoint_updated.emit(self.temp_waypoint)
            elif self.last_pos:
                self.parent_viewer.draw_line(self.last_pos, pos)
                self.last_pos = pos
                self.updateCursor()
        elif self.edit_mode and self.editing_waypoint:
            pos = event.position().toPoint()
            im_pos = self.parent_viewer.display_to_image_coords(pos)
            if im_pos is None:
                return
            x = im_pos.x()
            y = im_pos.y()

            if self.is_editing_angle:
                dx = pos.x() - self.editing_start_pos.x()
                dy = -(pos.y() - self.editing_start_pos.y())
                angle = np.arctan2(dy, dx)
                self.editing_waypoint.set_angle(angle)
            else:
                self.editing_waypoint.set_position(x, y)

            if self.parent_viewer:
                self.parent_viewer.update_display()
                self.parent_viewer.waypoint_edited.emit(self.editing_waypoint)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_enabled:
            if self.is_setting_angle and self.click_pos:
                current_pos = event.position().toPoint()
                dx = current_pos.x() - self.click_pos.x()
                dy = -(current_pos.y() - self.click_pos.y())
                if self.temp_waypoint:
                    final_angle = np.arctan2(dy, dx)
                    self.temp_waypoint.set_angle(final_angle)
                    self.waypoint_updated.emit(self.temp_waypoint)
                self.is_setting_angle = False
                self.click_pos = None
                self.temp_waypoint = None
            self.last_pos = None
        elif self.edit_mode and self.editing_waypoint:
            self.is_editing_angle = False
            if self.parent_viewer:
                self.parent_viewer.update_display()
                self.parent_viewer.waypoint_edited.emit(self.editing_waypoint)
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        """右クリックメニューの表示"""
        if not self.parent_viewer:
            return

        pos = event.pos()
        im_pos = self.parent_viewer.display_to_image_coords(pos)
        if im_pos is None:
            return
        x = im_pos.x()
        y = im_pos.y()

        from PySide6.QtWidgets import QMenu
        from PySide6.QtWidgets import QDialog

        for waypoint in self.parent_viewer.waypoints:
            hover_range = max(6, int(WAYPOINT_SETTINGS['BASE_SIZE'] * 1.6))
            if abs(waypoint.pixel_x - x) < hover_range and abs(waypoint.pixel_y - y) < hover_range:
                    menu = QMenu(self)
                    # Use global high-contrast light theme from constants.py
                    edit_action = menu.addAction("Add Actions") 
                    action = menu.exec(event.globalPos())
                    
                    if action == edit_action:
                        dialog = AttributeDialog(waypoint, format_manager.get_format(), self)
                        if dialog.exec() == QDialog.DialogCode.Accepted:
                            waypoint.attributes = dialog.get_attributes()
                            self.parent_viewer.update_display()
                            if self.parent_viewer:
                                self.parent_viewer.waypoint_edited.emit(waypoint)
                    break

class ImageViewer(QWidget):
    """画像表示用ウィジェット
    PGM画像の表示とズーム機能を管理"""
    scale_changed = Signal(float)
    layer_changed = Signal()
    waypoint_added = Signal(Waypoint)
    waypoint_removed = Signal(int)
    waypoint_edited = Signal(Waypoint)
    history_changed = Signal(bool, bool)
    
    def __init__(self):
        super().__init__()
        self.scale_factor = 1.0
        self.drawing_mode = DrawingMode.NONE
        self.last_point = None
        self.pen_color = Qt.GlobalColor.black
        self.pen_size = 2
        self.eraser_size = 10
        self.is_drawing = False
        self.current_drawing_points = []
        
        self.scroll_area = CustomScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(600, 400)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc; }")

        self.coord_label = QLabel(self.scroll_area.viewport())
        self.coord_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.98);
                border: 2px solid #64748b;
                border-radius: 6px;
                padding: 8px 12px; 
                font-size: 11px;
                font-family: 'JetBrains Mono', 'Cascadia Code', monospace;
                min-height: 44px;
                min-width: 180px;
                color: #000000;
                font-weight: 800;
            }
        """)
        self.coord_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.coord_label.hide()

        self.layers = []
        self.active_layer = None
        
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
        self.active_layer = self.drawing_layer
        
        for layer in self.layers:
            layer.changed.connect(self.on_layer_changed)
        
        self.waypoints = []
        self.waypoint_size = 15
        self.show_grid = False
        self.grid_size = 50
        self.origin_point = None
        self.resolution = 0.05

        self.setup_display()
        self.setup_scroll_area()
        self.setup_drawing_tools()

        self.pgm_display.waypoint_edited.connect(self.handle_waypoint_edited)
        self.scroll_area.scale_changed.connect(self.handle_scale_change)

        self.history = []
        self.current_index = -1
        self.max_history = 10
        
        self._is_drawing_stroke = False
        self._stroke_old_pixmap = None
        self._update_pending = False
        self._cached_result = None
        self._cache_valid = False

    def setup_display(self):
        self.pgm_display = DrawableLabel()
        self.pgm_display.parent_viewer = self
        self.pgm_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pgm_display.setStyleSheet("background-color: white;")
        self.pgm_display.waypoint_clicked.connect(self.add_waypoint)
        self.pgm_display.waypoint_updated.connect(self.update_waypoint)
        self.pgm_display.mouse_position_changed.connect(self.update_mouse_position)

        self.status_label = QLabel(self.scroll_area.viewport())
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: rgba(15, 23, 42, 0.95);
                color: #ffffff;
                padding: 10px 24px;
                border: 2px solid #3b82f6;
                border-radius: 22px;
                font-size: 13px;
                font-weight: 800;
            }
        """)
        self.status_label.hide()

        self.scroll_area.setWidget(self.pgm_display)

    def setup_scroll_area(self):
        self.scroll_area.scale_changed.connect(self.handle_scale_change)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.scroll_area)
        self.coord_label.setParent(self.scroll_area.viewport())
        self.coord_label.hide()

        original_resize_event = self.scroll_area.resizeEvent
        def new_resize_event(event):
            original_resize_event(event)
            label_width = 150
            label_height = 40
            new_x = self.scroll_area.viewport().width() - label_width - 30
            new_y = 10
            self.coord_label.setGeometry(new_x, new_y, label_width, label_height)
            
            status_width = 300
            status_height = 30
            status_x = (self.scroll_area.viewport().width() - status_width) // 2
            status_y = self.scroll_area.viewport().height() - status_height - 10
            self.status_label.setGeometry(status_x, status_y, status_width, status_height)
            
            self.coord_label.raise_()
            self.status_label.raise_()
        self.scroll_area.resizeEvent = new_resize_event

    def show_edit_message(self, message):
        self.status_label.setText(message)
        self.status_label.adjustSize()
        viewport = self.scroll_area.viewport()
        x = (viewport.width() - self.status_label.width()) // 2
        y = viewport.height() - self.status_label.height() - 20
        self.status_label.move(x, y)
        self.status_label.show()
        self.status_label.raise_()
        QTimer.singleShot(3000, self.status_label.hide)

    def setup_drawing_tools(self):
        tools_layout = QVBoxLayout()
        buttons_layout = QHBoxLayout()
        
        self.pen_button = QPushButton("ペン")
        self.pen_button.setCheckable(True)
        self.pen_button.clicked.connect(lambda: self.set_drawing_mode(DrawingMode.PEN))
        
        self.eraser_button = QPushButton("消しゴム")
        self.eraser_button.setCheckable(True)
        self.eraser_button.clicked.connect(lambda: self.set_drawing_mode(DrawingMode.ERASER))
        
        self.waypoint_button = QPushButton("ウェイポイント")
        self.waypoint_button.setCheckable(True)
        self.waypoint_button.clicked.connect(lambda: self.set_drawing_mode(DrawingMode.WAYPOINT))
        
        buttons_layout.addWidget(self.pen_button)
        buttons_layout.addWidget(self.eraser_button)
        buttons_layout.addWidget(self.waypoint_button)
        
        sliders_layout = QHBoxLayout()
        pen_slider_layout = QVBoxLayout()
        pen_slider_label = QLabel("ペンの太さ")
        self.pen_slider = QSlider(Qt.Orientation.Horizontal)
        self.pen_slider.setRange(1, 20)
        self.pen_slider.setValue(self.pen_size)
        self.pen_slider.valueChanged.connect(self.set_pen_size)
        pen_slider_layout.addWidget(pen_slider_label)
        pen_slider_layout.addWidget(self.pen_slider)
        
        eraser_slider_layout = QVBoxLayout()
        eraser_slider_label = QLabel("消しゴムの太さ")
        self.eraser_slider = QSlider(Qt.Orientation.Horizontal)
        self.eraser_slider.setRange(5, 50)
        self.eraser_slider.setValue(self.eraser_size)
        self.eraser_slider.valueChanged.connect(self.set_eraser_size)
        eraser_slider_layout.addWidget(eraser_slider_label)
        eraser_slider_layout.addWidget(self.eraser_slider)
        
        sliders_layout.addLayout(pen_slider_layout)
        sliders_layout.addLayout(eraser_slider_layout)
        
        tools_layout.addLayout(buttons_layout)
        tools_layout.addLayout(sliders_layout)
        self.layout().insertLayout(0, tools_layout)

    def set_pen_size(self, size):
        self.pen_size = size
        if self.drawing_mode == DrawingMode.PEN:
            self.pgm_display.updateCursor()

    def set_eraser_size(self, size):
        self.eraser_size = size
        if self.drawing_mode == DrawingMode.ERASER:
            self.pgm_display.updateCursor()

    def set_drawing_mode(self, mode):
        if self.drawing_mode == mode:
            self.drawing_mode = DrawingMode.NONE
            self.pen_button.setChecked(False)
            self.eraser_button.setChecked(False)
            self.waypoint_button.setChecked(False)
            self.pgm_display.set_drawing_mode(False)
            self.scroll_area.set_drawing_mode(False)
            return

        self.drawing_mode = mode
        self.pen_button.setChecked(mode == DrawingMode.PEN)
        self.eraser_button.setChecked(mode == DrawingMode.ERASER)
        self.waypoint_button.setChecked(mode == DrawingMode.WAYPOINT)
        self.pgm_display.set_drawing_mode(mode != DrawingMode.NONE)
        self.scroll_area.set_drawing_mode(mode != DrawingMode.NONE)
        if (mode != DrawingMode.NONE):
            if (mode == DrawingMode.WAYPOINT):
                self.pgm_display.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.pgm_display.updateCursor()

    def draw_line(self, start_pos, end_pos):
        if not self.drawing_layer.pixmap or self.drawing_mode == DrawingMode.NONE:
            return

        if not self._is_drawing_stroke:
            self._is_drawing_stroke = True
            self._stroke_old_pixmap = self.drawing_layer.pixmap.copy()

        start_img = self.display_to_image_coords(start_pos)
        end_img = self.display_to_image_coords(end_pos)
        if start_img is None or end_img is None:
            return
        scaled_start = start_img
        scaled_end = end_img

        if self.pgm_display.pixmap() and self.pgm_layer.pixmap:
            orig_w = self.pgm_layer.pixmap.width()
            disp_w = self.pgm_display.pixmap().width()
            scale_factor = orig_w / disp_w if disp_w else 1.0
        else:
            scale_factor = 1.0
        scaled_pen_size = max(1, int(self.pen_size * scale_factor))
        scaled_eraser_size = max(1, int(self.eraser_size * scale_factor))

        painter = QPainter(self.drawing_layer.pixmap)
        if self.drawing_mode == DrawingMode.PEN:
            painter.setPen(QPen(self.pen_color, scaled_pen_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        else:
            painter.setPen(QPen(Qt.GlobalColor.white, scaled_eraser_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        painter.drawLine(scaled_start, scaled_end)
        painter.end()
        self._cache_valid = False
        self.update_display()

    def mousePressEvent(self, event):
        if self.drawing_mode != DrawingMode.NONE:
            self.last_point = event.position().toPoint()
            self.draw_line(event.position().toPoint(), event.position().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_mode != DrawingMode.NONE and self.last_point:
            current_pos = event.position().toPoint()
            self.draw_line(self.last_point, current_pos)
            self.last_point = current_pos
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_mode != DrawingMode.NONE:
            if self._is_drawing_stroke and self._stroke_old_pixmap is not None:
                self.add_to_history({
                    'type': 'draw',
                    'old_pixmap': self._stroke_old_pixmap,
                    'new_pixmap': self.drawing_layer.pixmap.copy()
                })
                self._stroke_old_pixmap = None
            self._is_drawing_stroke = False
            self.last_point = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def load_image(self, img_array, width, height):
        bytes_per_line = width
        q_img = QImage(img_array.data, width, height, bytes_per_line,
                    QImage.Format.Format_Grayscale8)
        self.pgm_layer.pixmap = QPixmap.fromImage(q_img)
        self.drawing_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
        self.drawing_layer.pixmap.fill(Qt.GlobalColor.transparent)
        self.update_display()
        self.coord_label.show()

    def zoom_in(self):
        self.handle_scale_change(1.2)

    def zoom_out(self):
        self.handle_scale_change(1.0/1.2)

    def zoom_reset(self):
        self.scale_factor = 1.0
        self.update_display()
        self.scale_changed.emit(self.scale_factor)

    def handle_scale_change(self, factor):
        new_scale = self.scale_factor * factor
        if MIN_SCALE <= new_scale <= MAX_SCALE:
            self.scale_factor = new_scale
            self.update_display()
            self.scale_changed.emit(self.scale_factor)
            if self.drawing_mode != DrawingMode.NONE:
                self.pgm_display.updateCursor()

    def add_waypoint(self, pos):
        if not self.pgm_layer.pixmap:
            return
        im_pos = self.display_to_image_coords(pos)
        if im_pos is None:
            return
        x, y = im_pos.x(), im_pos.y()
        waypoint = Waypoint(x, y)
        if self.origin_point:
            origin_x, origin_y = self.origin_point
            waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
        self.waypoints.append(waypoint)
        self.pgm_display.temp_waypoint = waypoint
        if not self.waypoint_layer.pixmap:
            self.waypoint_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
            self.waypoint_layer.pixmap.fill(Qt.GlobalColor.transparent)
        self.waypoint_added.emit(waypoint)
        self.update_display()
        self.add_to_history({'type': 'waypoint_add', 'waypoint': waypoint})

    def update_waypoint(self, waypoint):
        self.update_display()
        self.waypoint_added.emit(waypoint)

    def update_display(self):
        if not self.pgm_layer.pixmap:
            return
        result = QPixmap(self.pgm_layer.pixmap.size())
        result.fill(Qt.GlobalColor.white)
        painter = QPainter(result)
        if (self.pgm_layer.visible and self.pgm_layer.pixmap):
            painter.setOpacity(self.pgm_layer.opacity)
            painter.drawPixmap(0, 0, self.pgm_layer.pixmap)
        if self.show_grid:
            painter.setOpacity(0.3)
            pen = QPen(Qt.GlobalColor.gray)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for x in range(0, result.width(), self.grid_size):
                painter.drawLine(x, 0, x, result.height())
            for y in range(0, result.height(), self.grid_size):
                painter.drawLine(0, y, result.width(), y)
        if self.drawing_layer.visible and self.drawing_layer.pixmap:
            painter.setOpacity(self.drawing_layer.opacity)
            painter.drawPixmap(0, 0, self.drawing_layer.pixmap)
        if self.path_layer.visible and self.path_layer.pixmap:
            painter.setOpacity(self.path_layer.opacity)
            painter.drawPixmap(0, 0, self.path_layer.pixmap)
        if self.waypoints and self.waypoint_layer.visible:
            painter.setOpacity(self.waypoint_layer.opacity)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            for waypoint in self.waypoints:
                x, y = waypoint.pixel_x, waypoint.pixel_y
                base_size = WAYPOINT_SETTINGS['BASE_SIZE']
                is_editing = (self.pgm_display.edit_mode and self.pgm_display.editing_waypoint and self.pgm_display.editing_waypoint.number == waypoint.number)
                color = QColor(0, 120, 255, 255) if is_editing else QColor(255, 0, 0, 255)
                size_multiplier = WAYPOINT_SETTINGS['EDIT_SIZE_MULT'] if is_editing else 1.0
                pen = QPen(color)
                pen.setWidth(3)
                painter.setPen(pen)
                adjusted_size = base_size * size_multiplier
                angle_line_length = adjusted_size * WAYPOINT_SETTINGS['ARROW_LENGTH_MULT']
                end_x = x + int(angle_line_length * np.cos(waypoint.angle))
                end_y = y - int(angle_line_length * np.sin(waypoint.angle))
                painter.drawLine(x, y, end_x, end_y)
                arrow_size = adjusted_size * WAYPOINT_SETTINGS['ARROW_WIDTH_MULT']
                arrow_angle1 = waypoint.angle + np.pi * 3/4
                arrow_angle2 = waypoint.angle - np.pi * 3/4
                arrow_x1 = end_x + int(arrow_size * np.cos(arrow_angle1))
                arrow_y1 = end_y - int(arrow_size * np.sin(arrow_angle1))
                arrow_x2 = end_x + int(arrow_size * np.cos(arrow_angle2))
                arrow_y2 = end_y - int(arrow_size * np.sin(arrow_angle2))
                painter.drawLine(end_x, end_y, arrow_x1, arrow_y1)
                painter.drawLine(end_x, end_y, arrow_x2, arrow_y2)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(x - adjusted_size, y - adjusted_size, adjusted_size * 2, adjusted_size * 2)
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
                num_attributes = len(waypoint.attributes)
                if (num_attributes > 0):
                    painter.setPen(QColor(255, 255, 255))
                    font.setPointSize(WAYPOINT_SETTINGS['FONT_SIZE_ATTR_MULT'] * WAYPOINT_SETTINGS['BASE_SIZE'])
                    font.setBold(True)
                    painter.setFont(font)
                    attr_text = str(num_attributes)
                    attr_x = x + adjusted_size - 5
                    attr_y = y - adjusted_size + 5
                    painter.setBrush(QColor(50, 50, 50, 200))
                    painter.drawEllipse(attr_x - 8, attr_y - 12, 16, 16)
                    painter.drawText(attr_x - 3, attr_y, attr_text)
                waypoint.hover_rect = QRect(x - adjusted_size, y - adjusted_size, adjusted_size * 2, adjusted_size * 2)
        if self.origin_layer.visible and self.origin_layer.pixmap:
            painter.setOpacity(self.origin_layer.opacity)
            painter.drawPixmap(0, 0, self.origin_layer.pixmap)
        painter.end()
        new_size = QSize(int(result.width() * self.scale_factor), int(result.height() * self.scale_factor))
        use_fast = (result.width() > 2000 or result.height() > 2000 or self._is_drawing_stroke or self.scale_factor < 0.5)
        transform_mode = (Qt.TransformationMode.FastTransformation if use_fast else Qt.TransformationMode.SmoothTransformation)
        scaled_pixmap = result.scaled(new_size, Qt.AspectRatioMode.KeepAspectRatio, transform_mode)
        self.pgm_display.setPixmap(scaled_pixmap)
        self.pgm_display.adjustSize()

    def get_displayed_pixmap_info(self):
        if not self.pgm_display or not self.pgm_display.pixmap() or not self.pgm_layer.pixmap: return None
        displayed_pm = self.pgm_display.pixmap()
        disp_w, disp_h = displayed_pm.width(), displayed_pm.height()
        label_w, label_h = self.pgm_display.width(), self.pgm_display.height()
        offset_x, offset_y = max(0, (label_w - disp_w) // 2), max(0, (label_h - disp_h) // 2)
        return disp_w, disp_h, offset_x, offset_y, displayed_pm

    def display_to_image_coords(self, pos: QPoint):
        info = self.get_displayed_pixmap_info()
        if not info: return None
        disp_w, disp_h, offset_x, offset_y, displayed_pm = info
        x_disp, y_disp = pos.x() - offset_x, pos.y() - offset_y
        if x_disp < 0 or y_disp < 0 or x_disp >= disp_w or y_disp >= disp_h: return None
        orig_pm = self.pgm_layer.pixmap
        orig_w, orig_h = orig_pm.width(), orig_pm.height()
        img_x, img_y = int(x_disp * (orig_w / disp_w)), int(y_disp * (orig_h / disp_h))
        return QPoint(img_x, img_y)

    def image_to_display_coords(self, image_pos: QPoint):
        info = self.get_displayed_pixmap_info()
        if not info: return None
        disp_w, disp_h, offset_x, offset_y, displayed_pm = info
        orig_pm = self.pgm_layer.pixmap
        orig_w, orig_h = orig_pm.width(), orig_pm.height()
        x_disp, y_disp = int(image_pos.x() * (disp_w / orig_w)), int(image_pos.y() * (disp_h / orig_h))
        return QPoint(x_disp + offset_x, y_disp + offset_y)

    def on_layer_changed(self):
        self.update_display()
        self.layer_changed.emit()

    def remove_waypoint(self, number):
        self.waypoints = [wp for wp in self.waypoints if wp.number != number]
        Waypoint.reset_counter()
        self.waypoint_removed.emit(number)
        for wp in self.waypoints:
            Waypoint.counter += 1
            wp.renumber(Waypoint.counter)
            self.waypoint_added.emit(wp)
        self.update_display()

    def remove_all_waypoints(self):
        self.waypoints.clear()
        Waypoint.reset_counter()
        self.waypoint_removed.emit(-1)
        self.update_display()

    def reorder_waypoints(self, source_number, target_number):
        if not self.waypoints: return
        source_wp = next((wp for wp in self.waypoints if wp.number == source_number), None)
        if not source_wp: return
        source_index = self.waypoints.index(source_wp)
        target_index = next((i for i, wp in enumerate(self.waypoints) if wp.number == target_number), -1)
        if target_index == -1: return
        self.waypoints.pop(source_index)
        self.waypoints.insert(target_index, source_wp)
        Waypoint.reset_counter()
        self.waypoint_removed.emit(-1)
        for wp in self.waypoints:
            Waypoint.counter += 1
            wp.renumber(Waypoint.counter)
            self.waypoint_added.emit(wp)
        self.update_display()

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.update_display()

    def update_mouse_position(self, pos):
        if not self.pgm_layer.pixmap or not self.origin_point: return
        im_pos = self.display_to_image_coords(pos)
        if im_pos is None:
            self.coord_label.hide()
            return
        pixel_x, pixel_y = im_pos.x(), im_pos.y()
        origin_x, origin_y = self.origin_point
        rel_x, rel_y = (pixel_x - origin_x) / 20, (origin_y - pixel_y) / 20
        self.coord_label.setText(f"Pixel: ({pixel_x}, {pixel_y})\nMetric: ({rel_x:.2f}, {rel_y:.2f})")
        self.coord_label.show()

    def load_yaml_file(self, file_path):
        try:
            with open(file_path, 'r') as f: yaml_data = yaml.safe_load(f)
            if 'origin' in yaml_data:
                origin = yaml_data['origin']
                if len(origin) >= 2:
                    self.resolution = float(yaml_data.get('resolution', 0.05))
                    x_pixel = int(-origin[0] / self.resolution)
                    y_pixel = int(-origin[1] / self.resolution)
                    if self.pgm_layer.pixmap:
                        height = self.pgm_layer.pixmap.height()
                        y_pixel = height - y_pixel
                    self.origin_point = (x_pixel, y_pixel)
                    self.draw_origin_point()
                    self.update_all_waypoint_coordinates()
        except Exception as e: print(f"Error loading YAML file: {str(e)}")

    def update_all_waypoint_coordinates(self):
        if not self.origin_point: return
        origin_x, origin_y = self.origin_point
        for waypoint in self.waypoints:
            waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
            self.waypoint_added.emit(waypoint)

    def draw_origin_point(self):
        if not self.origin_point or not self.pgm_layer.pixmap: return
        if not self.origin_layer.pixmap or self.origin_layer.pixmap.size() != self.pgm_layer.pixmap.size():
            self.origin_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
            self.origin_layer.pixmap.fill(Qt.GlobalColor.transparent)
        self.origin_layer.pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self.origin_layer.pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y = self.origin_point
        marker_size = 20
        pen = QPen(QColor(255, 0, 0))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(x - marker_size, y, x + marker_size, y)
        painter.drawLine(x, y - marker_size, x, y + marker_size)
        painter.drawEllipse(x - marker_size//2, y - marker_size//2, marker_size, marker_size)
        painter.end()
        self.update_display()

    def generate_path(self):
        if self.waypoints and len(self.waypoints) >= 2:
            if not self.path_layer.pixmap or self.path_layer.pixmap.size() != self.pgm_layer.pixmap.size():
                self.path_layer.pixmap = QPixmap(self.pgm_layer.pixmap.size())
            self.path_layer.pixmap.fill(Qt.GlobalColor.transparent)
            # Use RightPanel to check if path should be generated
            # Circular dependency check: We'll assume the setting is accessible
            # This logic might need to be refined if it relies on a specific UI state
            painter = QPainter(self.path_layer.pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(Qt.GlobalColor.green, 3)
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            for i in range(len(self.waypoints) - 1):
                start, end = self.waypoints[i], self.waypoints[i + 1]
                painter.drawLine(start.pixel_x, start.pixel_y, end.pixel_x, end.pixel_y)
            painter.end()
        else:
            if self.path_layer.pixmap: self.path_layer.pixmap.fill(Qt.GlobalColor.transparent)
        self.update_display()

    def handle_waypoint_edited(self, waypoint):
        old_state = {'pixel_x': waypoint.pixel_x, 'pixel_y': waypoint.pixel_y, 'angle': waypoint.angle}
        if self.origin_point:
            origin_x, origin_y = self.origin_point
            waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
        self.waypoint_edited.emit(waypoint)
        self.update_display()
        new_state = {'pixel_x': waypoint.pixel_x, 'pixel_y': waypoint.pixel_y, 'angle': waypoint.angle}
        self.add_to_history({'type': 'waypoint_edit', 'waypoint': waypoint, 'old_state': old_state, 'new_state': new_state})

    def enter_edit_mode(self, waypoint):
        self.pgm_display.edit_mode, self.pgm_display.editing_waypoint = True, waypoint
        self.pgm_display.setCursor(Qt.CursorShape.SizeAllCursor)

    def exit_edit_mode(self):
        self.pgm_display.edit_mode, self.pgm_display.editing_waypoint = False, None
        self.pgm_display.setCursor(Qt.CursorShape.ArrowCursor)

    def get_combined_pixmap(self):
        if not self.pgm_layer.pixmap: return None
        result = QPixmap(self.pgm_layer.pixmap.size())
        result.fill(Qt.GlobalColor.white)
        painter = QPainter(result)
        for layer in [self.pgm_layer, self.drawing_layer]:
            if layer.visible and layer.pixmap:
                painter.setOpacity(layer.opacity)
                painter.drawPixmap(0, 0, layer.pixmap)
        painter.end()
        return result

    def import_waypoints_from_yaml(self, yaml_data):
        if 'waypoints' not in yaml_data: return
        self.waypoints.clear()
        Waypoint.reset_counter()
        for wp_data in yaml_data['waypoints']:
            try:
                if self.origin_point:
                    origin_x, origin_y = self.origin_point
                    x_m, y_m = wp_data['x'] * 20, wp_data['y'] * 20
                    px, py = int(origin_x + x_m), int(origin_y - y_m)
                    waypoint = Waypoint(px, py, wp_data['angle_radians'])
                    waypoint.update_metric_coordinates(origin_x, origin_y, self.resolution)
                    for k, v in wp_data.items():
                        if k not in ['number', 'x', 'y', 'angle_degrees', 'angle_radians']:
                            waypoint.set_attribute(k, v)
                    self.waypoints.append(waypoint)
                    self.waypoint_added.emit(waypoint)
            except Exception as e: print(f"Error importing waypoint: {e}"); continue
        self.update_display()

    def add_to_history(self, action):
        self.history = self.history[:self.current_index + 1]
        self.history.append(action)
        if len(self.history) > self.max_history: self.history.pop(0)
        else: self.current_index += 1
        self.history_changed.emit(self.can_undo(), self.can_redo())
    
    def can_undo(self): return self.current_index >= 0
    def can_redo(self): return self.current_index < len(self.history) - 1
    
    def undo(self):
        if not self.can_undo(): return
        action = self.history[self.current_index]
        self.current_index -= 1
        if action['type'] == 'waypoint_add': self.remove_waypoint(action['waypoint'].number)
        elif action['type'] == 'waypoint_remove':
            self.waypoints.append(action['waypoint'])
            self.waypoint_added.emit(action['waypoint'])
        elif action['type'] == 'waypoint_edit':
            wp, old = action['waypoint'], action['old_state']
            wp.pixel_x, wp.pixel_y, wp.angle = old['pixel_x'], old['pixel_y'], old['angle']
            if self.origin_point:
                o_x, o_y = self.origin_point
                wp.update_metric_coordinates(o_x, o_y, self.resolution)
            self.waypoint_edited.emit(wp)
        elif action['type'] == 'draw': self.drawing_layer.pixmap = action['old_pixmap']
        self.update_display()
        self.history_changed.emit(self.can_undo(), self.can_redo())
    
    def redo(self):
        if not self.can_redo(): return
        self.current_index += 1
        action = self.history[self.current_index]
        if action['type'] == 'waypoint_add':
            self.waypoints.append(action['waypoint'])
            self.waypoint_added.emit(action['waypoint'])
        elif action['type'] == 'waypoint_remove': self.remove_waypoint(action['waypoint'].number)
        elif action['type'] == 'waypoint_edit':
            wp, new = action['waypoint'], action['new_state']
            wp.pixel_x, wp.pixel_y, wp.angle = new['pixel_x'], new['pixel_y'], new['angle']
            if self.origin_point:
                o_x, o_y = self.origin_point
                wp.update_metric_coordinates(o_x, o_y, self.resolution)
            self.waypoint_edited.emit(wp)
        elif action['type'] == 'draw': self.drawing_layer.pixmap = action['new_pixmap']
        self.update_display()
        self.history_changed.emit(self.can_undo(), self.can_redo())
