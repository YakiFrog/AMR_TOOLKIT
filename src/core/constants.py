# 共通のスタイル定義 (High-Contrast Premium Light Mode)
COMMON_STYLES = """
    QMainWindow {
        background-color: #e2e8f0;
    }
    
    QWidget {
        font-family: 'Inter', 'Segoe UI', 'Roboto', sans-serif;
        font-size: 11px;
        color: #000000;
    }
    
    QPushButton {
        background-color: #ffffff;
        border: 2px solid #94a3b8;
        border-radius: 6px;
        padding: 6px 12px;
        color: #000000;
        font-weight: 700;
    }
    
    QPushButton:hover {
        background-color: #f1f5f9;
        border-color: #3b82f6;
    }
    
    QPushButton:pressed {
        background-color: #cbd5e1;
    }
    
    QPushButton:checked {
        background-color: #2563eb;
        color: white;
        border-color: #1e3a8a;
    }
    
    QLabel {
        color: #000000;
        font-weight: 500;
    }
    
    QScrollArea {
        border: 2px solid #94a3b8;
        border-radius: 8px;
        background-color: #ffffff;
    }
    
    QScrollBar:vertical {
        border: 1px solid #cbd5e1;
        background: #f1f5f9;
        width: 10px;
        margin: 0;
    }
    
    QScrollBar::handle:vertical {
        background: #64748b;
        min-height: 20px;
        border-radius: 5px;
    }
    
    QScrollBar::handle:vertical:hover {
        background: #475569;
    }
    
    QCheckBox {
        spacing: 8px;
        font-weight: 600;
    }
    
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 2px solid #64748b;
        border-radius: 4px;
        background: white;
    }
    
    QCheckBox::indicator:checked {
        background-color: #2563eb;
        border-color: #1e3a8a;
    }
    
    QToolTip {
        background-color: #0f172a;
        color: #ffffff;
        border: 1px solid white;
        border-radius: 4px;
        padding: 6px;
        font-size: 12px;
    }
    
    QSlider::groove:horizontal {
        border: 1px solid #94a3b8;
        height: 6px;
        background: #f1f5f9;
        margin: 2px 0;
        border-radius: 3px;
    }
    
    QSlider::handle:horizontal {
        background: #3b82f6;
        border: 2px solid #1e40af;
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }
    
    QMenuBar {
        background-color: #ffffff;
        border-bottom: 1px solid #cbd5e1;
        color: #000000;
        font-weight: 700;
        padding: 2px;
    }
    
    QMenuBar::item {
        background: transparent;
        padding: 4px 10px;
        border-radius: 4px;
    }
    
    QMenuBar::item:selected {
        background: #f1f5f9;
        color: #2563eb;
    }
    
    QMenu {
        background-color: #ffffff;
        border: 2px solid #94a3b8;
        border-radius: 6px;
        padding: 4px;
    }
    
    QMenu::item {
        padding: 6px 24px;
        color: #000000;
        border-radius: 4px;
        font-weight: 600;
    }
    
    QMenu::item:selected {
        background-color: #2563eb;
        color: #ffffff;
    }
    
    QMenu::separator {
        height: 2px;
        background: #cbd5e1;
        margin: 4px 0;
    }
"""

WAYPOINT_SETTINGS = {
    'BASE_SIZE': 10,           
    'ARROW_LENGTH_MULT': 2.2,  
    'ARROW_WIDTH_MULT': 0.7,   
    'FONT_SIZE_MAIN_MULT': 1.4,      
    'FONT_SIZE_ATTR_MULT': 0.7,      
    'EDIT_SIZE_MULT': 1.2,     
}

# 共通のレイアウト設定
LAYOUT_MARGINS = 12
WIDGET_SPACING = 10
STANDARD_HEIGHT = 32

# ピンチジェスチャーの感度調整用定数
SCALE_SENSITIVITY = 0.2

# スケール関連の定数
MIN_SCALE = 0.02  
MAX_SCALE = 2.0   
DEFAULT_SCALE = 1.0  

# カラーパレット
PALETTE = {
    'BACKGROUND': '#e2e8f0',
    'SURFACE': '#ffffff',
    'PRIMARY': '#2563eb',
    'PRIMARY_HOVER': '#1d4ed8',
    'TEXT': '#000000',
    'TEXT_SECONDARY': '#1e293b',
    'BORDER': '#94a3b8',
    'DANGER': '#dc2626',
    'SUCCESS': '#059669',
}
