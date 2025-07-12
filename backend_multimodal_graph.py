import os
# import osmnx as ox  # Removed OSMnx
# ox.settings.use_cache = False  # Disable cache for a clean start
import networkx as nx
from shapely.geometry import Point
from geopy.distance import geodesic
import logging
from pyrosm import OSM  # Added Pyrosm import
# from pyrosm.network import to_networkx # This line is removed as per the edit hint

logger = logging.getLogger(__name__)

class MultimodalGraphBuilder:
    """
    Builds or loads a multimodal graph combining walking, biking, and driving networks
    """
    
    def __init__(self, place_or_bbox=None, walk_speed=5, bike_speed=15, car_speed=40, graphml_path=None, osm_file=None, network_type='drive'):
        """
        Initialize the multimodal graph builder
        Args:
            place_or_bbox: Either a place name string or bbox tuple (north, south, east, west)
            walk_speed: Walking speed in km/h (default: 5)
            bike_speed: Biking speed in km/h (default: 15)
            car_speed: Car speed in km/h (default: 40)
            graphml_path: Path to pre-downloaded GraphML file (optional)
            osm_file: Path to a local OSM file (.osm.pbf or .osm.xml) (optional)
            network_type: 'drive', 'walk', 'bike', etc. (default: 'drive')
        """
        self.place_or_bbox = place_or_bbox
        self.walk_speed = walk_speed
        self.bike_speed = bike_speed
        self.car_speed = car_speed
        self.graph = None
        self.graphml_path = graphml_path
        self.osm_file = osm_file
        self.network_type = network_type
        
        # Configure OSMnx settings
        

    def build(self):
        """
        Build or load the complete multimodal graph
        Returns:
            nx.MultiDiGraph: The complete multimodal graph
        """
        # 1. Load from GraphML if available (optional, but OSMnx-specific logic removed)
        if self.graphml_path and os.path.exists(self.graphml_path):
            logger.info(f"Loading graph from {self.graphml_path} ...")
            self.graph = nx.read_graphml(self.graphml_path)
            logger.info(f"Graph loaded from {self.graphml_path}: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
            return self.graph
        # 2. Load from OSM PBF file using Pyrosm
        if self.osm_file and os.path.exists(self.osm_file):
            logger.info(f"Loading graph from OSM PBF file: {self.osm_file} ...")
            # Extract networks for each mode
            walk_graph = self._extract_graph('walking')
            bike_graph = self._extract_graph('cycling')
            car_graph = self._extract_graph('driving')

            # Relabel nodes to make them unique per mode
            walk_graph = self._relabel_nodes(walk_graph, 'walk')
            bike_graph = self._relabel_nodes(bike_graph, 'bike')
            car_graph = self._relabel_nodes(car_graph, 'car')

            # Add mode attributes and calculate travel times
            self._add_mode_attributes(walk_graph, 'walk', self.walk_speed)
            self._add_mode_attributes(bike_graph, 'bike', self.bike_speed)
            self._add_mode_attributes(car_graph, 'car', self.car_speed)

            # Merge all graphs
            logger.info("Merging individual mode graphs...")
            merged_graph = nx.compose_all([walk_graph, bike_graph, car_graph])

            # Add interlayer transfer edges
            self._add_interlayer_edges(merged_graph, walk_graph, bike_graph, car_graph)

            self.graph = merged_graph
            logger.info(f"Multimodal graph built successfully: {len(merged_graph.nodes)} nodes, {len(merged_graph.edges)} edges")

            # Save the graph if a path is provided (as GraphML, using NetworkX)
            if self.graphml_path:
                logger.info(f"Saving graph to {self.graphml_path} ...")
                nx.write_graphml(self.graph, self.graphml_path)
                logger.info(f"Graph saved to {self.graphml_path}")

            return merged_graph
        else:
            raise ValueError("No valid OSM PBF file provided.")

    def _extract_graph(self, network_type):
        logger.info(f"Extracting {network_type} graph using Pyrosm...")
        try:
            osm = OSM(self.osm_file)
            gdf = osm.get_network(network_type=network_type)
            print("GDF columns:", gdf.columns)
            # Try using 'u' and 'v' as source and target
            graph = nx.from_pandas_edgelist(
                gdf,
                source="u",
                target="v",
                edge_attr=True,
                create_using=nx.MultiDiGraph()
            )
            logger.info(f"{network_type} graph extracted: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
            return graph
        except Exception as e:
            logger.error(f"Failed to extract {network_type} graph: {str(e)}")
            raise e
    
    def _relabel_nodes(self, graph, mode_suffix):
        """
        Relabel nodes to include mode suffix
        
        Args:
            graph: The graph to relabel
            mode_suffix: Suffix to add to node names
            
        Returns:
            nx.MultiDiGraph: Graph with relabeled nodes
        """
        logger.info(f"Relabeling nodes for {mode_suffix} mode...")
        return nx.relabel_nodes(graph, lambda n: f"{n}_{mode_suffix}")
    
    def _add_mode_attributes(self, graph, mode, speed_kmh):
        """
        Add mode and time attributes to edges
        
        Args:
            graph: The graph to modify
            mode: The transportation mode
            speed_kmh: Speed in km/h
        """
        logger.info(f"Adding attributes for {mode} mode...")
        
        for u, v, key, data in graph.edges(data=True, keys=True):
            # Add mode attribute
            data['mode'] = mode
            
            # Calculate travel time in minutes
            if 'length' in data:
                # Convert length from meters to km, then calculate time
                distance_km = data['length'] / 1000
                time_hours = distance_km / speed_kmh
                time_minutes = time_hours * 60
                data['time'] = time_minutes
            else:
                # Fallback time
                data['time'] = 1.0
                
            # Set weight for shortest path algorithm
            data['weight'] = data['time']
    
    def _add_interlayer_edges(self, merged_graph, walk_graph, bike_graph, car_graph):
        """
        Add transfer edges between different transportation modes
        
        Args:
            merged_graph: The merged graph to add edges to
            walk_graph: Walking graph
            bike_graph: Biking graph
            car_graph: Car graph
        """
        logger.info("Adding interlayer transfer edges...")
        
        # Build lookup for node positions
        node_positions = {}
        
        for mode_graph, suffix in [(walk_graph, '_walk'), (bike_graph, '_bike'), (car_graph, '_car')]:
            for node_id, node_data in mode_graph.nodes(data=True):
                if 'y' in node_data and 'x' in node_data:
                    node_positions[node_id] = (node_data['y'], node_data['x'])
        
        # Add transfer edges between nodes within 10 meters
        transfer_edges_added = 0
        max_transfer_distance = 10  # meters
        
        for node1, pos1 in node_positions.items():
            for node2, pos2 in node_positions.items():
                if node1 == node2:
                    continue
                
                # Skip if same original OSM node (different modes)
                original_id1 = node1.split('_')[0]
                original_id2 = node2.split('_')[0]
                
                if original_id1 == original_id2:
                    # Same original node, add transfer edge with minimal cost
                    merged_graph.add_edge(
                        node1, node2, 
                        weight=0.5, 
                        time=0.5, 
                        mode='transfer',
                        length=0
                    )
                    transfer_edges_added += 1
                    continue
                
                # Check if nodes are within transfer distance
                distance = geodesic(pos1, pos2).meters
                if distance <= max_transfer_distance:
                    # Add bidirectional transfer edges
                    transfer_time = 2.0  # 2 minutes transfer time
                    
                    merged_graph.add_edge(
                        node1, node2,
                        weight=transfer_time,
                        time=transfer_time,
                        mode='transfer',
                        length=distance
                    )
                    merged_graph.add_edge(
                        node2, node1,
                        weight=transfer_time,
                        time=transfer_time,
                        mode='transfer',
                        length=distance
                    )
                    transfer_edges_added += 2
        
        logger.info(f"Added {transfer_edges_added} transfer edges")
    
    def get_graph_stats(self):
        """
        Get statistics about the built graph
        
        Returns:
            dict: Graph statistics
        """
        if self.graph is None:
            return {"error": "Graph not built yet"}
        
        # Count nodes and edges by mode
        mode_stats = {}
        for u, v, data in self.graph.edges(data=True):
            mode = data.get('mode', 'unknown')
            if mode not in mode_stats:
                mode_stats[mode] = 0
            mode_stats[mode] += 1
        
        return {
            "total_nodes": len(self.graph.nodes),
            "total_edges": len(self.graph.edges),
            "edges_by_mode": mode_stats,
            "is_directed": self.graph.is_directed(),
            "is_multigraph": self.graph.is_multigraph()
        }