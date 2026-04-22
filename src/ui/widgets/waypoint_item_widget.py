import numpy as np
from PySide6.QtWidgets import QWidget, QHBoxLayout, QFrame, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtGui import QDrag, QCursor

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
                background-color: #ffffff;
                border: 2px solid #94a3b8;
                border-radius: 8px;
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
                color: #64748b;
                font-size: 18px;
                font-weight: bold;
                padding: 0 4px;
            }
        """)
        
        # ウェイポイント番号（エレガントな青いバッジ）
        number_badge = QLabel(f"{waypoint.number:02d}")
        number_badge.setStyleSheet("""
            QLabel {
                color: #ffffff;
                background-color: #3b82f6;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 700;
                text-align: center;
            }
        """)
        number_badge.setFixedWidth(45)
        
        # 座標情報
        self.coord_label = QLabel(f"({waypoint.x:.2f}, {waypoint.y:.2f})")
        self.coord_label.setStyleSheet("""
            QLabel {
                color: #000000;
                font-size: 12px;
                font-weight: 600;
            }
        """)
        
        # 角度表示
        degrees = int(waypoint.angle * 180 / np.pi)
        self.angle_label = QLabel(f"{degrees}°")
        self.angle_label.setStyleSheet("""
            QLabel {
                color: #0f172a;
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
                min-width: 40px;
                text-align: center;
            }
        """)

        # 削除ボタン
        delete_button = QPushButton("×")
        delete_button.setFixedSize(24, 24)
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 12px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
                color: #ef4444;
            }
        """)
        delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.waypoint_number))
        
        # フレームにウィジェットを追加
        frame_layout.addWidget(drag_handle)
        frame_layout.addWidget(number_badge)
        frame_layout.addWidget(self.coord_label, 1)
        frame_layout.addWidget(self.angle_label)
        frame_layout.addWidget(delete_button)
        
        # メインレイアウトにフレームを追加
        layout.addWidget(self.frame)
        
        # ホバー効果
        self.setStyleSheet("""
            WaypointListItem {
                background-color: transparent;
                margin: 2px 0;
            }
            WaypointListItem:hover QFrame {
                border: 2px solid #2563eb;
                background-color: #f1f5f9;
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
        # Note: RightPanel is imported locally or we assume the hierarchy
        from ..panels.right_panel import RightPanel
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
            right_panel = self.get_right_panel()
            if right_panel:
                # ドロップ位置に基づいて順序を変更
                right_panel.handle_waypoint_reorder(source_number, target_number)
        
        # frameのスタイルを元に戻す
        self.frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        event.accept()
