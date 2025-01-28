import yaml
import math

def convert_waypoints(input_file: str, output_file: str):
    # 入力ファイルの読み込み
    with open(input_file, 'r') as f:
        data = yaml.safe_load(f)
    
    # 新形式のデータ構造を作成
    new_waypoints = []
    for wp in data['waypoints']:
        # 基本姿勢
        x = y = z = qx = qy = 0.0
        x = wp['x']
        y = wp['y']
        # ヨー角からクォータニオンに変換
        yaw = wp['angle_radians']
        qz = wp['angle_radians']
        qw = math.sqrt(1 - qz**2)
        
        # 新形式のウェイポイントを追加
        new_waypoints.append([x, y, z, qx, qy, qz, qw])
    
    # 新形式で出力
    output_data = {'points': new_waypoints}
    
    with open(output_file, 'w') as f:
        yaml.dump(output_data, f, default_flow_style=False)

if __name__ == '__main__':
    convert_waypoints('map/sample_127_waypoint.yaml', 'output_waypoints.yaml')