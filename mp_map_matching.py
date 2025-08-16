import networkx as nx
from leuvenmapmatching.map.inmem import InMemMap
from leuvenmapmatching.matcher.distance import DistanceMatcher
import pandas as pd
from typing import Optional
from tqdm import tqdm
import concurrent.futures


def convert_df_to_trajectory(df):
    # Convert dataframe to a trajectory (list of tuples with latitude, longitude)
    return [(float(row['latitude']), float(row['longitude'])) for _, row in df.iterrows()]


def create_graph_from_csvs(nodes_filepath: str,
                           edges_filepath: str,
                           node_id_col: str = 'osmid',
                           edge_u_col: str = 'u',
                           edge_v_col: str = 'v',
                           edge_key_col: Optional[str] = 'key',
                           crs: str = 'epsg:4326') -> InMemMap:
    """
    Create a graph from CSV files containing nodes and edges.
    """
    try:
        nodes_df = pd.read_csv(nodes_filepath)
        edges_df = pd.read_csv(edges_filepath)
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        raise

    G = nx.MultiDiGraph()

    # Add nodes
    if node_id_col not in nodes_df.columns:
        raise KeyError(f"Node ID column '{node_id_col}' not found.")
    nodes_df = nodes_df.set_index(node_id_col)
    for node_id, data in nodes_df.iterrows():
        G.add_node(node_id, **data.to_dict())

    # Add edges
    if edge_u_col not in edges_df.columns or edge_v_col not in edges_df.columns:
        raise KeyError(f"Edge columns '{edge_u_col}' or '{edge_v_col}' not found.")
    for _, row in edges_df.iterrows():
        u, v = row[edge_u_col], row[edge_v_col]
        attributes = row.to_dict()
        attributes.pop(edge_u_col)
        attributes.pop(edge_v_col)
        key = attributes.pop(edge_key_col, 0) if edge_key_col else 0
        G.add_edge(u, v, key=key, **attributes)

    G.graph['crs'] = crs
    print(f"Graph created successfully with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

    # Create InMemMap object
    map_con = InMemMap("leuven_map", use_latlon=True, use_rtree=True, index_edges=True)
    for node_id, node_data in G.nodes(data=True):
        map_con.add_node(node_id, (node_data['y'], node_data['x']))  # y=lat, x=lon

    for u, v in G.edges(keys=False):
        map_con.add_edge(u, v)

    return map_con


def create_matcher(map_con: InMemMap) -> DistanceMatcher:
    """
    Create a map matcher using the InMemMap object.
    """
    return DistanceMatcher(
        map_con=map_con,
        max_dist=100,
        obs_noise=15,
        min_prob_norm=0.001,
        non_emitting_states=True
    )


def process_order(order_id, df, matcher, map_con):
    """
    Process an individual order to match the trajectory to the graph.
    """
    order_data = df[df['order_id'] == order_id]
    order_data_sorted = order_data.sort_values('gps_time')
    trajectory = convert_df_to_trajectory(order_data_sorted)

    states, _ = matcher.match(trajectory, unique=False)
    nodes = matcher.path_pred_onlynodes

    matched_data = []
    for i, node_id in enumerate(nodes):
        try:
            lat, lon = map_con.node_coordinates(node_id)
            matched_data.append({
                'sequence': i,
                'order_id': order_id,
                'matched_latitude': lat,
                'matched_longitude': lon
            })
        except KeyError:
            print(f"Warning: Coordinates for node {node_id} not found.")
            continue

    return matched_data, len(trajectory) != len(states)


def main():
    # Create the graph and matcher
    map_con = create_graph_from_csvs('road_network_nodes.csv', 'road_network_edges.csv')
    matcher = create_matcher(map_con)

    # Read the CSV file containing the orders
    csv_file = 'filtered_orders.csv'
    df = pd.read_csv(csv_file)

    unique_order_ids = df['order_id'].unique()
    result_df = pd.DataFrame()
    no_eq_count = 0

    # Use concurrent.futures for parallel processing of orders
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {
            executor.submit(process_order, order_id, df, matcher, map_con): order_id
            for order_id in unique_order_ids
        }

        for future in tqdm(concurrent.futures.as_completed(futures)):
            matched_data, is_inconsistent = future.result()
            matched_df = pd.DataFrame(matched_data)
            result_df = pd.concat([result_df, matched_df])

            if is_inconsistent:
                no_eq_count += 1

    # Save the results to a CSV file
    result_df.to_csv('matched_results.csv', index=False)
    print(f"Processed {len(unique_order_ids)} orders.")
    print(f"Number of orders with length mismatch: {no_eq_count}")


if __name__ == '__main__':
    main()
