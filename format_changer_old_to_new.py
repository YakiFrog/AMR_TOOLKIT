import yaml
import math

def quaternion_to_euler(qz, qw):
    """四元数からヨー角（ラジアン）に変換"""
    return 2 * math.atan2(qz, qw)

def convert_waypoints(input_file: str, output_file: str):
    # 入力ファイルの読み込み
    with open(input_file, 'r') as f:
        data = yaml.safe_load(f)
    
    # 新形式のデータ構造を作成
    new_waypoints = []
    for i, point in enumerate(data['points'], 1):
        # 位置とクォータニオン情報を取得
        x, y, _, _, _, qz, qw = point
        
        # ヨー角を計算
        angle_radians = qz
        
        # 新フォーマットのウェイポイントを作成
        waypoint = {
            'number': i,
            'x': x,
            'y': y,
            'angle_radians': angle_radians
        }
        new_waypoints.append(waypoint)
    
    # 新形式で出力
    output_data = {
        'format_version': '1.0',
        'waypoints': new_waypoints
    }
    
    with open(output_file, 'w') as f:
        yaml.dump(output_data, f, default_flow_style=False)

if __name__ == '__main__':
    convert_waypoints('map/sotsuken_present/1515_waypoint.yaml', 'map/sotsuken_present/converted_waypoint.yaml')