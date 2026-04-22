from PySide6.QtWidgets import QWidget, QHBoxLayout, QCheckBox, QSlider
from PySide6.QtCore import Signal, Qt

class Layer(QWidget):  
    """レイヤークラス"""
    changed = Signal()  # レイヤーの状態変更通知用シグナル
    
    def __init__(self, name, visible=True):
        super().__init__()
        self.name = name
        self.visible = visible
        self.pixmap = None
        self.opacity = 1.0

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

    def _on_visibility_changed(self, state):
        """表示/非表示の切り替え"""
        self.layer.set_visible(state == Qt.CheckState.Checked.value)
    
    def _on_opacity_changed(self, value):
        """不透明度の変更"""
        self.layer.set_opacity(value / 100.0)
