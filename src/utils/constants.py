from enum import Enum

# Common styles
COMMON_STYLES = """
    QWidget {
        font-size: 11px;
    }
"""

# Layout settings
LAYOUT_MARGINS = 8
WIDGET_SPACING = 5
STANDARD_HEIGHT = 25

# Scale constants
MIN_SCALE = 0.02
MAX_SCALE = 2.0
DEFAULT_SCALE = 1.0

class DrawingMode(Enum):
    NONE = 0
    PEN = 1
    ERASER = 2
    WAYPOINT = 3
