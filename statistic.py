import pandas as pd


def analyze_gps_data(file_path):
    """
    分析GPS数据集，包括基本特性、边界框、采样间隔和异常值识别。

    参数:
    file_path (str): CSV文件的路径。

    返回:
    dict: 包含分析结果的字典。
    """
    try:
        # 1. 加载数据
        chunksize = 100000
        df_chunks = pd.read_csv(file_path, chunksize=chunksize)
        df = pd.concat(df_chunks)

        # 统一列名
        df.rename(columns={
            '司机ID': 'driver_id',
            '订单ID': 'order_id',
            'GPS时间': 'gps_time',
            '轨迹点经度': 'longitude',
            '轨迹点纬度': 'latitude'
        }, inplace=True)

        # 2. 数据预处理和基本特性分析
        print("--- 数据基本特性分析 ---")
        df['gps_time'] = pd.to_datetime(df['gps_time'])

        print(df.info())
        print("\n描述性统计:")

        # --- 修改点 ---
        # 移除了 'datetime_is_numeric=True' 参数以兼容旧版Pandas
        # 旧版本Pandas会自动处理datetime列的描述性统计
        print(df.describe(include='all'))
        # ---------------

        num_drivers = df['driver_id'].nunique()
        num_orders = df['order_id'].nunique()
        time_range = (df['gps_time'].min(), df['gps_time'].max())

        print(f"\n司机数量: {num_drivers}")
        print(f"订单数量: {num_orders}")
        print(f"GPS时间范围: 从 {time_range[0]} 到 {time_range[1]}")

        # 3. 计算经纬度边界
        min_lon = df['longitude'].min()
        max_lon = df['longitude'].max()
        min_lat = df['latitude'].min()
        max_lat = df['latitude'].max()

        bounding_box = {
            "top_left": (max_lat, min_lon),
            "top_right": (max_lat, max_lon),
            "bottom_left": (min_lat, min_lon),
            "bottom_right": (min_lat, max_lon)
        }
        print("\n--- 矩形边界的四个经纬度点 ---")
        print(bounding_box)

        # 4. 分析每个订单的GPS采样间隔
        print("\n--- 每个订单GPS采样间隔分析 ---")
        df.sort_values(by=['order_id', 'gps_time'], inplace=True)
        df['time_diff_seconds'] = df.groupby('order_id')['gps_time'].diff().dt.total_seconds()

        sampling_interval_stats = df.groupby('order_id')['time_diff_seconds'].agg(['min', 'max', 'mean'])
        sampling_interval_stats.rename(columns={
            'min': 'min_interval_s',
            'max': 'max_interval_s',
            'mean': 'avg_interval_s'
        }, inplace=True)

        print("每个订单GPS采样间隔统计（单位：秒）:")
        print(sampling_interval_stats.head())

        print("\n所有订单采样间隔的总体描述性统计（单位：秒）:")
        print(sampling_interval_stats.describe())

        # 5. 识别异常数据集 (使用IQR方法)
        print(f"\n--- 异常数据集识别 ---")
        Q1_lon = df['longitude'].quantile(0.25)
        Q3_lon = df['longitude'].quantile(0.75)
        IQR_lon = Q3_lon - Q1_lon

        Q1_lat = df['latitude'].quantile(0.25)
        Q3_lat = df['latitude'].quantile(0.75)
        IQR_lat = Q3_lat - Q1_lat

        lon_lower_bound = Q1_lon - 1.5 * IQR_lon
        lon_upper_bound = Q3_lon + 1.5 * IQR_lon
        lat_lower_bound = Q1_lat - 1.5 * IQR_lat
        lat_upper_bound = Q3_lat + 1.5 * IQR_lat

        outliers = df[
            (df['longitude'] < lon_lower_bound) | (df['longitude'] > lon_upper_bound) |
            (df['latitude'] < lat_lower_bound) | (df['latitude'] > lat_upper_bound)
            ]

        print(f"根据IQR方法，共发现 {len(outliers)} 个潜在的异常数据点。")
        if not outliers.empty:
            print("异常数据示例:")
            print(outliers.head())

        # 6. 整合并返回所有分析结果
        analysis_results = {
            "num_drivers": num_drivers,
            "num_orders": num_orders,
            "time_range": time_range,
            "bounding_box": bounding_box,
            "sampling_interval_stats": sampling_interval_stats,
            "outliers": outliers
        }

        return analysis_results

    except FileNotFoundError:
        print(f"错误: 文件未找到，请检查文件路径 '{file_path}'。")
        return None
    except Exception as e:
        print(f"发生错误: {e}")
        return None



file_path = 'filtered_orders.csv'
results = analyze_gps_data(file_path)

# 您可以接下来使用 'results' 字典中的数据进行进一步的处理和分析
if results:
    if not results['outliers'].empty:
        results['outliers'].to_csv('outliers.csv', index=False)
        print("\n异常值数据已保存到 'outliers.csv'")

    # if 'sampling_interval_stats' in results and not results['sampling_interval_stats'].empty:
    #     results['sampling_interval_stats'].to_csv('sampling_interval_stats.csv')
    #     print("GPS采样间隔统计数据已保存到 'sampling_interval_stats.csv'")