import networkx as nx
from utils_py import nearest_node, calc_cost
import logging

logger = logging.getLogger(__name__)

def get_multimodal_route(graph, start_lat, start_lon, end_lat, end_lon):
    """
    Calculate the optimal multimodal route between two points
    
    Args:
        graph: The multimodal graph
        start_lat: Starting latitude
        start_lon: Starting longitude
        end_lat: Ending latitude
        end_lon: Ending longitude
        
    Returns:
        dict: Route information with segments, total time, and cost
    """
    
    try:
        # Find nearest nodes in the graph
        logger.info(f"Finding nearest nodes for start ({start_lat}, {start_lon}) and end ({end_lat}, {end_lon})")
        
        start_node = nearest_node(graph, start_lat, start_lon)
        end_node = nearest_node(graph, end_lat, end_lon)
        
        if start_node is None or end_node is None:
            raise ValueError("Could not find valid nodes near the specified coordinates")
        
        logger.info(f"Found start node: {start_node}, end node: {end_node}")
        
        # Calculate shortest path based on time
        logger.info("Calculating shortest path...")
        try:
            path = nx.shortest_path(graph, start_node, end_node, weight='time')
        except nx.NetworkXNoPath:
            raise ValueError("No path found between the specified points")
        
        logger.info(f"Path found with {len(path)} nodes")
        
        # Convert path to segments
        segments = _path_to_segments(graph, path)
        
        # Calculate totals
        total_time = sum(segment['time'] for segment in segments)
        total_cost = sum(segment['cost'] for segment in segments)
        
        route_data = {
            'total_time': round(total_time, 1),
            'total_cost': round(total_cost, 0),
            'segments': segments
        }
        
        logger.info(f"Route calculated successfully: {len(segments)} segments, {total_time:.1f} minutes, {total_cost} ৳")
        
        return route_data
        
    except Exception as e:
        logger.error(f"Error in route calculation: {str(e)}")
        raise e

def _path_to_segments(graph, path):
    """
    Convert a path (list of nodes) to route segments grouped by transportation mode
    
    Args:
        graph: The multimodal graph
        path: List of node IDs representing the path
        
    Returns:
        list: List of segment dictionaries
    """
    
    if len(path) < 2:
        return []
    
    segments = []
    current_mode = None
    current_coords = []
    current_time = 0
    current_cost = 0
    
    # Process each edge in the path
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        
        # Get edge data (handle MultiDiGraph)
        edge_data = _get_edge_data(graph, u, v)
        
        mode = edge_data.get('mode', 'walk')
        time = edge_data.get('time', 1.0)
        
        # Get coordinates for the current node
        node_data = graph.nodes[u]
        coord = [node_data['y'], node_data['x']]  # [lat, lon]
        
        # Check if we need to start a new segment
        if current_mode is None:
            current_mode = mode
            current_coords = [coord]
        
        if mode != current_mode:
            # Save current segment and start new one
            if current_coords:
                segments.append({
                    'mode': current_mode,
                    'coords': current_coords,
                    'time': round(current_time, 1),
                    'cost': round(current_cost, 0)
                })
            
            # Start new segment
            current_mode = mode
            current_coords = [coord]
            current_time = 0
            current_cost = 0
        
        # Add to current segment
        if coord not in current_coords:
            current_coords.append(coord)
        current_time += time
        current_cost += calc_cost(mode, time)
    
    # Add final coordinate (destination)
    if len(path) > 1:
        final_node = path[-1]
        final_node_data = graph.nodes[final_node]
        final_coord = [final_node_data['y'], final_node_data['x']]
        if final_coord not in current_coords:
            current_coords.append(final_coord)
    
    # Add final segment
    if current_mode is not None and current_coords:
        segments.append({
            'mode': current_mode,
            'coords': current_coords,
            'time': round(current_time, 1),
            'cost': round(current_cost, 0)
        })
    
    return segments

def _get_edge_data(graph, u, v):
    """
    Handles MultiDiGraph edge data extraction
    """
    edge_data = graph.get_edge_data(u, v)
    if isinstance(edge_data, dict):
        # If MultiDiGraph, get the first edge's data
        if 0 in edge_data:
            return edge_data[0]
        else:
            # Get the first available edge data
            return list(edge_data.values())[0]
    return edge_data or {}
