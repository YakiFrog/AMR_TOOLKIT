from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QCursor, QPixmap

class DrawableLabel(QLabel):
    """描画可能なラベル"""
    waypoint_clicked = Signal(QPoint)
    waypoint_updated = Signal(object)
    waypoint_completed = Signal(QPoint)
    mouse_position_changed = Signal(QPoint)
    waypoint_edited = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.parent_viewer = None
        self.drawing_enabled = False
        self.setup_drawing_tools()

    def setup_drawing_tools(self):
        """描画ツールの初期化"""
        self.last_point = None
        self.cursor_pixmap = None
        self.current_cursor_size = 0
        self.temp_waypoint = None
        self.is_setting_angle = False
        self.click_pos = None
        self.edit_mode = False
        self.editing_waypoint = None

    def updateCursor(self):
        """カーソルの更新"""
        if not self.parent_viewer:
            return

        # 現在のツールのサイズを取得
        size = self.get_tool_size()
        
        # スケールに応じてカーソルサイズを調整
        scaled_size = self.calculate_scaled_size(size)
            
        # カーソルの作成と設定
        self.create_cursor(scaled_size)

    def create_cursor(self, size):
        """カーソルの作成"""
        cursor_size = max(size, 8)
        self.cursor_pixmap = QPixmap(cursor_size, cursor_size)
        self.cursor_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(self.cursor_pixmap)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(0, 0, cursor_size-1, cursor_size-1)
        painter.end()
        
        cursor = QCursor(self.cursor_pixmap, cursor_size // 2, cursor_size // 2)
        self.setCursor(cursor)

    def get_tool_size(self):
        """現在のツールサイズを取得"""
        if self.parent_viewer.drawing_mode == DrawingMode.PEN:
            return self.parent_viewer.pen_size
        else:
            return self.parent_viewer.eraser_size

    def calculate_scaled_size(self, size):
        """スケールに応じたサイズを計算"""
        pixmap_geometry = self.geometry()
        if self.parent_viewer.drawing_layer.pixmap:
            scale_x = pixmap_geometry.width() / self.parent_viewer.drawing_layer.pixmap.width()
            return int(size * scale_x)
        return size

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

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        self.mouse_position_changed.emit(pos)
        
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

    def mouseDoubleClickEvent(self, event):
        """ウェイポイントの編集モード切り替え"""
        if not self.parent_viewer:
            return
            
        pos = event.position().toPoint()
        pixmap_geometry = self.geometry()
        if self.parent_viewer.drawing_layer.pixmap:
            scale_x = self.parent_viewer.drawing_layer.pixmap.width() / pixmap_geometry.width()
            scale_y = self.parent_viewer.drawing_layer.pixmap.height() / pixmap_geometry.height()
            x = int(pos.x() * scale_x)
            y = int(pos.y() * scale_y)
            
            if self.edit_mode and self.editing_waypoint:
                self.exit_edit_mode()
            else:
                self.try_enter_edit_mode(x, y)

    def exit_edit_mode(self):
        """編集モードを終了"""
        self.edit_mode = False
        self.editing_waypoint = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.parent_viewer:
            self.parent_viewer.update_display()

    def try_enter_edit_mode(self, x, y):
        """編集モードに入る"""
        if not self.parent_viewer:
            return

        for waypoint in self.parent_viewer.waypoints:
            if abs(waypoint.pixel_x - x) < 15 and abs(waypoint.pixel_y - y) < 15:
                self.edit_mode = True
                self.editing_waypoint = waypoint
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                if self.parent_viewer:
                    self.parent_viewer.show_edit_message("ドラッグで移動、Shift+ドラッグで角度を変更")
                    self.parent_viewer.update_display()
                break

    # ...existing drawing methods...
