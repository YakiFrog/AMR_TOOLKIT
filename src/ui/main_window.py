import sys
import os
import numpy as np
import yaml
import json
from collections import OrderedDict

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QSplitter, 
                               QMessageBox, QFileDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

from ..core.constants import COMMON_STYLES
from ..utils.format_manager import format_manager
from .panels.menu_panel import MenuPanel
from .panels.map_panel import ImageViewer
from .panels.right_panel import RightPanel

class MainWindow(QMainWindow):
    """メインウィンドウ
    アプリケーションの主要なUIと機能を統合"""
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet(COMMON_STYLES)
        self.setWindowTitle("Map and Waypoint Editor")
        self.setGeometry(100, 100, 1200, 1000)
        
        # メインウィジェットとレイアウト
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左側パネル
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(5)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # メニューパネル
        self.menu_panel = MenuPanel()
        
        # 画像ビューア
        self.image_viewer = ImageViewer()
        
        # シグナルの接続
        self.menu_panel.file_selected.connect(self.load_pgm_file)
        self.menu_panel.zoom_value_changed.connect(self.handle_zoom_value_changed)
        self.image_viewer.scale_changed.connect(self.handle_scale_changed)
        self.menu_panel.grid_button.clicked.connect(self.image_viewer.toggle_grid)
        self.menu_panel.yaml_selected.connect(self.load_yaml_file)
        self.menu_panel.undo_requested.connect(self.image_viewer.undo)
        self.menu_panel.redo_requested.connect(self.image_viewer.redo)
        self.image_viewer.history_changed.connect(self.update_history_buttons)

        # 左側レイアウトの構成
        left_layout.addWidget(self.menu_panel)
        left_layout.addWidget(self.image_viewer)
        left_widget.setLayout(left_layout)
        
        # 右側パネル
        self.right_panel = RightPanel()
        
        # スプリッタの設定
        splitter.addWidget(left_widget)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([600, 400])
        
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 相互接続
        self.image_viewer.layer_changed.connect(self.update_layer_panel)
        self.update_layer_panel()
        self.image_viewer.waypoint_added.connect(self.right_panel.add_waypoint_to_list)
        self.image_viewer.waypoint_removed.connect(self.right_panel.remove_waypoint_from_list)
        self.right_panel.waypoint_delete_requested.connect(self.image_viewer.remove_waypoint)
        self.right_panel.all_waypoints_delete_requested.connect(self.image_viewer.remove_all_waypoints)
        self.right_panel.waypoint_reorder_requested.connect(self.image_viewer.reorder_waypoints)
        self.right_panel.generate_path_requested.connect(self.image_viewer.generate_path)
        self.image_viewer.waypoint_edited.connect(self.right_panel.add_waypoint_to_list)
        self.image_viewer.landmark_added.connect(self.right_panel.add_landmark_to_list)
        self.image_viewer.landmark_edited.connect(self.right_panel.add_landmark_to_list)
        self.image_viewer.landmark_removed.connect(self.right_panel.remove_landmark_from_list)
        self.right_panel.landmark_delete_requested.connect(self.image_viewer.remove_landmark)
        self.right_panel.all_landmarks_delete_requested.connect(self.image_viewer.remove_all_landmarks)
        self.right_panel.landmark_name_changed.connect(self.handle_landmark_name_changed)
        self.right_panel.landmark_import_requested.connect(self.import_landmarks_json)
        self.right_panel.landmark_export_requested.connect(self.export_landmarks_json)
        self.right_panel.export_requested.connect(self.handle_export)
        self.right_panel.waypoint_import_requested.connect(self.import_waypoints_yaml)
        self.right_panel.layer_add_requested.connect(self.handle_layer_add_requested)

    def update_layer_panel(self):
        """レイヤーパネルの表示を更新"""
        if hasattr(self, 'right_panel') and hasattr(self, 'image_viewer'):
            self.right_panel.update_layer_list(self.image_viewer.all_layers)

    def load_pgm_file(self, file_path):
        """PGMファイルを読み込む (ImageViewerのマルチレイヤー機能を利用)"""
        try:
            # ImageViewer側でパレット読み込みやレイヤー追加を一括処理
            self.image_viewer.load_image(None, 0, 0, file_path=file_path)
            self.menu_panel.file_name_label.setText(os.path.basename(file_path))
            print(f"Requested image load: {file_path}")
        except Exception as e:
            print(f"Error requesting PGM load: {str(e)}")

    def handle_layer_add_requested(self):
        """右パネルの「＋」ボタンから新規レイヤーを追加"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Add Map Layer",
            "",
            "Map Files (*.pgm *.yaml *.png);;All Files (*)"
        )
        if file_name:
            if file_name.endswith('.yaml'):
                self.load_yaml_file(file_name)
            else:
                self.load_pgm_file(file_name)

    def handle_zoom_value_changed(self, value):
        """ズームスライダーの値変更を処理"""
        scale_factor = value / 50.0
        self.image_viewer.scale_factor = scale_factor
        self.image_viewer.update_display()

    def handle_scale_changed(self, scale_factor):
        """ImageViewerからのスケール変更通知を処理"""
        slider_value = int(scale_factor * 50)
        self.menu_panel.zoom_slider.blockSignals(True)
        self.menu_panel.zoom_slider.setValue(slider_value)
        self.menu_panel.zoom_slider.blockSignals(False)
        zoom_percent = int(scale_factor * 100)
        self.menu_panel.zoom_label.setText(f"{zoom_percent}%")

    def load_yaml_file(self, file_path):
        """YAMLファイルの読み込みとPGMファイルの自動読み込み"""
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
                else:
                    print(f"PGM file not found: {pgm_path}")
            self.image_viewer.load_yaml_file(file_path)
        except Exception as e:
            print(f"Error loading YAML file: {str(e)}")
            import traceback
            traceback.print_exc()

    def handle_export(self, export_pgm, export_waypoints):
        """エクスポート処理"""
        if export_pgm:
            self.export_pgm_with_drawings()
        if export_waypoints:
            self.export_waypoints_yaml()

    def export_pgm_with_drawings(self):
        """描画込みのPGMファイルをエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(self, "Export PGM with drawings", "", "PGM Files (*.pgm);;All Files (*)")
        if file_name:
            pixmap = self.image_viewer.get_combined_pixmap()
            if (pixmap):
                image = pixmap.toImage()
                gray_image = image.convertToFormat(QImage.Format.Format_Grayscale8)
                gray_image.save(file_name, "PGM")
                yaml_file_name = os.path.splitext(file_name)[0] + '.yaml'
                pgm_file_name = os.path.basename(file_name)
                yaml_data = {
                    'image': pgm_file_name,
                    'mode': 'trinary',
                    'resolution': self.image_viewer.resolution,
                    'origin': [0, 0, 0],
                    'negate': 0,
                    'occupied_thresh': 0.65,
                    'free_thresh': 0.25
                }
                if self.image_viewer.origin_point:
                    origin_x = -self.image_viewer.origin_point[0] * self.image_viewer.global_resolution
                    # 最初のマップレイヤーを基準にする
                    h = self.image_viewer.pgm_layers[0].pixmap.height() if self.image_viewer.pgm_layers else 0
                    origin_y = -(h - self.image_viewer.origin_point[1]) * self.image_viewer.global_resolution
                    yaml_data['origin'] = [origin_x, origin_y, 0]
                try:
                    with open(yaml_file_name, 'w') as f:
                        yaml.dump(yaml_data, f, default_flow_style=None)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Error saving YAML file: {str(e)}")

    def export_waypoints_yaml(self):
        """ウェイポイントをYAMLファイルとしてエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(self, "Export Waypoints YAML", "", "YAML Files (*.yaml);;All Files (*)")
        if file_name:
            def ordered_dict_representer(dumper, data):
                return dumper.represent_mapping('tag:yaml.org,2002:map', dict(data.items()))
            yaml.add_representer(OrderedDict, ordered_dict_representer)
            
            waypoints_data = []
            current_format = format_manager.get_format()
            
            for wp in self.image_viewer.waypoints:
                waypoint_data = {}
                for key in current_format['format'].keys():
                    value = self.get_waypoint_value(wp, key, current_format['format'][key])
                    if value is not None:
                        waypoint_data[key] = value
                waypoints_data.append(waypoint_data)
            
            data = {
                'format_version': current_format['version'],
                'waypoints': waypoints_data
            }
            
            try:
                with open(file_name, 'w') as f:
                    class CleanDumper(yaml.SafeDumper): pass
                    CleanDumper.add_representer(bool, lambda dumper, data: dumper.represent_bool(data))
                    def str_representer(dumper, data):
                        if data == '' or any(c in data for c in ':{}[]&*#?|-<>=!%@\\'):
                            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")
                        return dumper.represent_scalar('tag:yaml.org,2002:str', data)
                    CleanDumper.add_representer(str, str_representer)
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True, Dumper=CleanDumper)
            except Exception as e:
                print(f"Error saving waypoints YAML: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to save waypoints: {str(e)}")

    def import_waypoints_yaml(self, file_path):
        """Waypointの設定をYAMLファイルからインポート"""
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                ordered_data = OrderedDict()
                for key in data:
                    if key == 'waypoints': ordered_data[key] = [OrderedDict(wp) for wp in data[key]]
                    else: ordered_data[key] = data[key]
            current_format = format_manager.get_format()
            if 'format_version' in ordered_data and ordered_data['format_version'] != current_format['version']:
                response = QMessageBox.question(self, "Version Mismatch", f"File format version ({ordered_data['format_version']}) differs from current version ({current_format['version']}). Continue?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if response == QMessageBox.StandardButton.No: return
            self.image_viewer.import_waypoints_from_yaml(ordered_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error importing waypoints: {str(e)}")

    def export_landmarks_json(self):
        """ランドマークをJSONファイルとしてエクスポート"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Landmarks JSON",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not file_name:
            return
        if not file_name.lower().endswith(".json"):
            file_name += ".json"
        try:
            with open(file_name, "w", encoding="utf-8") as f:
                json.dump(self.image_viewer.export_landmarks_data(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save landmarks: {str(e)}")

    def import_landmarks_json(self, file_path):
        """ランドマークJSONをインポート"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.right_panel.clear_landmark_list()
            self.image_viewer.import_landmarks_from_json(data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error importing landmarks: {str(e)}")

    def handle_landmark_name_changed(self, number, name):
        landmark = next((lm for lm in self.image_viewer.landmarks if lm.number == number), None)
        if not landmark:
            return
        landmark.set_name(name)
        self.image_viewer.landmark_edited.emit(landmark)
        self.image_viewer.update_display()

    def update_history_buttons(self, can_undo, can_redo):
        """戻る/進むボタンの状態を更新"""
        self.menu_panel.update_undo_redo_actions(can_undo, can_redo)

    def get_waypoint_value(self, waypoint, key, type_info):
        """ウェイポイントから指定されたキーの値を取得し、適切な型に変換"""
        if key == 'number': return waypoint.number
        elif key == 'x': return round(float(waypoint.x), 3)
        elif key == 'y': return round(float(waypoint.y), 3)
        elif key == 'angle_radians': return round(float(waypoint.angle), 3) 
        else:
            value = waypoint.get_attribute(key, None)
            if value is not None:
                converted = self.convert_value(value, type_info)
                if (type_info in ('str', 'string')) and converted == '': return None
                return converted
        return None

    def convert_value(self, value, type_info):
        """値を指定された型に変換"""
        try:
            if type_info == 'int': return int(value)
            elif type_info == 'float': return float(value)
            elif type_info in ('str', 'string'): return str(value)
            elif type_info == 'bool':
                if isinstance(value, str): return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            return value
        except (ValueError, TypeError): return value
