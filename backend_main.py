from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend_router import get_multimodal_route
from backend_multimodal_graph import MultimodalGraphBuilder
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Multimodal Smart City Routing API",
    description="AI-Powered routing system for walking, biking, and driving",
    version="1.0.0"
)

# Enable CORS for all origins (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variable to store the graph
G = None

@app.on_event("startup")
async def startup_event():
    """Initialize the multimodal graph on startup"""
    global G
    logger.info("Starting up the Multimodal Routing System...")
    
    try:
        # Use the externally downloaded OSM PBF file for the graph (now loaded with Pyrosm)
        osm_file = "../noord-holland-latest.osm.pbf"  # Path relative to backend/
        graphml_path = "amsterdam.graphml"  # Optional: cache as GraphML
        logger.info(f"Loading multimodal graph from OSM PBF file: {osm_file}")
        graph_builder = MultimodalGraphBuilder(osm_file=osm_file, graphml_path=graphml_path, network_type="drive")
        G = graph_builder.build()
        logger.info(f"Graph built/loaded successfully with {len(G.nodes)} nodes and {len(G.edges)} edges")
    except Exception as e:
        logger.error(f"Failed to build graph: {str(e)}")
        raise e

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Multimodal Smart City Routing API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "route": "/route?start_lat=52.370&start_lon=4.880&end_lat=52.380&end_lon=4.890"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "graph_loaded": G is not None,
        "nodes": len(G.nodes) if G else 0,
        "edges": len(G.edges) if G else 0
    }

@app.get("/route")
async def get_route(
    start_lat: float = Query(..., description="Start latitude", ge=-90, le=90),
    start_lon: float = Query(..., description="Start longitude", ge=-180, le=180),
    end_lat: float = Query(..., description="End latitude", ge=-90, le=90),
    end_lon: float = Query(..., description="End longitude", ge=-180, le=180)
):
    """
    Calculate multimodal route between two points
    
    Returns:
        - total_time: Total travel time in minutes
        - total_cost: Total cost in ৳
        - segments: List of route segments with mode, coordinates, time, and cost
    """
    
    # Check if graph is loaded
    if G is None:
        raise HTTPException(
            status_code=503, 
            detail="Graph not loaded. Please wait for system initialization."
        )
    
    try:
        logger.info(f"Calculating route from ({start_lat}, {start_lon}) to ({end_lat}, {end_lon})")
        
        # Get the multimodal route
        route_data = get_multimodal_route(G, start_lat, start_lon, end_lat, end_lon)
        
        logger.info(f"Route calculated: {route_data['total_time']} minutes, {route_data['total_cost']} ৳")
        
        return route_data
        
    except Exception as e:
        logger.error(f"Error calculating route: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error calculating route: {str(e)}"
        )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

if __name__ == "__main__":
    uvicorn.run(
        "backend_main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )