import networkx as nx
from leuvenmapmatching.map.inmem import InMemMap
from leuvenmapmatching.matcher.distance import DistanceMatcher
import pandas as pd
import numpy as np
from leuvenmapmatching import visualization as mmviz
from typing import Optional
from tqdm import tqdm

def convert_df_to_trajectory(df):
    trajectory = []
    for _, row in df.iterrows():
        # 假设DataFrame中包含'latitude'和'longitude'列
        # trajectory变量中需要latitude在前，longitude在后
        latitude = float(row['latitude'])
        longitude = float(row['longitude'])
        trajectory.append((latitude, longitude))
    return trajectory


def create_graph_from_csvs(nodes_filepath: str,
                           edges_filepath: str,
                           node_id_col: str = 'osmid',
                           edge_u_col: str = 'u',
                           edge_v_col: str = 'v',
                           edge_key_col: Optional[str] = 'key',
                           crs: str = 'epsg:4326') -> InMemMap:
    """
    从节点和边的 CSV 文件创建一个 NetworkX MultiDiGraph。

    该函数会读取两个CSV文件，一个包含节点及其属性，另一个包含边及其属性，
    然后构建并返回一个 NetworkX 多重有向图（MultiDiGraph）。

    Args:
        nodes_filepath (str): 包含节点数据的 CSV 文件的路径。
        edges_filepath (str): 包含边数据的 CSV 文件的路径。
        node_id_col (str, optional): 节点文件中用作唯一节点标识符的列名。
                                     默认为 'osmid'。
        edge_u_col (str, optional): 边文件中表示边起点节点的列名。默认为 'u'。
        edge_v_col (str, optional): 边文件中表示边终点节点的列名。默认为 'v'。
        edge_key_col (Optional[str], optional): 边文件中用于区分平行边的键（key）的列名。
                                                如果为 None 或列不存在，则使用默认键。默认为 'key'。
        crs (str, optional): 要设置在图属性中的坐标参考系统 (CRS)。
                             默认为 'epsg:4326'。

    Returns:
        nx.MultiDiGraph: 根据输入文件创建的图对象。

    Raises:
        FileNotFoundError: 如果节点或边的文件路径不存在。
        KeyError: 如果指定的 ID 或 u/v 列在相应的 DataFrame 中不存在。
    """
    # 1. 读取数据
    try:
        nodes_df = pd.read_csv(nodes_filepath)
        edges_df = pd.read_csv(edges_filepath)
    except FileNotFoundError as e:
        print(f"错误：文件未找到 - {e}")
        raise

    # 2. 创建一个空的 MultiDiGraph
    G = nx.MultiDiGraph()

    # 3. 添加节点
    # 检查节点ID列是否存在
    if node_id_col not in nodes_df.columns:
        raise KeyError(f"错误：节点文件中未找到指定的节点ID列 '{node_id_col}'。")

    nodes_df = nodes_df.set_index(node_id_col)
    for node_id, data in nodes_df.iterrows():
        # 使用 to_dict() 将一行所有数据转换为属性字典
        attributes = data.to_dict()
        G.add_node(node_id, **attributes)

    # 4. 添加边
    # 检查 u, v 列是否存在
    if edge_u_col not in edges_df.columns or edge_v_col not in edges_df.columns:
        raise KeyError(f"错误：边文件中未找到指定的起点/终点列 '{edge_u_col}' 或 '{edge_v_col}'。")

    for _, row in edges_df.iterrows():
        u, v = row[edge_u_col], row[edge_v_col]

        # 提取除了 u, v 之外的所有属性
        attributes = row.to_dict()
        attributes.pop(edge_u_col)
        attributes.pop(edge_v_col)

        # 获取 key，如果列存在则使用，否则默认为 0
        key = attributes.pop(edge_key_col, 0) if edge_key_col else 0

        G.add_edge(u, v, key=key, **attributes)

    # 5. 设置图的全局属性
    G.graph['crs'] = crs

    print(f"图创建成功！包含 {G.number_of_nodes()} 个节点和 {G.number_of_edges()} 条边。")

    map_con = InMemMap("leuven_map", use_latlon=True, use_rtree=True, index_edges=True)

    # 将从OSMnx下载的图数据加载到地图对象中
    # 遍历所有节点
    for node_id, node_data in G.nodes(data=True):
        map_con.add_node(node_id, (node_data['y'], node_data['x']))  # y是纬度, x是经度

    # 遍历所有边
    for u, v in G.edges(keys=False):
        map_con.add_edge(u, v)

    return map_con


def create_matcher(map_con:InMemMap) -> DistanceMatcher:
    map_matcher = DistanceMatcher(
        map_con = map_con,
        max_dist=100,  # 观测点与路段的最大搜索距离（米）
        obs_noise=15,  # 观测噪声的标准差（米），代表GPS的误差范围
        min_prob_norm=0.001,
        non_emitting_states=True,  # 允许在稀疏轨迹点之间插入未匹配的路径
        only_edges=True
    )

    return map_matcher




if __name__ == '__main__':
    map_con = create_graph_from_csvs('road_network_nodes.csv','road_network_edges.csv')
    matcher = create_matcher(map_con)


    csv_file = 'filtered_orders.csv'
    df = pd.read_csv(csv_file)

    unique_order_ids = df['order_id'].unique()

    for order_id in tqdm(unique_order_ids):
        print(f"正在处理订单 {order_id}...")
    random_order_id = np.random.choice(unique_order_ids)
    order_data = df[df['order_id'] == random_order_id]
    order_data_sorted = order_data.sort_values('gps_time')

    trajectory = convert_df_to_trajectory(order_data_sorted)
    print(f"已定义 {len(trajectory)} 个点的示例GPS轨迹。")



    states, _ = matcher.match(trajectory, unique=False)
    print("地图匹配完成。")


    # 打印匹配到的路径（节点ID序列）
    # states 列表包含了最可能的路径所经过的节点ID
    print("\n匹配到的路径节点序列:")
    print(states)
    print(f"states序列长度：{len(states)}")

    nodes = matcher.path_pred_onlynodes
    print("Nodes\n------")
    print(nodes)
    print(f"nodes序列长度：{len(nodes)}")

    path = matcher.path


    mmviz.plot_map(map_con, matcher=matcher,
                  show_labels=True, show_matching=True,
                  filename="output.png")


    # 将匹配结果保存为CSV文件
    # 创建一个dataframe
    matched_data = []
    for i, node_id in enumerate(nodes):
        try:
            lat, lon = map_con.node_coordinates(node_id)
            matched_data.append({
                'sequence': i,
                'order_id': random_order_id,
                'matched_latitude': lat,
                'matched_longitude': lon
            })
        except KeyError:
            print(f"警告: 找不到节点 {node_id} 的坐标信息")
            continue

        # 创建DataFrame
    matched_df = pd.DataFrame(matched_data)
    print(f"匹配结果长度{len(matched_df)}")
    # 合并原始GPS数据和匹配结果




    matched_df.to_csv('vis_matched_results.csv', index=False)
    print("匹配结果已保存到 'vis_matched_results.csv' 文件中。")
    order_data_sorted.to_csv('original_gps_data.csv', index=False)
