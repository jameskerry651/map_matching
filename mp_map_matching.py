import networkx as nx
from leuvenmapmatching.map.inmem import InMemMap
from leuvenmapmatching.matcher.distance import DistanceMatcher
import pandas as pd
from typing import Optional
import os  # 导入os模块以获取CPU核心数

# --- 数据转换函数 (稍作优化) ---
def convert_df_to_trajectory(df: pd.DataFrame) -> list[tuple]:
    """将DataFrame转换为轨迹点列表，使用.values提高效率"""
    # to_numpy() 或 .values 比 iterrows() 快得多
    trajectory = df[['latitude', 'longitude']].to_numpy().tolist()
    # 确保内部是元组 (latitude, longitude)
    return [tuple(point) for point in trajectory]


# --- 图和地图构建函数 (保持不变) ---
def create_graph_from_csvs(nodes_filepath: str,
                           edges_filepath: str,
                           node_id_col: str = 'osmid',
                           edge_u_col: str = 'u',
                           edge_v_col: str = 'v',
                           edge_key_col: Optional[str] = 'key',
                           crs: str = 'epsg:4326') -> InMemMap:
    """
    从节点和边的 CSV 文件创建一个 InMemMap 对象。
    (此函数逻辑不变，因为它是一次性设置)
    """
    try:
        nodes_df = pd.read_csv(nodes_filepath, index_col=node_id_col)
        edges_df = pd.read_csv(edges_filepath)
    except FileNotFoundError as e:
        print(f"错误：文件未找到 - {e}")
        raise
    except KeyError:
        # 如果index_col指定的列不存在，pandas会抛出KeyError
        raise KeyError(f"错误：节点文件中未找到指定的节点ID列 '{node_id_col}'。")

    G = nx.MultiDiGraph()

    # 添加节点 (更高效的方式)
    for node_id, data in nodes_df.iterrows():
        G.add_node(node_id, **data.to_dict())

    # 添加边 (更高效的方式)
    for _, row in edges_df.iterrows():
        u, v = row[edge_u_col], row[edge_v_col]
        attributes = row.to_dict()
        attributes.pop(edge_u_col, None)
        attributes.pop(edge_v_col, None)
        key = attributes.pop(edge_key_col, 0) if edge_key_col else 0
        G.add_edge(u, v, key=key, **attributes)

    G.graph['crs'] = crs
    print(f"图创建成功！包含 {G.number_of_nodes()} 个节点和 {G.number_of_edges()} 条边。")

    map_con = InMemMap("leuven_map", use_latlon=True, use_rtree=True, index_edges=True)
    for node_id, node_data in G.nodes(data=True):
        map_con.add_node(node_id, (node_data['y'], node_data['x']))
    for u, v in G.edges():
        map_con.add_edge(u, v)

    return map_con


def create_matcher():
    matcher = DistanceMatcher(
        map_con=global_map_con,
        max_dist=100,
        obs_noise=15,
        min_prob_norm=0.001,
        non_emitting_states=True
    )

    return matcher


def process_order(order_id: str, order_task: pd.DataFrame) -> pd.DataFrame:
    """
    处理单个订单的地图匹配任务。
    这个函数将在子进程中执行。
    """
    order_data = order_task

    # 1. 准备轨迹
    order_data_sorted = order_data.sort_values('gps_time')
    trajectory = convert_df_to_trajectory(order_data_sorted)

    # 如果轨迹为空，直接返回
    if not trajectory:
        print("空的轨迹")
        return pd.DataFrame()

    # 2. 地图匹配
    local_matcher = create_matcher()

    states, _ = local_matcher.match(trajectory, unique=False)
    nodes = local_matcher.path_pred_onlynodes
    total_distance_m = local_matcher.path_pred_distance()
    # 3. 整理结果
    matched_data = []
    for i, node_id in enumerate(nodes):
        try:
            lat, lon = global_map_con.node_coordinates(node_id)
            matched_data.append({
                'point_sequence': i,
                'order_id': order_id,
                'matched_latitude': lat,
                'matched_longitude': lon,
                'total_order_distance_m': total_distance_m,

            })
        except KeyError:
            # 在并行环境中，打印警告可能导致输出混乱，可以考虑记录到日志文件
            # print(f"警告: 找不到节点 {node_id} 的坐标信息")
            continue

    matched_df = pd.DataFrame(matched_data)

    return matched_df


print(f"正在初始化地图...")
global_map_con = create_graph_from_csvs('road_network_nodes.csv', 'road_network_edges.csv')

if __name__ == '__main__':
    print("正在读取订单数据...")
    csv_file = 'filtered_orders.csv'
    df = pd.read_csv(csv_file)

    # --- 2. 准备任务列表 ---
    # 使用groupby来拆分DataFrame，这比循环过滤高效得多
    # 我们创建一个(order_id, order_df)元组的列表作为任务
    print("正在准备并行任务...")
    tasks = list(df.groupby('order_id'))

    total_orders = len(tasks)
    print(f"共找到 {total_orders} 个独立订单，准备进行并行处理。")

    # --- 3. 使用ProcessPoolExecutor进行并行处理 ---
    results_list = []
    no_eq_count = 0

    # 设置工作进程数量，可以根据你的CPU核心数调整
    # os.cpu_count() or 1 确保在单核机器上也能工作
    num_workers = max(1, os.cpu_count() - 1)  # 留一个核心给系统
    print(f"启动 {num_workers} 个工作进程...")

    # 使用tqdm显示进度
    from tqdm.contrib.concurrent import process_map

    # 使用process_map替代Pool.starmap，自带进度条
    # 设置chunksize以提高多进程性能，根据任务数量和进程数调整
    chunksize = max(1, len(tasks) // (num_workers * 2))
    matched_df = process_map(process_order, *zip(*tasks), max_workers=num_workers, desc="匹配进度", chunksize=chunksize)

    # 将matched_df列表合并为一个DataFrame
    result_df = pd.concat(matched_df, ignore_index=True)

    # 保存结果
    result_df.to_csv('matched_results_parallel.csv', index=False)
    print("结果已保存到 'matched_results_parallel.csv'")

    print(f"共处理订单数量：{total_orders}")
