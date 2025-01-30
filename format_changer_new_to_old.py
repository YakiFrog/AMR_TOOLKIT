import yaml
import math

def yaw_to_quaternion(yaw):
    """ヨー角からクォータニオンに変換する関数"""
    half_yaw = yaw * 0.5
    return [
        0.0,  # x
        0.0,  # y
        math.sin(half_yaw),  # z
        math.cos(half_yaw)   # w
    ]

def convert_waypoints(input_file: str, output_file: str):
    try:
        # 入力ファイルの読み込み
        with open(input_file, 'r') as f:
            data = yaml.safe_load(f)
        
        # 新形式のデータ構造を作成
        new_waypoints = []
        for wp in data['waypoints']:
            # 基本位置
            x = wp['x']
            y = wp['y']
            z = 0.0
            
            # ヨー角からクォータニオンに変換
            quat = yaw_to_quaternion(wp['angle_radians'])
            
            # 新形式のウェイポイントを追加
            new_waypoints.append([x, y, z, quat[0], quat[1], quat[2], quat[3]])
        
        # 新形式で出力
        output_data = {'points': new_waypoints}
        
        with open(output_file, 'w') as f:
            yaml.dump(output_data, f, default_flow_style=False)
            
        print(f"Successfully converted {input_file} to {output_file}")
            
    except Exception as e:
        print(f"Error converting waypoints: {str(e)}")

if __name__ == '__main__':
    convert_waypoints('/home/sirius24/AMR_TOOLKIT/map/sotsuken_video/waypoints.yaml', 
                     '/home/sirius24/AMR_TOOLKIT/map/sotsuken_video/waypoints_old.yaml')