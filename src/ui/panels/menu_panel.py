from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QMenuBar, 
                               QMenu, QLabel, QPushButton, QSlider, QFileDialog)
from PySide6.QtCore import Qt, Signal

class MenuPanel(QWidget):
    """メニューパネル
    ファイル操作とズーム制御のUIを提供"""
    
    # シグナルの定義
    file_selected = Signal(str)  # ファイル選択時のシグナル
    zoom_value_changed = Signal(int)  # ズーム値変更時のシグナル
    yaml_selected = Signal(str)  # YAMLファイル選択用のシグナルを追加
    undo_requested = Signal()  # 戻るボタン用シグナル
    redo_requested = Signal()  # 進むボタン用シグナル
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """UIコンポーネントの初期化と配置"""
        layout = QVBoxLayout()
        self.setStyleSheet("""
            MenuPanel {
                background-color: #ffffff;
                border-bottom: 2px solid #94a3b8;
            }
        """)
        self.setFixedHeight(120)

        # メニューバー
        menu_bar = QMenuBar()
        file_menu = QMenu("File", self)
        edit_menu = QMenu("Edit", self)
        
        # 戻る/進むボタンの追加
        # button_layout = QHBoxLayout()
        
        self.undo_button = QPushButton("Undo")
        self.undo_button.setEnabled(False)  # 初期状態は無効
        self.undo_button.clicked.connect(self.undo_requested.emit)
        self.undo_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 2px solid #64748b;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 80px;
                color: #000000;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #e2e8f0;
                color: #94a3b8;
                border-color: #cbd5e1;
            }
        """)
        
        self.redo_button = QPushButton("Redo ↪")
        self.redo_button.setEnabled(False)  # 初期状態は無効
        self.redo_button.clicked.connect(self.redo_requested.emit)
        self.redo_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 2px solid #64748b;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 80px;
                color: #000000;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #e2e8f0;
                color: #94a3b8;
                border-color: #cbd5e1;
            }
        """)
        
        # ファイルメニューのアクションを作成
        open_action = file_menu.addAction("Open PGM")
        save_action = file_menu.addAction("Save PGM")
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
        self.select_button = QPushButton("Add Map (PGM)")
        self.select_button.setToolTip("PGM地図をレイヤーとして追加します。最初の地図が基準原点となります。")
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
                background-color: #ffffff;
                border: 2px solid #64748b;
                border-radius: 4px;
                font-weight: 700;
            }
            QPushButton:checked {
                background-color: #2563eb;
                color: white;
                border-color: #1e3a8a;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
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
        self.zoom_slider.setRange(1, 150)  # 50 = 100%, 150 = 300%
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

    def update_undo_redo_actions(self, can_undo, can_redo):
        """Undo/Redoボタンの状態を更新"""
        self.undo_button.setEnabled(can_undo)
        self.redo_button.setEnabled(can_redo)
