import pandas as pd
import numpy as np
def get_random_order_trajectories(df: pd.DataFrame, n: int = 1) -> pd.DataFrame:
    """
    从包含GPS轨迹数据的DataFrame中随机抽取n个订单的完整轨迹，并按订单和时间排序。

    参数:
        df (pd.DataFrame): 包含GPS数据的输入DataFrame。
                           必须包含 'order_id' 和 'gps_time' 列。
        n (int, optional):  要随机抽取的订单数量。默认为 1。

    返回:
        pd.DataFrame: 一个新的DataFrame，其中包含随机选定的n个订单的所有GPS点。
                      数据首先按 'order_id' 排序，然后在每个订单内按 'gps_time' 升序排列。
                      如果输入DataFrame为空或n<1，则返回空DataFrame。
    """
    # 1. 边缘情况处理
    if df.empty or n < 1:
        print("警告：输入的DataFrame为空或请求的订单数n小于1，返回空DataFrame。")
        return pd.DataFrame()

    # 2. 获取所有唯一的订单ID
    unique_orders = df['order_id'].unique()
    num_unique_orders = len(unique_orders)

    if num_unique_orders == 0:
        print("警告：在 'order_id' 列中没有找到有效订单。")
        return pd.DataFrame()

    # 3. 决定要抽样的订单ID列表
    # 如果请求的n大于等于总订单数，就返回所有订单
    if n >= num_unique_orders:
        print(f"警告：请求的订单数 ({n}) 大于或等于总的唯一订单数 ({num_unique_orders})。将返回所有订单的轨迹。")
        sampled_order_ids = unique_orders
    else:
        # 随机抽取n个不重复的订单ID
        sampled_order_ids = np.random.choice(unique_orders, size=n, replace=False)

    print(f"已随机抽取的订单ID为: {list(sampled_order_ids)}")

    # 4. 使用 .isin() 高效筛选出所有被选中订单的数据
    # 使用 .copy() 以避免后续操作影响原始数据
    trajectories_df = df[df['order_id'].isin(sampled_order_ids)].copy()

    # 5. 将 'gps_time' 列转换为 datetime 对象以确保排序准确性
    trajectories_df['gps_time'] = pd.to_datetime(trajectories_df['gps_time'])

    # 6. 核心排序：先按订单ID分组，再在组内按时间升序排列
    sorted_trajectories_df = trajectories_df.sort_values(
        by=['order_id', 'gps_time'],
        ascending=True
    )

    return sorted_trajectories_df

def get_random_driver_data(df: pd.DataFrame, n: int = 1) -> pd.DataFrame:
    """
    从包含GPS轨迹数据的DataFrame中随机抽取n个司机的全部数据，并按司机和时间排序。

    参数:
        df (pd.DataFrame): 包含GPS数据的输入DataFrame。
                           必须包含 'driver_id' 和 'gps_time' 列。
        n (int, optional):  要随机抽取的司机数量。默认为 1。

    返回:
        pd.DataFrame: 一个新的DataFrame，其中包含随机选定的n个司机的所有数据点。
                      数据首先按 'driver_id' 排序，然后在每个司机内按 'gps_time' 升序排列。
                      如果输入DataFrame为空或n<1，则返回空DataFrame。
    """
    # 1. 边缘情况处理
    if df.empty or n < 1:
        print("警告：输入的DataFrame为空或请求的司机数n小于1，返回空DataFrame。")
        return pd.DataFrame()

    # 2. 获取所有唯一的司机ID
    unique_drivers = df['driver_id'].unique()
    num_unique_drivers = len(unique_drivers)

    if num_unique_drivers == 0:
        print("警告：在 'driver_id' 列中没有找到有效司机。")
        return pd.DataFrame()

    # 3. 决定要抽样的司机ID列表
    # 如果请求的n大于等于总司机数，就返回所有司机的数据
    if n >= num_unique_drivers:
        print(f"警告：请求的司机数 ({n}) 大于或等于总的唯一司机数 ({num_unique_drivers})。将返回所有司机的数据。")
        sampled_driver_ids = unique_drivers
    else:
        # 随机抽取n个不重复的司机ID
        sampled_driver_ids = np.random.choice(unique_drivers, size=n, replace=False)

    print(f"已随机抽取的司机ID为: {list(sampled_driver_ids)}")

    # 4. 使用 .isin() 高效筛选出所有被选中司机的数据
    driver_data_df = df[df['driver_id'].isin(sampled_driver_ids)].copy()

    # 5. 将 'gps_time' 列转换为 datetime 对象以确保排序准确性
    driver_data_df['gps_time'] = pd.to_datetime(driver_data_df['gps_time'])

    # 6. 核心排序：先按司机ID分组，再在组内按时间升序排列
    sorted_driver_data_df = driver_data_df.sort_values(
        by=['driver_id', 'gps_time'],
        ascending=True
    )

    return sorted_driver_data_df

