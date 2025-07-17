import pandas as pd
import requests
import json
import math

def read_trajectory_data(csv_path):
    """
    从 CSV 文件中读取轨迹数据。
    """
    try:
        # 使用 pandas 读取 CSV 文件 [8, 10]
        df = pd.read_csv(csv_path)
        required_columns = ['driver_id', 'order_id', 'gps_time', 'longitude', 'latitude']
        if not all(col in df.columns for col in required_columns):
            raise ValueError("CSV 文件缺少必要的列: 'driver_id', 'order_id', 'gps_time', 'longitude', 'latitude'")
        return df
    except FileNotFoundError:
        print(f"错误: 文件未找到 at {csv_path}")
        return None
    except Exception as e:
        print(f"读取 CSV 文件时发生错误: {e}")
        return None


def osrm_map_matching(trajectory_df, osrm_url="http://localhost:5000"):
    """
    使用 OSRM 对单个轨迹数据块进行地图匹配。
    """
    if len(trajectory_df) < 2:
        return None

    trajectory_df = trajectory_df.sort_values(by='gps_time')
    # 格式化坐标点 [16]
    coords = ";".join([f"{lon},{lat}" for lon, lat in zip(trajectory_df['longitude'], trajectory_df['latitude'])])
    # 构建请求 URL [6]
    request_url = f"{osrm_url}/match/v1/driving/{coords}?overview=full&steps=true&geometries=geojson"

    try:
        # 发送 HTTP GET 请求 [1, 3]
        response = requests.get(request_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求 OSRM 服务时发生错误: {e}")
        return None
    except json.JSONDecodeError:
        print("错误: 无法解析 OSRM 服务的响应。")
        return None


def main():
    """
    主函数，执行读取、分块匹配，并将结果以每个点一行的格式保存到 CSV。
    """
    input_csv_path = 'filtered_orders.csv'
    output_csv_path = 'matched_points_for_qgis.csv'  # 新的输出文件名

    CHUNK_SIZE = 95



    trajectories = read_trajectory_data(input_csv_path)
    if trajectories is None:
        return

    orders = trajectories.groupby('order_id')

    # *** 新增：用于存储所有匹配点的行数据的列表 ***
    all_points_rows = []

    for order_id, trajectory_df in orders:
        print(f"--- 正在处理订单: {order_id} (共 {len(trajectory_df)} 个点) ---")

        all_matchings_for_order = []
        num_chunks = math.ceil(len(trajectory_df) / CHUNK_SIZE)

        for i in range(num_chunks):
            start_index = i * CHUNK_SIZE
            end_index = (i + 1) * CHUNK_SIZE
            chunk_df = trajectory_df.iloc[start_index:end_index]  # 使用 iloc 进行分块 [12]

            match_result = osrm_map_matching(chunk_df)

            if match_result and match_result.get('code') == 'Ok':
                all_matchings_for_order.extend(match_result.get('matchings', []))
            else:
                print(f"  块 {i + 1} 地图匹配失败。")

        # 4. *** 修改：分解几何路径并为每个点创建行 ***
        if all_matchings_for_order:
            # 首先，计算整个订单的聚合信息
            total_distance = sum(m.get('distance', 0) for m in all_matchings_for_order)
            total_duration = sum(m.get('duration', 0) for m in all_matchings_for_order)
            average_confidence = sum(m.get('confidence', 0) for m in all_matchings_for_order) / len(
                all_matchings_for_order)

            # 获取 driver_id (对于同一个订单，driver_id 应该是相同的)
            driver_id = trajectory_df['driver_id'].iloc[0]

            point_sequence = 0  # 用于标记点在路径中的顺序

            # 遍历每个匹配分段
            for matching in all_matchings_for_order:
                geometry = matching.get('geometry')
                if geometry and 'coordinates' in geometry:
                    # 遍历该分段几何路径中的每一个坐标点
                    for coord in geometry['coordinates']:
                        point_row = {
                            'order_id': order_id,
                            'driver_id': driver_id,
                            'matched_longitude': coord[0],
                            'matched_latitude': coord[1],
                            'point_sequence': point_sequence,
                            'total_order_distance_m': round(total_distance, 2),
                            'total_order_duration_s': round(total_duration, 2),
                            'order_avg_confidence': round(average_confidence, 4)
                        }
                        all_points_rows.append(point_row)
                        point_sequence += 1

            print(f"订单 {order_id} 匹配成功，生成了 {point_sequence} 个匹配点。")

        else:
            print(f"订单 {order_id} 未能成功进行地图匹配，将不会写入文件。")

        print("\n" + "=" * 40 + "\n")

    # 5. *** 修改：将所有点的数据保存到 CSV 文件 ***
    if all_points_rows:
        print(f"正在将 {len(all_points_rows)} 个匹配点保存到 {output_csv_path}...")
        results_df = pd.DataFrame(all_points_rows)
        results_df.to_csv(output_csv_path, index=False, encoding='utf-8')
        print("文件保存成功！")
    else:
        print("没有可供保存的匹配点。")


if __name__ == '__main__':
    main()