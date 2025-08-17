import pandas as pd
import os

def find_traversed_osmids(network_csv_path, trajectories_csv_path):
    """
    读取路网和轨迹文件，找出每个订单ID所经过路段的osmid列表。

    Args:
        network_csv_path (str): 路网CSV文件的路径。
        trajectories_csv_path (str): 轨迹CSV文件的路径。

    Returns:
        pandas.DataFrame: 一个包含 [order_id, osmids] 列的DataFrame。
    """
    # --- 步骤 1: 读取CSV文件 ---
    print("\n--- 步骤 1: 读取CSV文件 ---")
    try:
        network_df = pd.read_csv(network_csv_path)
        trajectories_df = pd.read_csv(trajectories_csv_path)
        print(f"成功读取 '{network_csv_path}' 和 '{trajectories_csv_path}'。")
    except FileNotFoundError as e:
        print(f"错误: {e}. 请确保文件路径正确。")
        return None

    # --- 步骤 2: 构建路网边到osmid的快速查找字典 ---
    # 为了高效匹配，我们将路网的边 (u, v) 和 osmid 存储在字典中。
    # 键是代表边的元组 (u, v)，值是 osmid。
    # 这样查找一条边的时间复杂度是 O(1)，远快于每次都在DataFrame中搜索。
    print("\n--- 步骤 2: 构建路网查找字典 ---")
    edge_to_osmid = {}
    for _, row in network_df.iterrows():
        # 将 (u,v) 对作为键，osmid 作为值
        edge_to_osmid[(row['u'], row['v'])] = row['osmid']
    print(f"查找字典构建完成，包含 {len(edge_to_osmid)} 条路段。")

    # --- 步骤 3: 处理轨迹数据 ---
    print("\n--- 步骤 3: 按 order_id 分组处理轨迹 ---")
    results = []

    # 按 'order_id' 对轨迹点进行分组
    grouped_trajectories = trajectories_df.groupby('order_id')

    for order_id, group in grouped_trajectories:
        # 在每个订单分组内，按 'point_sequence' 排序以确保节点顺序正确
        sorted_group = group.sort_values('point_sequence')

        # 提取排序后的节点ID列表
        path_nodes = sorted_group['node_id'].tolist()

        path_osmids = []
        # 遍历节点列表，两两组合成边 (u, v)
        # 例如，[101, 102, 103] 会生成边 (101, 102) 和 (102, 103)
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i + 1]
            edge = (u, v)

            # 使用字典进行快速查找
            osmid = edge_to_osmid.get(edge)

            if osmid is not None:
                path_osmids.append(osmid)
            else:
                # 如果在路网中找不到对应的边，可以打印一个警告
                print(f"警告: 在路网中未找到订单 '{order_id}' 的路段 {edge}。")

        # 将结果添加到列表中
        results.append({
            'order_id': order_id,
            'osmids': path_osmids
        })

    # --- 步骤 4: 创建并返回最终的DataFrame ---
    print("\n--- 步骤 4: 生成最终结果 ---")
    final_df = pd.DataFrame(results)
    return final_df


if __name__ == '__main__':

    # --- 然后，定义文件路径并运行主函数 ---
    network_file = 'road_network_edges.csv'
    trajectories_file = 'matched_results_parallel.csv'

    # 调用核心函数进行处理
    result_df = find_traversed_osmids(network_file, trajectories_file)

    if result_df is not None:
        print("\n处理完成！每个order_id所经过的路段osmid列表:")
        print(result_df)

    candidate_file_path  = 'candidate_road_segments.csv'

    df = pd.read_csv(candidate_file_path, usecols=['latitude','longitude','candidate_road_osmids'])

    print(df.head())
    # 从df中找到true 候选路段
