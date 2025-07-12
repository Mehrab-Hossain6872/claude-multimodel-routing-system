import networkx as nx
from geopy.distance import geodesic

def nearest_node(G, lat, lon):
    """
    Find the nearest node in the graph to the given coordinates.
    
    Args:
        G: NetworkX graph
        lat: Latitude
        lon: Longitude
    
    Returns:
        Node ID of the nearest node
    """
    min_dist = float('inf')
    nearest = None
    
    for n, data in G.nodes(data=True):
        node_lat, node_lon = data.get('y'), data.get('x')
        if node_lat is None or node_lon is None:
            continue
        
        # Calculate distance using geodesic (more accurate for geographic coordinates)
        dist = geodesic((lat, lon), (node_lat, node_lon)).meters
        
        if dist < min_dist:
            min_dist = dist
            nearest = n
    
    if nearest:
        print(f"Requested: ({lat:.6f}, {lon:.6f}), Nearest: ({G.nodes[nearest]['y']:.6f}, {G.nodes[nearest]['x']:.6f}), Distance: {min_dist:.2f}m")
    else:
        print(f"No nearest node found for ({lat:.6f}, {lon:.6f})")
    
    return nearest

def calc_cost(mode, time_minutes):
    """
    Calculate the cost for a given transport mode and time.
    
    Args:
        mode: Transport mode ('walk', 'bike', 'car', 'transfer')
        time_minutes: Time in minutes
    
    Returns:
        Cost in currency units (৳)
    """
    if mode == 'car':
        return 20  # Flat rate per car trip in ৳
    elif mode == 'bike':
        return 0   # Free biking
    elif mode == 'walk':
        return 0   # Free walking
    elif mode == 'transfer':
        return 0   # Free transfer between modes
    else:
        return 0   # Default: free