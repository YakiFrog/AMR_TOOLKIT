from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QFrame, QDrag)
from PySide6.QtCore import Qt, Signal, QMimeData
import numpy as np

class WaypointListItem(QWidget):
    """ウェイポイントリストアイテム"""
    delete_clicked = Signal(int)
    
    def __init__(self, waypoint):
        super().__init__()
        self.waypoint_number = waypoint.number
        self.waypoint = waypoint
        self.setup_ui()

    def setup_ui(self):
        """UIの初期化"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        # フレームの設定
        self.frame = QFrame()
        self.frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        
        # フレーム内のレイアウト
        frame_layout = QHBoxLayout(self.frame)
        frame_layout.setContentsMargins(8, 4, 8, 4)
        frame_layout.setSpacing(12)

        # コンポーネントの追加
        self.setup_components(frame_layout)
        
        # メインレイアウトにフレームを追加
        layout.addWidget(self.frame)

    def setup_components(self, layout):
        """コンポーネントの設定"""
        # ドラッグハンドル
        drag_handle = QLabel("⋮")
        drag_handle.setStyleSheet("""
            QLabel {
                color: #9e9e9e;
                font-size: 16px;
                padding: 0 2px;
            }
        """)
        
        # ウェイポイント番号バッジ
        number_badge = QLabel(f"{self.waypoint.number:02d}")
        number_badge.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #f44336;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        
        # ...existing code for coordinate and angle labels...

        layout.addWidget(drag_handle)
        layout.addWidget(number_badge)
        layout.addWidget(self.coord_label, 1)
        layout.addWidget(self.angle_label)

    def update_label(self, text):
        if hasattr(self, 'waypoint'):
            degrees = int(self.waypoint.angle * 180 / np.pi)
            self.coord_label.setText(f"({self.waypoint.x:.2f}, {self.waypoint.y:.2f})")
            self.angle_label.setText(f"{degrees}°")

    def mousePressEvent(self, event):
        if not self.isVisible():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                right_panel = self.get_right_panel()
                if (right_panel):
                    right_panel.stop_auto_scroll()
                
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(str(self.waypoint_number))
                drag.setMimeData(mime_data)
                drag.exec(Qt.DropAction.MoveAction)
            except RuntimeError:
                pass

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.source() != self:
            event.accept()
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
        """ドラッグが領域を離れた時の処理"""
        self.frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        """ドロップ時の処理"""
        source_number = int(event.mimeData().text())
        target_number = self.waypoint_number
        
        if source_number != target_number:
            right_panel = self.get_right_panel()
            if right_panel:
                right_panel.handle_waypoint_reorder(source_number, target_number)
        
        self.frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        event.accept()

    def get_right_panel(self):
        """親のRightPanelウィジェットを取得"""
        parent = self.parent()
        while parent and not isinstance(parent, 'RightPanel'):
            parent = parent.parent()
        return parent

    # ...remaining waypoint list item methods...
