import osmnx as ox

bbox = (120.0215, 35.8679, 120.4932, 36.1673)

print("osmnx, geopandas, matplotlib 库已成功导入。")

try:
    G = ox.graph_from_bbox(bbox, network_type='all', simplify=False)
    print("路网数据下载成功！")
except Exception as e:
    print(f"下载数据时发生错误: {e}")
    exit()

# 3. 将路网数据转换为 GeoDataFrames
# osmnx 可以方便地将图(Graph)结构转换为节点(nodes)和边(edges)的 GeoDataFrame
# 节点是交叉路口，边是道路
nodes, edges = ox.graph_to_gdfs(G)
print("已将路网图转换为 GeoDataFrames。")

# 4. 导出为 CSV 文件
# GeoDataFrame 可以像 Pandas DataFrame 一样轻松保存
# 节点信息 (交叉路口)
nodes_filepath = 'road_network_nodes.csv'
edges_filepath = 'road_network_edges.csv'

# 使用 encoding='utf-8-sig' 可以防止在 Excel 中打开中文路名时出现乱码
nodes.to_csv(nodes_filepath, encoding='utf-8-sig')
edges.to_csv(edges_filepath, encoding='utf-8-sig')

print(f"节点数据已保存到: {nodes_filepath}")
print(f"边(道路)数据已保存到: {edges_filepath}")

# 5. 绘制路网并保存为图像文件
print("正在生成路网图像...")

# 使用 osmnx 内置的绘图功能
# bgcolor 是背景色，edge_color 是道路颜色，node_size 控制节点大小 (设为0则不显示)
fig, ax = ox.plot_graph(
    G,
    bgcolor='#FFFFFF',       # 白色背景
    edge_color='gray',       # 灰色道路
    edge_linewidth=0.8,      # 道路线宽
    node_size=0,             # 不显示节点
    show=False,              # 不在屏幕上显示，仅用于保存
    close=True               # 完成后关闭图形
)

# 定义输出图像文件名和参数
image_filepath = 'road_network_map.png'
# dpi (dots per inch) 控制图像分辨率，值越高图像越清晰
# bbox_inches='tight' 和 pad_inches=0 可以去除图像周边的白边
fig.savefig(image_filepath, dpi=300, format='png', bbox_inches='tight', pad_inches=0)

print(f"路网图像已保存到: {image_filepath}")
print("\n所有任务完成！")