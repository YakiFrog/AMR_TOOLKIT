import numpy as np

class MapProcessor:
    """地図データの処理を行うクラス"""
    
    @staticmethod
    def validate_pgm(data):
        """PGMファイルの検証"""
        if not isinstance(data, np.ndarray):
            raise ValueError("Invalid data format")
        if len(data.shape) != 2:
            raise ValueError("Data must be 2-dimensional")
        return True

    @staticmethod
    def convert_coordinates(pixel_x, pixel_y, origin_x, origin_y, resolution):
        """ピクセル座標からメートル座標への変換"""
        rel_x = (pixel_x - origin_x) * resolution
        rel_y = (origin_y - pixel_y) * resolution  # y軸は反転
        return rel_x, rel_y

    @staticmethod
    def convert_to_grayscale(image):
        """画像をグレースケールに変換"""
        if len(image.shape) > 2:
            return np.mean(image, axis=2).astype(np.uint8)
        return image
