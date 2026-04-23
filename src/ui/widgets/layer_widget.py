from PySide6.QtWidgets import QWidget, QHBoxLayout, QCheckBox, QSlider, QDoubleSpinBox, QLabel
from PySide6.QtCore import Signal, Qt, QObject

class Layer(QObject):  
    """レイヤークラス"""
    changed = Signal()  # レイヤーの状態変更通知用シグナル
    
    def __init__(self, name, visible=True):
        super().__init__()
        self.name = name
        self.visible = visible
        self.pixmap = None
        self.opacity = 1.0
        
        # マップレイヤー用拡張
        self.offset_x = 0.0  # メートル単位
        self.offset_y = 0.0  # メートル単位
        self.resolution = 0.05
        self.origin_m = (0.0, 0.0)  # YAML由来の原点(m)
        self.file_path = ""
        self.is_map = False
        self.rotation = 0.0  # 角度（度単位）

    def set_visible(self, visible):
        if (self.visible != visible):
            self.visible = visible
            self.changed.emit()

    def set_opacity(self, opacity):
        new_opacity = max(0.0, min(1.0, opacity))
        if (self.opacity != new_opacity):
            self.opacity = new_opacity
            self.changed.emit()

class LayerControl(QWidget):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)  # ウィジェット間のスペースを設定
        
        self.setStyleSheet("""
            LayerControl {
                background-color: #ffffff;
                border-bottom: 1px solid #f1f5f9;
                padding: 4px;
            }
            LayerControl:hover {
                background-color: #f8fafc;
            }
        """)
        
        # チェックボックスの設定
        self.visibility_cb = QCheckBox(self.layer.name)
        self.visibility_cb.setStyleSheet("""
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
            QCheckBox {
                min-width: 120px;
                max-width: 120px;
                color: #000000;
                font-weight: 700;
            }
        """)
        self.visibility_cb.setChecked(self.layer.visible)
        self.visibility_cb.stateChanged.connect(self._on_visibility_changed)
        
        # 不透明度スライダーの設定
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(int(self.layer.opacity * 100))
        self.opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #e2e8f0;
                height: 4px;
                background: #f1f5f9;
                margin: 2px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #3b82f6;
                border: 1px solid #2563eb;
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }
        """)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        
        # レイアウトに追加
        layout.addWidget(self.visibility_cb)
        layout.addWidget(self.opacity_slider, stretch=1)  # スライダーを伸縮可能に設定

        # オフセット設定（マップレイヤーの場合のみ）
        if self.layer.is_map:
            self.offset_group = QWidget()
            group_layout = QHBoxLayout(self.offset_group)
            group_layout.setContentsMargins(0, 0, 0, 0)
            
            off_x_label = QLabel("Shift X (m):")
            off_x_label.setToolTip("Horizontal displacement in meters")
            group_layout.addWidget(off_x_label)
            
            self.off_x_spin = QDoubleSpinBox()
            self.off_x_spin.setRange(-1000, 1000)
            self.off_x_spin.setSingleStep(0.1)  # 10cm step for intuitive control
            self.off_x_spin.setDecimals(3)
            self.off_x_spin.setValue(self.layer.offset_x)
            self.off_x_spin.setToolTip("Fine-tune the map's X position")
            self.off_x_spin.valueChanged.connect(self._on_off_x_changed)
            group_layout.addWidget(self.off_x_spin)
            
            off_y_label = QLabel("Shift Y (m):")
            off_y_label.setToolTip("Vertical displacement in meters")
            group_layout.addWidget(off_y_label)
            
            self.off_y_spin = QDoubleSpinBox()
            self.off_y_spin.setRange(-1000, 1000)
            self.off_y_spin.setSingleStep(0.1)
            self.off_y_spin.setDecimals(3)
            self.off_y_spin.setValue(self.layer.offset_y)
            self.off_y_spin.setToolTip("Fine-tune the map's Y position")
            self.off_y_spin.valueChanged.connect(self._on_off_y_changed)
            group_layout.addWidget(self.off_y_spin)
            
            rot_label = QLabel("Rot (deg):")
            rot_label.setToolTip("Rotation in degrees")
            group_layout.addWidget(rot_label)
            
            self.rot_spin = QDoubleSpinBox()
            self.rot_spin.setRange(-360, 360)
            self.rot_spin.setSingleStep(0.5)
            self.rot_spin.setDecimals(1)
            self.rot_spin.setValue(self.layer.rotation)
            self.rot_spin.valueChanged.connect(self._on_rot_changed)
            group_layout.addWidget(self.rot_spin)
            
            layout.addWidget(self.offset_group)

    def _on_rot_changed(self, value):
        self.layer.rotation = value
        self.layer.changed.emit()

    def _on_off_x_changed(self, value):
        self.layer.offset_x = value
        self.layer.changed.emit()

    def _on_off_y_changed(self, value):
        self.layer.offset_y = value
        self.layer.changed.emit()

    def _on_visibility_changed(self, state):
        """表示/非表示の切り替え"""
        self.layer.set_visible(state == Qt.CheckState.Checked.value)
    
    def _on_opacity_changed(self, value):
        """不透明度の変更"""
        self.layer.set_opacity(value / 100.0)
