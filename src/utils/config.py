class Config:
    """アプリケーション設定"""
    
    # Window settings
    WINDOW_TITLE = "Map and Waypoint Editor"
    WINDOW_GEOMETRY = (100, 100, 1200, 1000)
    
    # Default values
    DEFAULT_RESOLUTION = 0.05
    DEFAULT_PEN_SIZE = 2
    DEFAULT_ERASER_SIZE = 10
    DEFAULT_WAYPOINT_SIZE = 15
    DEFAULT_GRID_SIZE = 50
    
    # File formats
    SUPPORTED_IMAGE_FORMATS = ["PGM Files (*.pgm)", "All Files (*)"]
    SUPPORTED_YAML_FORMATS = ["YAML Files (*.yaml *.yml)", "All Files (*)"]
    
    # Style settings
    STYLE_SHEET = """
        QWidget {
            font-size: 11px;
        }
    """
