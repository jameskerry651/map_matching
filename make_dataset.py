import pandas as pd
import geopandas as gpd
from shapely.wkt import loads

print("开始创建地图匹配数据集 (v2)...")

# --- 1. 配置和文件路径 ---
# 输入文件
ORIGINAL_TRAJ_PATH = 'original_trajectories_under_70m_diff.csv'
ROAD_NETWORK_PATH = 'road_network_edges.csv'
MATCHED_TRAJ_PATH = 'matched_trajectories_under_70m_diff.csv'

# 输出文件
OUTPUT_PATH = 'map_matching_dataset.csv'

# 为每个原始GPS点查找候选路段的搜索半径（单位：米）
SEARCH_RADIUS_METERS = 70

# --- 2. 加载和初始化数据 ---
try:
    # 加载原始GPS轨迹
    print(f"正在加载原始轨迹: {ORIGINAL_TRAJ_PATH}")
    df_orig = pd.read_csv(ORIGINAL_TRAJ_PATH)
    # 按订单和时间排序，确保轨迹点顺序正确
    df_orig = df_orig.sort_values(by=['order_id', 'gps_time']).reset_index(drop=True)

    # 加载匹配后的轨迹
    print(f"正在加载匹配结果: {MATCHED_TRAJ_PATH}")
    df_matched = pd.read_csv(MATCHED_TRAJ_PATH)

    # 加载路网数据
    print(f"正在加载路网: {ROAD_NETWORK_PATH}")
    df_roads = pd.read_csv(ROAD_NETWORK_PATH)

    # **【修改点】**: 保留原始的WKT字符串格式，用于最终输出
    df_roads['geometry_wkt'] = df_roads['geometry']

    # 将WKT（Well-Known Text）格式的geometry字符串转换为Shapely几何对象以进行空间计算
    df_roads['geometry'] = df_roads['geometry'].apply(loads)
    # 创建路网的GeoDataFrame，并指定其坐标系为EPSG:4326
    gdf_roads = gpd.GeoDataFrame(df_roads, geometry='geometry', crs="EPSG:4326")

except FileNotFoundError as e:
    print(f"错误：文件未找到 - {e}。请确保所有CSV文件都在正确的路径下。")
    exit()

# --- 3. 数据对齐与合并 ---
print("正在对齐原始轨迹与匹配结果...")
# 假设 matched_trajectories_under_70m_diff.csv 中的 'point_sequence' 是从0开始的序列
df_orig['point_sequence'] = df_orig.groupby('order_id').cumcount()

# 根据order_id和point_sequence合并两个DataFrame
df_merged = pd.merge(
    df_orig,
    df_matched[['order_id', 'point_sequence', 'matched_longitude', 'matched_latitude']],
    on=['order_id', 'point_sequence'],
    how='inner'
)

if df_merged.empty:
    print("错误：原始轨迹与匹配结果合并后为空。请检查 'order_id' 和 'point_sequence' 是否能够正确对齐。")
    exit()

print(f"成功合并 {len(df_merged)} 个GPS点。")

# --- 4. 确定真值路段 (True Candidate) ---
print("正在为每个匹配点确定真值路段...")
# 创建包含“真值”匹配点位置的GeoDataFrame (坐标系为 EPSG:4326)
gdf_matched_points = gpd.GeoDataFrame(
    df_merged,
    geometry=gpd.points_from_xy(df_merged['matched_longitude'], df_merged['matched_latitude']),
    crs="EPSG:4326"
)

# 使用sjoin_nearest在路网中为每个匹配点找到最近的道路
gdf_true_candidates = gpd.sjoin_nearest(gdf_matched_points, gdf_roads, how='left')

# sjoin_nearest可能会产生重复行，只保留第一个匹配结果
gdf_true_candidates = gdf_true_candidates.drop_duplicates(subset=['order_id', 'point_sequence'])

# **【修改点】**: 提取真值路段的osmid和原始的WKT几何字符串(geometry_wkt)
df_final = gdf_true_candidates[
    ['order_id', 'point_sequence', 'driver_id', 'gps_time', 'longitude', 'latitude', 'osmid', 'geometry_wkt']].copy()
df_final.rename(columns={'osmid': 'ture_candidate_osmid', 'geometry_wkt': 'ture_candidate_geometry'}, inplace=True)

# --- 5. 寻找候选路段 (Candidate Roads) ---
print(f"正在为每个原始GPS点寻找半径 {SEARCH_RADIUS_METERS} 米内的候选路段...")
# 创建包含原始GPS点位置的GeoDataFrame (坐标系为 EPSG:4326)
gdf_orig_points = gpd.GeoDataFrame(
    df_merged,
    geometry=gpd.points_from_xy(df_merged['longitude'], df_merged['latitude']),
    crs="EPSG:4326"
)

# 为了进行精确的缓冲区计算，临时将坐标系转换为以米为单位的投影坐标系
projected_crs = "EPSG:3857"
gdf_orig_proj = gdf_orig_points.to_crs(projected_crs)
gdf_roads_proj = gdf_roads.to_crs(projected_crs)

# 创建缓冲区
gdf_orig_proj['buffer_geometry'] = gdf_orig_proj.geometry.buffer(SEARCH_RADIUS_METERS)
gdf_orig_proj = gdf_orig_proj.set_geometry('buffer_geometry')

# 将缓冲区与路网进行空间连接，找出所有相交的路段
gdf_candidates = gpd.sjoin(gdf_orig_proj, gdf_roads_proj, how='inner', predicate='intersects')

# 按原始点分组，将所有候选路段的osmid聚合为列表
candidate_osmid_list = gdf_candidates.groupby(['order_id', 'point_sequence'])['osmid'].apply(list)
df_candidate_osmids = candidate_osmid_list.reset_index()
df_candidate_osmids.rename(columns={'osmid': 'candidate_roads_osmid'}, inplace=True)

# --- 6. 合并所有信息并生成最终文件 ---
print("正在整合所有信息并生成最终数据集...")

# 将候选路段列表合并到主DataFrame中
df_final = pd.merge(df_final, df_candidate_osmids, on=['order_id', 'point_sequence'], how='left')

# 填充那些没有找到任何候选路段的GPS点（用空列表表示）
df_final['candidate_roads_osmid'] = df_final['candidate_roads_osmid'].apply(
    lambda x: x if isinstance(x, list) else []
)

# 添加全局唯一的 gps_id
df_final.insert(0, 'gps_id', range(len(df_final)))

# **【修改点】**: 此处不再需要转换 'ture_candidate_geometry' 的格式，因为它已经是正确的WKT字符串

# 按照要求的列顺序排列
final_columns = [
    'gps_id', 'order_id', 'driver_id', 'gps_time',
    'longitude', 'latitude', 'ture_candidate_osmid',
    'ture_candidate_geometry', 'candidate_roads_osmid'
]
df_final = df_final[final_columns]

# 保存到CSV文件
df_final.to_csv(OUTPUT_PATH, index=False)

print("-" * 30)
print(f"成功！数据集已保存到: {OUTPUT_PATH}")
print(f"总共处理了 {len(df_final)} 条记录。")
print("最终数据的坐标均为 EPSG:4326。")
print("数据集预览（前5行）:")
print(df_final.head())
print("-" * 30)