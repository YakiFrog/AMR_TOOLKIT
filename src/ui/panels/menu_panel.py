from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QMenuBar, QMenu, QSlider, QFileDialog)
from PySide6.QtCore import Qt, Signal
import os

class MenuPanel(QWidget):
    """メニューパネル"""
    file_selected = Signal(str)
    zoom_value_changed = Signal(int)
    yaml_selected = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #e8e8e8;")
        self.setFixedHeight(120)

        # メニューバーの設定
        menu_bar = QMenuBar()
        file_menu = QMenu("File", self)
        menu_bar.addMenu(file_menu)

        # ファイル選択部分の設定
        file_layout = QHBoxLayout()
        self.select_button = QPushButton("Select PGM File")
        self.yaml_button = QPushButton("Select YAML File")
        self.file_name_label = QLabel("No file selected")
        
        # ボタンをレイアウトに追加
        file_layout.addWidget(self.select_button)
        file_layout.addWidget(self.yaml_button)
        file_layout.addWidget(self.file_name_label, stretch=1)

        # ファイル選択ボタンのシグナル接続
        self.select_button.clicked.connect(self.open_file_dialog)
        self.yaml_button.clicked.connect(self.open_yaml_dialog)

        # レイアウトの構築
        layout.addWidget(menu_bar)
        layout.addLayout(file_layout)

        # ズームコントロールの設定
        zoom_widget = self.create_zoom_controls()
        layout.addWidget(zoom_widget)

        # グリッドボタンの設定
        self.grid_button = QPushButton("Toggle Grid")
        self.grid_button.setCheckable(True)
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
        file_layout.addWidget(self.grid_button)
        
        self.setLayout(layout)

    def create_zoom_controls(self):
        """ズームコントロールの作成"""
        zoom_widget = QWidget()
        zoom_layout = QHBoxLayout()
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(1, 100)
        self.zoom_slider.setValue(50)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(50)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        def update_zoom(value):
            zoom_percent = int((value / 50.0) * 100)
            self.zoom_label.setText(f"{zoom_percent}%")
            self.zoom_value_changed.emit(value)
        
        self.zoom_slider.valueChanged.connect(update_zoom)
        
        reset_button = QPushButton("Reset Zoom")
        reset_button.clicked.connect(lambda: self.zoom_slider.setValue(50))
        
        zoom_layout.addWidget(self.zoom_slider, stretch=1)
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(reset_button)
        zoom_widget.setLayout(zoom_layout)
        return zoom_widget

    def open_file_dialog(self):
        """PGMファイル選択ダイアログを開く"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open PGM File",
            "",
            "PGM Files (*.pgm);;All Files (*)"
        )
        if file_name:
            self.file_name_label.setText(os.path.basename(file_name))
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
