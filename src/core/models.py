import numpy as np
from enum import Enum

class DrawingMode(Enum):
    """描画モードを定義"""
    NONE = 0
    PEN = 1
    ERASER = 2
    WAYPOINT = 3
    LANDMARK = 4

class Waypoint:
    """ウェイポイントを管理するクラス"""
    counter = 0
    
    @classmethod
    def reset_counter(cls):
        """カウンターをリセット"""
        cls.counter = 0
    
    def __init__(self, pixel_x, pixel_y, angle=0, name=None):
        Waypoint.counter += 1
        self.number = Waypoint.counter
        self.pixel_x = pixel_x
        self.pixel_y = pixel_y
        self.x = 0
        self.y = 0
        self.angle = angle
        self.name = name if name else f"Waypoint {self.number}"
        self.resolution = 0.05  # 解像度を保存
        self.update_display_name()
        self.attributes = {}  # 属性を保存するディクショナリを追加

    def set_angle(self, angle):
        """角度を設定し、表示名を更新"""
        self.angle = angle
        self.update_display_name()

    def update_display_name(self):
        """表示名を更新"""
        degrees = int(self.angle * 180 / np.pi)  # ラジアンを度に変換
        self.display_name = f"#{self.number:02d} ({self.x:.2f}, {self.y:.2f}) {degrees}°"

    def update_metric_coordinates(self, origin_x, origin_y, resolution):
        """ピクセル座標からメートル座標を計算"""
        # 原点情報を保存 (ピクセル単位の相対位置計算用)
        self._origin_x = origin_x
        self._origin_y = origin_y
        self.resolution = resolution
        
        # 原点からの相対位置をメートル単位に変換
        # 画像座標系(左上原点)から ROS座標系(原点基準、Y上、X右)への変換
        self.x = (self.pixel_x - origin_x) * self.resolution
        self.y = (origin_y - self.pixel_y) * self.resolution # Y軸を反転
        self.update_display_name()

    def renumber(self, new_number):
        """ウェイポイントの番号を変更"""
        self.number = new_number
        self.name = f"Waypoint {self.number}"
        self.update_display_name()

    def set_position(self, x, y):
        """ピクセル座標を更新"""
        self.pixel_x = x
        self.pixel_y = y
        if hasattr(self, '_origin_x') and hasattr(self, '_origin_y'):
            # 既存の原点情報がある場合は座標を更新
            self.update_metric_coordinates(self._origin_x, self._origin_y, self.resolution)

    def set_attribute(self, key, value):
        """属性を設定"""
        self.attributes[key] = value
    
    def get_attribute(self, key, default=None):
        """属性を取得"""
        return self.attributes.get(key, default)


class Landmark:
    """名前付きランドマークを管理するクラス"""
    counter = 0

    @classmethod
    def reset_counter(cls):
        cls.counter = 0

    def __init__(self, pixel_x, pixel_y, angle=0, name=None):
        Landmark.counter += 1
        self.number = Landmark.counter
        self.pixel_x = pixel_x
        self.pixel_y = pixel_y
        self.x = 0
        self.y = 0
        self.angle = angle
        self.name = name if name else f"Landmark {self.number}"
        self.aliases = []
        self.resolution = 0.05
        self.update_display_name()

    def set_angle(self, angle):
        self.angle = angle
        self.update_display_name()

    def set_name(self, name):
        cleaned = str(name).strip()
        if cleaned:
            self.name = cleaned
        self.update_display_name()

    def update_display_name(self):
        degrees = int(self.angle * 180 / np.pi)
        self.display_name = f"{self.name} ({self.x:.2f}, {self.y:.2f}) {degrees}°"

    def update_metric_coordinates(self, origin_x, origin_y, resolution):
        self._origin_x = origin_x
        self._origin_y = origin_y
        self.resolution = resolution
        self.x = (self.pixel_x - origin_x) * self.resolution
        self.y = (origin_y - self.pixel_y) * self.resolution
        self.update_display_name()

    def set_position(self, x, y):
        self.pixel_x = x
        self.pixel_y = y
        if hasattr(self, '_origin_x') and hasattr(self, '_origin_y'):
            self.update_metric_coordinates(self._origin_x, self._origin_y, self.resolution)
