from collections import OrderedDict

# Waypointの追加属性とデフォルト値
WAYPOINT_ATTRIBUTE_DEFAULTS = OrderedDict([
    ('rotate', 0.0),
    ('stop', False),
    ('wait_time', 0.0),
    ('change_map', ''),
    ('threshold', -1.0),
    ('person_area', False),
])


def count_configured_waypoint_actions(attributes):
    """Count attributes whose values differ from the action defaults."""
    configured = 0
    for key, value in attributes.items():
        if key not in WAYPOINT_ATTRIBUTE_DEFAULTS:
            if value is not None and value != '':
                configured += 1
            continue

        default = WAYPOINT_ATTRIBUTE_DEFAULTS[key]
        try:
            if isinstance(default, bool):
                normalized = (
                    value.lower() in ('true', '1', 'yes', 'on')
                    if isinstance(value, str)
                    else bool(value)
                )
            elif isinstance(default, float):
                normalized = float(value)
            elif isinstance(default, int):
                normalized = int(value)
            else:
                normalized = str(value)
        except (TypeError, ValueError):
            normalized = value

        if normalized != default:
            configured += 1

    return configured

# Waypointのエクスポート/インポートフォーマット定義
WAYPOINT_FORMAT = {
    'version': '1.0',
    'format': {
        'number': 'int',      # ウェイポイントの番号
        'x': 'float',         # X座標 (メートル)
        'y': 'float',         # Y座標 (メートル) 
        'angle_radians': 'float',  # 角度 (ラジアン)
        'rotate': 'float',      # 到着後の追加回転量
        'stop': 'bool',         # 停止フラグ
        'wait_time': 'float',   # 待機時間 (秒)
        'change_map': 'string', # 切り替え先の地図名
        'threshold': 'float',   # 個別の到着判定距離
        'person_area': 'bool',  # 人物探索エリア
        'manual': 'bool'        # 手動記録ステータス（手動配置した場合のみtrue）
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
