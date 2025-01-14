from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QScrollArea, QFrame, QCheckBox, QSlider)
from PySide6.QtCore import Qt, Signal, QTimer, QMimeData
from PySide6.QtGui import QDrag, QCursor
import numpy as np

class LayerControl(QWidget):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        self.visibility_cb = QCheckBox(self.layer.name)
        self.visibility_cb.setChecked(self.layer.visible)
        self.visibility_cb.stateChanged.connect(self._on_visibility_changed)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(int(self.layer.opacity * 100))
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        
        layout.addWidget(self.visibility_cb)
        layout.addWidget(self.opacity_slider, stretch=1)

class WaypointListItem(QWidget):
    """ウェイポイントリストの各アイテム用ウィジェット"""
    delete_clicked = Signal(int)
    
    def __init__(self, waypoint):
        super().__init__()
        self.waypoint_number = waypoint.number
        self.waypoint = waypoint
        self.setup_ui()
        
    # ...existing code...

class RightPanel(QWidget):
    """右側のパネル"""
    waypoint_delete_requested = Signal(int)
    all_waypoints_delete_requested = Signal()
    waypoint_reorder_requested = Signal(int, int)
    generate_path_requested = Signal()
    export_requested = Signal(bool, bool)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.waypoint_widgets = {}

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # レイヤーパネル
        self.layer_widget = self.create_layer_panel()
        layout.addWidget(self.layer_widget)
        
        # ウェイポイントパネル
        self.waypoint_widget = self.create_waypoint_panel()
        layout.addWidget(self.waypoint_widget)
        
        # エクスポートパネル
        self.export_widget = self.create_export_panel()
        layout.addWidget(self.export_widget)
        
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
        self.layer_list_layout.setSpacing(5)
        self.layer_list.setMinimumHeight(100)
        
        layout.addWidget(title_label)
        layout.addWidget(self.layer_list)
        layout.setSpacing(5)
        
        return widget

    def create_waypoint_panel(self):
        """ウェイポイントリストパネルを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)
        
        # ヘッダー部分のレイアウト
        header_layout = QHBoxLayout()
        
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
        
        self.generate_path_button = QPushButton("Generate Path")
        self.generate_path_button.setCheckable(True)
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
        header_layout.addStretch()
        header_layout.addWidget(self.generate_path_button)
        header_layout.addWidget(clear_button)
        
        # スクロールエリアの設定
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)
        
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
        
        self.scroll_area.setWidget(self.waypoint_list)
        self.scroll_area.setMinimumHeight(150)
        self.scroll_area.setMaximumHeight(300)
        
        layout.addLayout(header_layout)
        layout.addWidget(self.scroll_area)
        
        return widget

    def create_export_panel(self):
        """エクスポートパネルを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title_label = QLabel("Export")
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
                padding: 10px;
            }
        """)
        content_layout = QVBoxLayout(content)
        
        self.export_pgm_cb = QCheckBox("Export PGM with drawings")
        self.export_waypoints_cb = QCheckBox("Export Waypoints YAML")
        
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
        
        content_layout.addWidget(self.export_pgm_cb)
        content_layout.addWidget(self.export_waypoints_cb)
        content_layout.addWidget(export_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title_label)
        layout.addWidget(content)
        
        return widget

    def handle_path_toggle(self):
        """パスの表示/非表示を切り替え"""
        if self.generate_path_button.isChecked():
            self.generate_path_requested.emit()
        else:
            self.generate_path_requested.emit()  # パスをクリア

    def handle_export(self):
        """エクスポートボタンクリック時の処理"""
        export_pgm = self.export_pgm_cb.isChecked()
        export_waypoints = self.export_waypoints_cb.isChecked()
        if export_pgm or export_waypoints:
            self.export_requested.emit(export_pgm, export_waypoints)

    def add_waypoint_to_list(self, waypoint):
        """ウェイポイントリストに新しいウェイポイントを追加"""
        if waypoint.number in self.waypoint_widgets:
            self.waypoint_widgets[waypoint.number].update_label(waypoint.display_name)
            return

        waypoint_item = WaypointListItem(waypoint)
        self.waypoint_widgets[waypoint.number] = waypoint_item
        waypoint_item.delete_clicked.connect(self.waypoint_delete_requested.emit)
        self.waypoint_list_layout.addWidget(waypoint_item)

    def remove_waypoint_from_list(self, number):
        """ウェイポイントをリストから削除"""
        if number == -1:  # 全削除の場合
            self.clear_waypoint_list()
            return
            
        if number in self.waypoint_widgets:
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

    def handle_waypoint_reorder(self, source_number, target_number):
        """ウェイポイントの順序変更を処理"""
        self.waypoint_reorder_requested.emit(source_number, target_number)

    def update_layer_list(self, layers):
        """レイヤーリストを更新"""
        for i in reversed(range(self.layer_list_layout.count())): 
            widget = self.layer_list_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        
        for layer in layers:
            layer_control = LayerControl(layer, self)
            self.layer_list_layout.addWidget(layer_control)
