import pandas as pd
import numpy as np

def filter_gps_data_by_interval(df: pd.DataFrame, time_threshold: int = 4) -> pd.DataFrame:
    """
    筛选出GPS平均采样间隔大于指定阈值的订单。

    这个函数接收一个包含GPS数据的DataFrame，计算每个订单的平均GPS时间间隔，
    并返回一个只包含那些平均间隔大于阈值的订单的完整数据的新DataFrame。

    参数:
    - df (pd.DataFrame): 输入的DataFrame。
      必须包含列: ['order_id', 'gps_time']。
      'gps_time' 列应为Unix时间戳（秒）或可以被pd.to_datetime识别的格式。
    - time_threshold (int): 平均采样间隔的阈值（单位：秒），默认为4。

    返回:
    - pd.DataFrame: 一个新的DataFrame，包含了所有满足条件的订单的原始记录。
      如果没有任何订单满足条件，将返回一个空的DataFrame。
    """
    # 检查必需的列是否存在
    required_columns = ['order_id', 'gps_time']
    if not all(col in df.columns for col in required_columns):
        raise KeyError(f"输入DataFrame中缺少必需的列。需要 {required_columns}。")

    # 创建一个副本以避免修改原始传入的DataFrame
    data = df.copy()

    # 1. 将 'gps_time' 列统一转换为datetime对象以便计算
    #    我们假设 'gps_time' 是以秒为单位的Unix时间戳。
    if not pd.api.types.is_datetime64_any_dtype(data['gps_time']):
        data['gps_time'] = pd.to_datetime(data['gps_time'])

    # 2. 按订单ID和GPS时间排序
    data = data.sort_values(by=['order_id', 'gps_time'])

    # 3. 按 'order_id' 分组，计算每个订单内连续记录的时间差（秒）
    #    .diff() 计算与前一行的差值。每个分组的第一行结果是 NaT。
    data['time_interval'] = data.groupby('order_id')['gps_time'].diff().dt.total_seconds()

    # 4. 计算每个订单的平均采样间隔
    #    这里我们使用 .groupby().mean() 来获取每个order_id的平均间隔
    mean_intervals = data.groupby('order_id')['time_interval'].mean()

    # 5. 找出平均间隔大于阈值的订单ID
    #    .index 会返回满足条件的 'order_id'
    orders_to_keep = mean_intervals[mean_intervals > time_threshold].index

    # 6. 从原始副本中筛选出这些订单的全部GPS信息
    #    .isin() 用于高效地筛选出'order_id'在列表orders_to_keep中的所有行
    result_df = data[data['order_id'].isin(orders_to_keep)].copy()

    # 7. 移除用于计算的临时列，使返回的DataFrame保持原始结构
    result_df.drop(columns=['time_interval'], inplace=True)

    return result_df


def filter_orders_by_max_interval(df: pd.DataFrame, max_time_threshold: int = 4) -> pd.DataFrame:
    """
    筛选出最大GPS采样间隔小于指定阈值的订单。

    此函数会检查每个订单内所有连续GPS点之间的时间间隔，并找出其中的最大值。
    只有当这个最大间隔严格小于指定的阈值时，该订单的全部数据才会被返回。

    参数:
    - df (pd.DataFrame): 输入的DataFrame。
      必须包含列: ['order_id', 'gps_time']。
    - max_time_threshold (int): 最大采样间隔的阈值（单位：秒），默认为3。
      订单的最大间隔必须严格小于此值。

    返回:
    - pd.DataFrame: 一个新的DataFrame，包含了所有满足条件的订单的原始记录。
      如果没有任何订单满足条件，或者订单只有一个GPS点（无法计算间隔），将返回一个空的DataFrame。
    """
    # 检查必需的列是否存在
    required_columns = ['order_id', 'gps_time']
    if not all(col in df.columns for col in required_columns):
        raise KeyError(f"输入DataFrame中缺少必需的列。需要 {required_columns}。")

    # 创建一个副本以避免修改原始传入的DataFrame
    data = df.copy()

    # 1. 将 'gps_time' 列统一转换为datetime对象以便计算
    if not pd.api.types.is_datetime64_any_dtype(data['gps_time']):
        try:
            data['gps_time'] = pd.to_datetime(data['gps_time'])
        except (ValueError, TypeError) as e:
            print("错误：无法将 'gps_time' 列转换为日期时间对象。")
            raise e

    # 2. 按订单ID和GPS时间排序
    data = data.sort_values(by=['order_id', 'gps_time'])

    # 3. 按 'order_id' 分组，计算每个订单内连续记录的时间差（秒）
    data['time_interval'] = data.groupby('order_id')['gps_time'].diff().dt.total_seconds()

    # 4. 计算每个订单的【最大】采样间隔
    #    .max()会忽略NaT/NaN值，这正是我们想要的，因为它只关注有效的间隔
    max_intervals = data.groupby('order_id')['time_interval'].max()

    # 5. 找出最大间隔小于阈值的订单ID
    #    注意：这里的条件是严格小于 (<)，所以等于阈值的间隔也会被排除。
    #    只有一个GPS点的订单，其max_interval为NaN，不会满足条件，因此也会被排除。
    orders_to_keep = max_intervals[max_intervals < max_time_threshold].index

    # 6. 从原始副本中筛选出这些订单的全部GPS信息
    result_df = data[data['order_id'].isin(orders_to_keep)].copy()

    # 7. 移除用于计算的临时列
    result_df.drop(columns=['time_interval'], inplace=True)

    return result_df

def filter_orders_by_length(df: pd.DataFrame, min_length: int = 20) -> pd.DataFrame:
    """
    根据GPS序列的长度筛选订单，移除点数过少的订单。

    此函数会计算每个订单ID对应的GPS点（即行数）的数量。
    只有当一个订单的GPS点数量大于或等于指定的最小长度时，该订单的
    全部数据才会被保留。

    参数:
    - df (pd.DataFrame): 输入的DataFrame，必须包含 'order_id' 列。
    - min_length (int): 订单需要保留的最小GPS点数量。
      任何订单的点数如果严格小于此值，将被整个移除。默认为 20。

    返回:
    - pd.DataFrame: 一个新的DataFrame，仅包含那些GPS点数足够多的订单的记录。
    """
    # 检查必需的列是否存在
    if 'order_id' not in df.columns:
        raise KeyError("输入DataFrame中缺少必需的列: 'order_id'。")

    # 按 'order_id' 分组，然后使用 filter 方法。
    # filter 会对每个分组（由 lambda x 中的 x 代表）应用一个条件。
    # len(x) 计算了当前分组的行数（即该订单的GPS点数）。
    # 只有当 len(x) >= min_length 条件为 True 时，该分组的全部数据才会被保留。
    filtered_df = df.groupby('order_id').filter(lambda x: len(x) >= min_length)

    # 返回一个副本以避免后续操作可能引发的 SettingWithCopyWarning
    return filtered_df.copy()

def remove_duplicate_gps_points(df: pd.DataFrame, keep: str = 'first') -> pd.DataFrame:
    """
    移除每个订单中GPS位置（经纬度）完全相同的重复数据点。

    此函数会检查每个订单内部是否存在经纬度完全相同的GPS点。如果存在，
    它会根据 'keep' 参数的设置，保留第一个或最后一个出现的点，并移除其余的重复点。

    参数:
    - df (pd.DataFrame): 输入的DataFrame。
      必须包含列: ['order_id', 'longitude', 'latitude']。
    - keep (str): 当检测到重复项时，决定保留哪一个。
      - 'first': (默认) 保留第一次出现的记录。
      - 'last': 保留最后一次出现的记录。
      - False: 移除所有重复的记录。

    返回:
    - pd.DataFrame: 一个新的DataFrame，其中每个订单内位置重复的点已被移除。
    """
    # 检查必需的列是否存在
    required_columns = ['order_id', 'longitude', 'latitude']
    if not all(col in df.columns for col in required_columns):
        raise KeyError(f"输入DataFrame中缺少必需的列。需要 {required_columns}。")

    # 定义用于判断重复的列的子集。
    # 一条记录被认为是重复的，必须是它的 'order_id', 'longitude', 和 'latitude' 都与另一条记录相同。
    subset_cols = ['order_id', 'longitude', 'latitude']

    # 使用 drop_duplicates 方法。
    # 它会根据 subset_cols 中定义的列来查找重复行，并根据 keep 参数决定保留哪一行。
    # 因为我们将 'order_id' 包含在子集中，所以这个操作自然地只会在每个订单内部查找重复。
    # （即，不同订单中相同的经纬度点不会被认为是重复的）
    cleaned_df = df.drop_duplicates(subset=subset_cols, keep=keep)

    return cleaned_df.copy()

def haversine_np(lon1: pd.Series, lat1: pd.Series, lon2: pd.Series, lat2: pd.Series) -> pd.Series:
    """
    使用NumPy向量化计算Haversine距离。

    参数:
    lon1, lat1, lon2, lat2: Pandas Series 对象，包含WGS84格式的经纬度。

    返回:
    一个包含两点之间距离（单位：米）的Pandas Series。
    """
    # 地球半径（米）
    R = 6371000

    # 将十进制度数转换为弧度
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

    # Haversine公式
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))

    distance = R * c
    return distance

def filter_orders_by_distance(df: pd.DataFrame, min_distance_meters: int = 1000) -> pd.DataFrame:
    """
    根据GPS轨迹的总长度筛选订单，移除轨迹过短的订单。

    此函数计算每个订单的GPS轨迹总长度，并移除那些总长度小于
    指定最小距离的订单。

    参数:
    - df (pd.DataFrame): 输入的DataFrame。
      必须包含列: ['order_id', 'gps_time', 'longitude', 'latitude']。
    - min_distance_meters (int): 订单轨迹需要保留的最小长度（单位：米）。
      默认为 1000。

    返回:
    - pd.DataFrame: 一个新的DataFrame，仅包含轨迹长度足够长的订单记录。
    """
    # 检查必需的列是否存在
    required_columns = ['order_id', 'gps_time', 'longitude', 'latitude']
    if not all(col in df.columns for col in required_columns):
        raise KeyError(f"输入DataFrame中缺少必需的列。需要 {required_columns}。")

    # 1. 创建副本并确保数据按订单和时间排序
    data = df.copy()
    data = data.sort_values(by=['order_id', 'gps_time'])

    # 2. 获取每个点的“下一个点”的经纬度
    #    groupby().shift(-1) 可以高效地将每个组的下一行数据移动到当前行
    data['lon_next'] = data.groupby('order_id')['longitude'].shift(-1)
    data['lat_next'] = data.groupby('order_id')['latitude'].shift(-1)

    # 3. 计算每个GPS段（点A到点B）的距离
    #    最后一行每个组的lon_next/lat_next是NaN，haversine_np会返回NaN，sum()时会自动忽略
    data['distance_segment'] = haversine_np(
        data['longitude'],
        data['latitude'],
        data['lon_next'],
        data['lat_next']
    )

    # 4. 按订单ID分组，计算每个订单的总距离
    order_distances = data.groupby('order_id')['distance_segment'].sum()

    # 5. 找出总距离大于或等于最小阈值的订单ID
    orders_to_keep = order_distances[order_distances >= min_distance_meters].index

    # 6. 从原始DataFrame中筛选出这些订单的数据
    result_df = df[df['order_id'].isin(orders_to_keep)].copy()

    return result_df


def filter_orders_by_max_segment_distance(df: pd.DataFrame, max_segment_meters: int = 100) -> pd.DataFrame:
    """
    移除那些包含过长GPS段（跳点）的订单。

    此函数会计算每个订单中所有连续GPS点之间的距离。如果任何一个距离段
    大于指定的阈值，则该订单的全部数据都将被移除。

    参数:
    - df (pd.DataFrame): 输入的DataFrame。
      必须包含列: ['order_id', 'gps_time', 'longitude', 'latitude']。
    - max_segment_meters (int): 连续两点间允许的最大距离（单位：米）。
      默认为 100。

    返回:
    - pd.DataFrame: 一个新的DataFrame，其中不包含任何有跳点的订单。
    """
    # 检查必需的列是否存在
    required_columns = ['order_id', 'gps_time', 'longitude', 'latitude']
    if not all(col in df.columns for col in required_columns):
        raise KeyError(f"输入DataFrame中缺少必需的列。需要 {required_columns}。")

    # 1. 创建副本并按订单和时间排序
    data = df.copy()
    data = data.sort_values(by=['order_id', 'gps_time'])

    # 2. 获取每个点的“下一个点”的经纬度
    data['lon_next'] = data.groupby('order_id')['longitude'].shift(-1)
    data['lat_next'] = data.groupby('order_id')['latitude'].shift(-1)

    # 3. 计算每个GPS段的距离
    data['distance_segment'] = haversine_np(
        data['longitude'],
        data['latitude'],
        data['lon_next'],
        data['lat_next']
    )

    # 4. 找到每个订单中的【最大】分段距离
    max_distances = data.groupby('order_id')['distance_segment'].max()

    # 5. 找出所有分段距离都小于或等于阈值的订单
    #    单点订单的最大距离为NaN，不满足条件，会被自动移除。
    orders_to_keep = max_distances[max_distances <= max_segment_meters].index

    # 6. 从原始DataFrame中筛选出这些“好”订单的数据
    result_df = df[df['order_id'].isin(orders_to_keep)].copy()

    return result_df