from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget, QScrollArea, QHBoxLayout, QPushButton, QLabel, QLineEdit
from ...utils.format_manager import format_manager

class AttributeDialog(QDialog):
    def __init__(self, waypoint, format_data, parent=None):
        super().__init__(parent)
        self.waypoint = waypoint
        self.format_data = format_data
        self.setup_ui()
        self.parent_viewer = None
        
        # 親ウィンドウを遡って ImageViewer を探す
        # Note: ImageViewer will be defined in panels.map_panel
        from ..panels.map_panel import ImageViewer
        current_parent = parent
        while current_parent:
            if isinstance(current_parent, ImageViewer):
                self.parent_viewer = current_parent
                break
            current_parent = current_parent.parent()
        
    def setup_ui(self):
        self.setWindowTitle("Add Actions")
        layout = QVBoxLayout(self)
        
        # 属性リスト
        self.attribute_list = QWidget()
        self.attribute_layout = QVBoxLayout(self.attribute_list)
        
        # フォーマットから利用可能な属性を取得
        available_attrs = [key for key in self.format_data['format'].keys()
                         if key not in ['number', 'x', 'y', 'angle_degrees', 'angle_radians']]
        
        # 既存の属性を表示
        for key in available_attrs:
            self.add_attribute_row(key, self.waypoint.get_attribute(key, ""))
        
        scroll = QScrollArea()
        scroll.setWidget(self.attribute_list)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 2px solid #94a3b8; border-radius: 6px; }")
        layout.addWidget(scroll)
        
        # ボタン
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
    
    def add_attribute_row(self, key, value):
        """属性入力行を追加"""
        row = QHBoxLayout()
        
        # キーのラベル
        key_label = QLabel(key)
        key_label.setMinimumWidth(100)
        
        # 値の入力フィールド
        value_edit = QLineEdit(str(value))
        value_edit.setProperty('key', key)  # キーを保存
        
        row.addWidget(key_label)
        row.addWidget(value_edit)
        self.attribute_layout.addLayout(row)
    
    def get_attributes(self):
        """ダイアログから属性を取得"""
        attributes = {}
        for i in range(self.attribute_layout.count()):
            layout_item = self.attribute_layout.itemAt(i)
            if layout_item and isinstance(layout_item, QHBoxLayout):
                value_edit = layout_item.itemAt(1).widget()
                if value_edit and value_edit.text():  # 空でない値のみ保存
                    key = value_edit.property('key')
                    attributes[key] = value_edit.text()
        return attributes

    def accept(self):
        """OKボタンが押された時の処理"""
        # 属性を更新
        self.waypoint.attributes = self.get_attributes()
        
        # ImageViewerの表示を更新
        if self.parent_viewer:
            self.parent_viewer.update_display()
        
        super().accept()
