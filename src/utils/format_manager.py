from collections import OrderedDict

# Waypointのエクスポート/インポートフォーマット定義
WAYPOINT_FORMAT = {
    'version': '1.0',
    'format': {
        'number': 'int',      # ウェイポイントの番号
        'x': 'float',         # X座標 (メートル)
        'y': 'float',         # Y座標 (メートル) 
        'angle_radians': 'float',  # 角度 (ラジアン)
        'stop': 'bool',        # 停止フラグ
        'change_map': 'string'  # マップ変更フラグ
    }
}

# OrderedDictへの変換
WAYPOINT_FORMAT = OrderedDict([
    ('version', WAYPOINT_FORMAT['version']),
    ('format', OrderedDict(WAYPOINT_FORMAT['format']))
])

class FormatManager:
    def __init__(self):
        self._format = WAYPOINT_FORMAT
        self._observers = []

    def get_format(self):
        return self._format

    def set_format(self, new_format):
        # 辞書をOrderedDictに変換
        if isinstance(new_format, dict):
            ordered_format = OrderedDict()
            for key in new_format:
                if key == 'format' and isinstance(new_format[key], dict):
                    ordered_format[key] = OrderedDict(new_format[key])
                else:
                    ordered_format[key] = new_format[key]
            self._format = ordered_format
        else:
            self._format = new_format
        self._notify_observers()

    def add_observer(self, observer):
        self._observers.append(observer)

    def _notify_observers(self):
        for observer in self._observers:
            observer(self._format)

# FormatManagerのグローバルインスタンス
format_manager = FormatManager()
