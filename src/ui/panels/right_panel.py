import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QScrollArea, QCheckBox, QFileDialog,
                               QLineEdit)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QCursor

from ..widgets.waypoint_item_widget import WaypointListItem
from ..widgets.layer_widget import LayerControl
from .format_editor_panel import FormatEditorPanel


class LandmarkListItem(QWidget):
    delete_clicked = Signal(int)
    name_changed = Signal(int, str)

    def __init__(self, landmark):
        super().__init__()
        self.landmark = landmark
        self.setup_ui()
        self.update_label()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        top_layout = QHBoxLayout()
        self.name_edit = QLineEdit(self.landmark.name)
        self.name_edit.setPlaceholderText("ランドマーク名")
        self.name_edit.editingFinished.connect(self.emit_name_changed)

        delete_button = QPushButton("×")
        delete_button.setFixedSize(24, 24)
        delete_button.setToolTip("ランドマークを削除")
        delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.landmark.number))

        top_layout.addWidget(self.name_edit, 1)
        top_layout.addWidget(delete_button)

        self.detail_label = QLabel()
        self.detail_label.setStyleSheet("color: #334155; font-size: 11px;")

        layout.addLayout(top_layout)
        layout.addWidget(self.detail_label)
        self.setStyleSheet("""
            LandmarkListItem {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
        """)

    def emit_name_changed(self):
        self.name_changed.emit(self.landmark.number, self.name_edit.text())

    def update_label(self):
        self.name_edit.blockSignals(True)
        self.name_edit.setText(self.landmark.name)
        self.name_edit.blockSignals(False)
        degrees = int(self.landmark.angle * 180 / np.pi)
        self.detail_label.setText(f"x={self.landmark.x:.2f}, y={self.landmark.y:.2f}, yaw={degrees}°")

class RightPanel(QWidget):
    """右側のパネル"""
    waypoint_delete_requested = Signal(int)  # 新しいシグナルを追加
    all_waypoints_delete_requested = Signal()  # 新しいシグナル
    waypoint_reorder_requested = Signal(int, int)  # 順序変更シグナルを追加
    landmark_delete_requested = Signal(int)
    all_landmarks_delete_requested = Signal()
    landmark_name_changed = Signal(int, str)
    landmark_import_requested = Signal(str)
    landmark_export_requested = Signal()
    generate_path_requested = Signal()  # パス生成用シグナル
    export_requested = Signal(bool, bool)  # (export_pgm, export_waypoints)
    waypoint_import_requested = Signal(str)  # YAMLファイルパスを送信
    layer_add_requested = Signal()  # レイヤー追加要求用
    
    def __init__(self):
        super().__init__()
        self.waypoint_widgets = {}  # ウェイポイントウィジェットを保持する辞書
        self.landmark_widgets = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setStyleSheet("""
            RightPanel { 
                background-color: #e2e8f0; 
                border-left: 2px solid #64748b;
            }
        """)

        # レイヤーパネルを追加
        self.layer_widget = self.create_layer_panel()
        layout.addWidget(self.layer_widget)
        
        # ウェイポイントリストパネルを追加
        self.waypoint_widget = self.create_waypoint_panel()
        layout.addWidget(self.waypoint_widget)

        self.landmark_widget = self.create_landmark_panel()
        layout.addWidget(self.landmark_widget)
        
        # Format Editor を追加
        self.format_editor = FormatEditorPanel()
        layout.addWidget(self.format_editor)
        
        # エクスポートパネルを追加
        self.export_widget = self.create_export_panel()
        layout.addWidget(self.export_widget)

        self.setLayout(layout)

    def create_layer_panel(self):
        """レイヤーパネルを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ヘッダー (タイトル + 追加ボタン)
        header_layout = QHBoxLayout()
        title_label = QLabel("Layers")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 800;
                color: #000000;
                padding: 8px 12px;
                background-color: #cbd5e1;
                border-bottom: 2px solid #64748b;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
        """)
        
        add_button = QPushButton("+")
        add_button.setToolTip("Add Map Layer (.pgm / .yaml)")
        add_button.setFixedSize(24, 24)
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border-radius: 12px;
                font-weight: bold;
                font-size: 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        add_button.clicked.connect(self.layer_add_requested.emit)
        
        header_layout.addWidget(title_label, stretch=1)
        header_layout.addWidget(add_button)
        
        # スクロールエリアを追加
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 2px solid #94a3b8;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
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
        
        layout.addLayout(header_layout)
        layout.addWidget(scroll_area)
        layout.setSpacing(5)
        
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
                font-size: 13px;
                font-weight: 800;
                color: #000000;
                padding: 8px 12px;
                background-color: #cbd5e1;
                border-bottom: 2px solid #64748b;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
        """)
        
        # パス生成ボタン（トグルボタンに変更）
        self.generate_path_button = QPushButton("Generate Path")
        self.generate_path_button.setCheckable(True)  # トグルボタンに設定
        self.generate_path_button.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                border: none;
            }
            QPushButton:checked {
                background-color: #2563eb;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.generate_path_button.clicked.connect(self.handle_path_toggle)
        
        # 全削除ボタン
        clear_button = QPushButton("×")
        clear_button.setFixedSize(24, 24)
        clear_button.setToolTip("すべてのウェイポイントを削除")
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #ef4444;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #fecaca;
            }
        """)
        clear_button.clicked.connect(self.all_waypoints_delete_requested.emit)
        
        # パス生成ボタンと全削除ボタンの間にインポートボタンを追加
        import_button = QPushButton("Import")
        import_button.setToolTip("Import Waypoints from YAML")
        import_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
            }
        """)
        import_button.clicked.connect(self.handle_import_waypoints)
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(import_button)  # インポートボタンを追加
        header_layout.addStretch()
        header_layout.addWidget(self.generate_path_button)
        header_layout.addWidget(clear_button)
        
        # スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
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
        self.waypoint_list_layout.setSpacing(4)
        self.waypoint_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # スクロールエリアにウェイポイントリストを設定
        self.scroll_area.setWidget(self.waypoint_list)
        
        # 固定の高さを設定
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
                font-size: 13px;
                font-weight: 800;
                color: #000000;
                padding: 8px 12px;
                background-color: #cbd5e1;
                border-bottom: 2px solid #64748b;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
        """)
        
        content = QWidget()
        content.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        content_layout = QVBoxLayout(content)
        
        self.export_pgm_cb = QCheckBox("Export PGM with drawings")
        self.export_waypoints_cb = QCheckBox("Export Waypoints YAML")
        
        export_button = QPushButton("Export Selected")
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                min-width: 120px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        export_button.clicked.connect(self.handle_export)
        
        content_layout.addWidget(self.export_pgm_cb)
        content_layout.addWidget(self.export_waypoints_cb)
        content_layout.addWidget(export_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title_label)
        layout.addWidget(content)
        
        return widget

    def create_landmark_panel(self):
        """ランドマーク編集パネルを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)

        header_layout = QHBoxLayout()
        title_label = QLabel("Landmarks")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 800;
                color: #000000;
                padding: 8px 12px;
                background-color: #cbd5e1;
                border-bottom: 2px solid #64748b;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
        """)

        import_button = QPushButton("Import")
        import_button.setToolTip("Import Landmarks from JSON")
        import_button.clicked.connect(self.handle_import_landmarks)

        export_button = QPushButton("Export")
        export_button.setToolTip("Export Landmarks to JSON")
        export_button.clicked.connect(self.landmark_export_requested.emit)

        clear_button = QPushButton("×")
        clear_button.setFixedSize(24, 24)
        clear_button.setToolTip("すべてのランドマークを削除")
        clear_button.clicked.connect(self.all_landmarks_delete_requested.emit)

        header_layout.addWidget(title_label)
        header_layout.addWidget(import_button)
        header_layout.addWidget(export_button)
        header_layout.addStretch()
        header_layout.addWidget(clear_button)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(120)
        scroll_area.setMaximumHeight(240)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
        """)

        self.landmark_list = QWidget()
        self.landmark_list_layout = QVBoxLayout(self.landmark_list)
        self.landmark_list_layout.setSpacing(4)
        self.landmark_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.landmark_list)

        layout.addLayout(header_layout)
        layout.addWidget(scroll_area)
        return widget

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
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Import Landmarks JSON",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if file_name:
            self.landmark_import_requested.emit(file_name)

    def handle_export(self):
        """エクスポートボタンクリック時の処理"""
        export_pgm = self.export_pgm_cb.isChecked()
        export_waypoints = self.export_waypoints_cb.isChecked()
        if export_pgm or export_waypoints:
            self.export_requested.emit(export_pgm, export_waypoints)

    def start_auto_scroll(self):
        if not hasattr(self, 'scroll_timer'):
            self.scroll_timer = QTimer()
            self.scroll_timer.timeout.connect(self.auto_scroll)
            self.scroll_timer.start(50)

    def stop_auto_scroll(self):
        if hasattr(self, 'scroll_timer'):
            self.scroll_timer.stop()
            delattr(self, 'scroll_timer')
            self.scroll_region = None

    def auto_scroll(self):
        if not hasattr(self, 'scroll_region') or not hasattr(self, 'scroll_area'):
            return
        scroll_bar = self.scroll_area.verticalScrollBar()
        current = scroll_bar.value()
        cursor_pos = self.scroll_area.mapFromGlobal(QCursor.pos())
        viewport_height = self.scroll_area.height()
        margin = 50
        if self.scroll_region == 'up':
            distance = max(0, cursor_pos.y())
            speed_factor = 1.0 - (distance / margin)
        else:
            distance = max(0, viewport_height - cursor_pos.y())
            speed_factor = 1.0 - (distance / margin)
        speed_factor = max(0.0, min(1.0, speed_factor))
        base_speed, max_speed = 5, 30
        scroll_speed = int(base_speed + (max_speed - base_speed) * speed_factor)
        if self.scroll_region == 'up':
            scroll_bar.setValue(max(scroll_bar.minimum(), current - scroll_speed))
        elif self.scroll_region == 'down':
            scroll_bar.setValue(min(scroll_bar.maximum(), current + scroll_speed))
        if scroll_bar.value() in (scroll_bar.minimum(), scroll_bar.maximum()):
            self.stop_auto_scroll()

    def handle_path_toggle(self):
        self.generate_path_requested.emit()

    def add_waypoint_to_list(self, waypoint):
        if waypoint.number in self.waypoint_widgets:
            self.waypoint_widgets[waypoint.number].update_label(waypoint.display_name)
            return
        waypoint_item = WaypointListItem(waypoint)
        self.waypoint_widgets[waypoint.number] = waypoint_item
        waypoint_item.delete_clicked.connect(self.waypoint_delete_requested.emit)
        self.waypoint_list_layout.addWidget(waypoint_item)

    def remove_waypoint_from_list(self, number):
        if number == -1:
            self.clear_waypoint_list()
            return
        if number in self.waypoint_widgets:
            widget = self.waypoint_widgets.pop(number)
            self.waypoint_list_layout.removeWidget(widget)
            widget.deleteLater()

    def clear_waypoint_list(self):
        while self.waypoint_list_layout.count():
            item = self.waypoint_list_layout.takeAt(0)
            if widget := item.widget(): widget.deleteLater()
        self.waypoint_widgets.clear()

    def add_landmark_to_list(self, landmark):
        if landmark.number in self.landmark_widgets:
            self.landmark_widgets[landmark.number].update_label()
            return
        landmark_item = LandmarkListItem(landmark)
        self.landmark_widgets[landmark.number] = landmark_item
        landmark_item.delete_clicked.connect(self.landmark_delete_requested.emit)
        landmark_item.name_changed.connect(self.landmark_name_changed.emit)
        self.landmark_list_layout.addWidget(landmark_item)

    def remove_landmark_from_list(self, number):
        if number == -1:
            self.clear_landmark_list()
            return
        if number in self.landmark_widgets:
            widget = self.landmark_widgets.pop(number)
            self.landmark_list_layout.removeWidget(widget)
            widget.deleteLater()

    def clear_landmark_list(self):
        while self.landmark_list_layout.count():
            item = self.landmark_list_layout.takeAt(0)
            if widget := item.widget(): widget.deleteLater()
        self.landmark_widgets.clear()

    def update_layer_list(self, layers):
        for i in reversed(range(self.layer_list_layout.count())): 
            widget = self.layer_list_layout.itemAt(i).widget()
            if widget: widget.setParent(None); widget.deleteLater()
        for layer in layers:
            self.layer_list_layout.addWidget(LayerControl(layer, self))

    def handle_waypoint_reorder(self, source_number, target_number):
        self.waypoint_reorder_requested.emit(source_number, target_number)
