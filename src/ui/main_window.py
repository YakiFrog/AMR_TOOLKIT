from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QSplitter,
                            QFileDialog)
from PySide6.QtCore import Qt
from .panels.menu_panel import MenuPanel
from .panels.right_panel import RightPanel
from .panels.map_panel import ImageViewer
import yaml
import os
import numpy as np

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """UIの初期化"""
        self.setWindowTitle("Map and Waypoint Editor")
        self.setGeometry(100, 100, 1200, 1000)
        self.setStyleSheet("font-size: 11px;")

        # メインウィジェット
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左パネル
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(5)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # コンポーネントの初期化
        self.menu_panel = MenuPanel()
        self.image_viewer = ImageViewer()
        self.analysis_panel = RightPanel()

        # レイアウトの構築
        left_layout.addWidget(self.menu_panel)
        left_layout.addWidget(self.image_viewer)
        left_widget.setLayout(left_layout)

        # スプリッターの設定
        splitter.addWidget(left_widget)
        splitter.addWidget(self.analysis_panel)
        splitter.setSizes([600, 400])

        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def connect_signals(self):
        """シグナル/スロットの接続"""
        # ファイル操作
        self.menu_panel.file_selected.connect(self.load_pgm_file)
        self.menu_panel.yaml_selected.connect(self.load_yaml_file)
        self.menu_panel.zoom_value_changed.connect(self.handle_zoom_value_changed)
        
        # ビューア制御
        self.image_viewer.scale_changed.connect(self.handle_scale_changed)
        self.image_viewer.layer_changed.connect(self.update_layer_panel)
        self.menu_panel.grid_button.clicked.connect(self.image_viewer.toggle_grid)
        
        # ウェイポイント操作
        self.image_viewer.waypoint_added.connect(self.analysis_panel.add_waypoint_to_list)
        self.image_viewer.waypoint_removed.connect(self.analysis_panel.remove_waypoint_from_list)
        self.image_viewer.waypoint_edited.connect(self.analysis_panel.add_waypoint_to_list)
        
        # 右パネル操作
        self.analysis_panel.waypoint_delete_requested.connect(self.image_viewer.remove_waypoint)
        self.analysis_panel.all_waypoints_delete_requested.connect(self.image_viewer.remove_all_waypoints)
        self.analysis_panel.waypoint_reorder_requested.connect(self.image_viewer.reorder_waypoints)
        self.analysis_panel.generate_path_requested.connect(self.image_viewer.generate_path)
        self.analysis_panel.export_requested.connect(self.handle_export)

    # ファイル操作メソッド
    def load_pgm_file(self, file_path):
        """PGMファイルの読み込み"""
        try:
            with open(file_path, 'rb') as f:
                magic = f.readline().decode('ascii').strip()
                if magic != 'P5':
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

    def load_yaml_file(self, file_path):
        """YAMLファイルの読み込み"""
        try:
            with open(file_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
            
            yaml_dir = os.path.dirname(file_path)
            
            if 'image' in yaml_data:
                pgm_filename = yaml_data['image']
                pgm_path = os.path.join(yaml_dir, pgm_filename) if not os.path.isabs(pgm_filename) else pgm_filename
                
                if os.path.exists(pgm_path):
                    self.menu_panel.file_name_label.setText(os.path.basename(pgm_path))
                    self.load_pgm_file(pgm_path)
            
            self.image_viewer.load_yaml_file(file_path)
            
        except Exception as e:
            print(f"Error loading YAML file: {str(e)}")

    # ビューア制御メソッド
    def handle_zoom_value_changed(self, value):
        """ズーム値の変更処理"""
        scale_factor = value / 50.0
        self.image_viewer.scale_factor = scale_factor
        self.image_viewer.update_display()

    def handle_scale_changed(self, scale_factor):
        """スケール変更の処理"""
        slider_value = int(scale_factor * 50)
        self.menu_panel.zoom_slider.blockSignals(True)
        self.menu_panel.zoom_slider.setValue(slider_value)
        self.menu_panel.zoom_slider.blockSignals(False)
        zoom_percent = int(scale_factor * 100)
        self.menu_panel.zoom_label.setText(f"{zoom_percent}%")

    def update_layer_panel(self):
        """レイヤーパネルの更新"""
        self.analysis_panel.update_layer_list(self.image_viewer.layers)

    def handle_export(self, export_pgm, export_waypoints):
        """エクスポート処理"""
        if export_pgm:
            self.export_pgm_with_drawings()
        if export_waypoints:
            self.export_waypoints_yaml()

    def export_pgm_with_drawings(self):
        """描画込みのPGMファイルをエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export PGM with drawings",
            "",
            "PGM Files (*.pgm);;All Files (*)"
        )
        if file_name:
            pixmap = self.image_viewer.get_combined_pixmap()
            if pixmap:
                image = pixmap.toImage()
                gray_image = image.convertToFormat(QImage.Format.Format_Grayscale8)
                gray_image.save(file_name, "PGM")

    def export_waypoints_yaml(self):
        """ウェイポイントをYAMLファイルとしてエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Waypoints YAML",
            "",
            "YAML Files (*.yaml);;All Files (*)"
        )
        if file_name:
            waypoints_data = []
            for wp in self.image_viewer.waypoints:
                angle_degrees = float(wp.angle * 180 / np.pi)
                waypoints_data.append({
                    'number': wp.number,
                    'x': float(wp.x),
                    'y': float(wp.y),
                    'angle_degrees': angle_degrees,
                    'angle_radians': float(wp.angle)
                })
            
            data = {'waypoints': waypoints_data}
            try:
                with open(file_name, 'w') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            except Exception as e:
                print(f"Error saving waypoints YAML: {str(e)}")