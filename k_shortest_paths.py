import pandas as pd
import networkx as nx
from haversine import haversine, Unit
import itertools

NODE_FILE = 'road_network_nodes.csv'
EDGE_FILE = 'road_network_edges.csv'

# --- 2. 加载数据 ---
print("正在加载CSV文件...")
try:
    nodes_df = pd.read_csv(NODE_FILE)
    edges_df = pd.read_csv(EDGE_FILE)
    print("文件加载成功。")
    # 确保列名正确，如果你的列名不同，请在这里修改
    # 例如: nodes_df.rename(columns={'id': 'node_id', 'longitude': 'lon', 'latitude': 'lat'}, inplace=True)
except FileNotFoundError as e:
    print(f"错误: {e}")
    print("请确保CSV文件与脚本在同一目录下，或者提供完整路径。")
    exit()

# --- 3. 构建路网图 ---
print("正在构建路网图...")
G = nx.Graph()

# 添加节点，并存储经纬度信息
for _, row in nodes_df.iterrows():
    G.add_node(row['osmid'], lon=row['x'], lat=row['y'])

# 添加边，并设置权重
if 'length' in edges_df.columns:
    print("使用CSV中提供的 'length' 作为权重。")
    for _, row in edges_df.iterrows():
        G.add_edge(row['u'], row['v'], weight=row['length'])
else:
    # 如果edges.csv中没有length列，我们可以自己计算
    print("警告: 'length' 列未在edges.csv中找到。")
    print("正在根据节点坐标计算边的权重（直线距离）。")
    node_coords = {row['node_id']: (row['lat'], row['lon']) for _, row in nodes_df.iterrows()}
    for _, row in edges_df.iterrows():
        try:
            coord1 = node_coords[row['u']]
            coord2 = node_coords[row['v']]
            # 计算两点间的哈弗赛因距离（单位：米）
            distance = haversine(coord1, coord2, unit=Unit.METERS)
            G.add_edge(row['u'], row['v'], weight=distance)
        except KeyError as e:
            print(f"警告: 节点 {e} 在edges文件中存在，但在nodes文件中未找到。该边将被忽略。")


print(f"图构建完成。节点数: {G.number_of_nodes()}, 边数: {G.number_of_edges()}")

# --- 4. 寻找最近的节点 ---
def find_nearest_node(graph, lat, lon):
    """
    在图中找到距离给定经纬度最近的节点
    """
    min_dist = float('inf')
    nearest_node = None
    for node, data in graph.nodes(data=True):
        dist = haversine((lat, lon), (data['lat'], data['lon']), unit=Unit.METERS)
        if dist < min_dist:
            min_dist = dist
            nearest_node = node
    return nearest_node


# 你的两个经纬度坐标 (纬度, 经度)
start_coord = (35.985924, 120.146173)
end_coord = (35.979291, 120.161095)

OUTPUT_CSV_FILE = 'shortest_paths_coordinates.csv'
print("\n正在为起始和结束坐标寻找最近的路网节点...")
start_node = find_nearest_node(G, start_coord[0], start_coord[1])
end_node = find_nearest_node(G, end_coord[0], end_coord[1])

print(f"起始坐标 {start_coord} -> 最近节点: {start_node}")
print(f"结束坐标 {end_coord} -> 最近节点: {end_node}")

# --- 5. 计算4条最短路径 ---
if start_node is None or end_node is None:
    print("错误：无法找到有效的起始或结束节点。")
elif start_node == end_node:
    print("错误：起始节点和结束节点相同。")
else:
    print(f"\n正在计算从节点 {start_node} 到 {end_node} 的4条最短路径...")
    try:
        paths_generator = nx.shortest_simple_paths(G, source=start_node, target=end_node, weight='weight')
        k_shortest_paths = list(itertools.islice(paths_generator, 4))

        # --- 6. 显示结果并准备保存数据 ---
        if not k_shortest_paths:
            print("在路网中找不到任何从起点到终点的路径。")
        else:
            # 用于存储所有路径坐标的列表
            all_paths_data = []

            for i, path in enumerate(k_shortest_paths):
                total_length = nx.path_weight(G, path, weight='weight')

                print(f"\n--- 路径 {i + 1} ---")
                print(f"  总长度: {total_length:.2f} 米")
                print(f"  节点数量: {len(path)}")
                print(f"  节点序列: {path}")

                # =======================================================
                # 新增部分：为当前路径的每个节点提取坐标并添加到列表中
                # =======================================================
                for j, node_id in enumerate(path):
                    # 从nodes_df中查找经纬度
                    node_coords = nodes_df.loc[nodes_df['osmid'] == node_id]
                    all_paths_data.append({
                        'path_id': i + 1,  # 路径编号 (1, 2, 3, ...)
                        'node_order': j,  # 节点在路径中的顺序 (0, 1, 2, ...)
                        'node_id': node_id,  # 节点ID
                        'lon': node_coords['x'].iloc[0],
                        'lat': node_coords['y'].iloc[0]
                    })

            # =======================================================
            # 新增部分：将所有路径数据转换为DataFrame并保存为CSV
            # =======================================================
            if all_paths_data:
                results_df = pd.DataFrame(all_paths_data)
                results_df.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
                print(f"\n所有路径的坐标已成功保存到文件: '{OUTPUT_CSV_FILE}'")

            if len(k_shortest_paths) < 4:
                print(f"\n注意: 在路网中只找到了 {len(k_shortest_paths)} 条路径，少于您要求的4条。")

    except nx.NetworkXNoPath:
        print(f"在路网中找不到任何从节点 {start_node} 到 {end_node} 的路径。")