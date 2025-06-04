import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse # Added PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import sys

# Add project root to sys.path to allow imports from linkbase module
# This assumes web_server.py is in the linkbase directory, and linkbase is in the project root.
# For robust path handling, consider project structure and how this script is run.
# If 'linkbase' is the root of the package:
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# If web_server.py is inside 'linkbase' and 'linkbase' is the package:
# No special sys.path manipulation needed if run with `python -m linkbase.web_server` from project root.
# However, for direct execution `python linkbase/web_server.py`, we might need to adjust.
# Assuming for now that it's run in a way that `linkbase.graph_tools` etc. are discoverable.
# If running from project root: `python -m linkbase.web_server`
# If running directly: `python linkbase/web_server.py` (might need sys.path adjustment above)

try:
    from linkbase.graph_tools import (
        get_all_nodes_and_edges,
        get_node_centric_data,
        get_path_graph_data
        # Mermaid generation will now happen client-side
    )
    from linkbase.db_tools import initialize_database # _normalize_text not directly used here
    from linkbase.logger_config import app_logger
except ImportError as e:
    # This fallback is for cases where the script might be run directly
    # and the parent directory isn't automatically in sys.path.
    print(f"Initial ImportError: {e}. Attempting to adjust sys.path.")
    # One level up to access 'linkbase' as a package from within 'linkbase' dir
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    print(f"Adjusted sys.path: {sys.path}")
    # Ensure this block imports the same data-fetching functions as the try block
    from linkbase.graph_tools import (
        get_all_nodes_and_edges,
        get_node_centric_data,
        get_path_graph_data
    )
    from linkbase.db_tools import initialize_database # _normalize_text not used here by web_server
    from linkbase.logger_config import app_logger


app = FastAPI()

# Ensure database is initialized on startup
initialize_database()
app_logger.info("Database initialized by web_server.py on startup.")

# --- Pydantic Models for Request/Response (Optional but good practice) ---
class GraphParams(BaseModel):
    center_node: Optional[str] = None
    start_node: Optional[str] = None
    end_node: Optional[str] = None
    max_depth: Optional[int] = 5 # For pathfinding

class NodeInfo(BaseModel):
    id: int
    name: str
    label: Optional[str] = None

class EdgeInfo(BaseModel):
    id: int
    source_id: int
    target_id: int
    label: Optional[str] = None

class GraphDataResponse(BaseModel):
    nodes: List[NodeInfo]
    edges: List[EdgeInfo]
    # Optional fields for context, like which node was centered or path start/end
    center_node_id: Optional[int] = None
    start_node_id: Optional[int] = None
    end_node_id: Optional[int] = None
    error_message: Optional[str] = None


# --- API Endpoints ---
@app.get("/api/graph", response_model=GraphDataResponse) # Changed response model
async def get_graph_data_endpoint(
    center_node: Optional[str] = None,
    start_node: Optional[str] = None,
    end_node: Optional[str] = None,
    # 'depth' is used for node-centric, 'max_depth' for pathfinding.
    # FastAPI will map query param 'depth' to this if present, else default.
    # For pathfinding, we use 'max_depth' as the parameter name.
    # For node-centric, we'll use 'depth' as the parameter name.
    # Let's rename max_depth to path_max_depth for clarity and add a new 'depth' for node-centric.
    path_max_depth: int = 5, 
    node_centric_depth: int = 1 
):
    """
    Generates and returns a Mermaid graph string.
    - If center_node is provided, a node-centric graph is generated up to node_centric_depth.
    - If start_node and end_node are provided, a path graph is generated up to path_max_depth.
    - Otherwise, the full graph is generated.
    """
    app_logger.info(
        f"API /api/graph called with: center='{center_node}', start='{start_node}', "
        f"end='{end_node}', node_centric_depth={node_centric_depth}, path_max_depth={path_max_depth}"
    )
    
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    
    # Variables to pass context to the frontend if needed (e.g. for highlighting)
    response_center_node_id: Optional[int] = None
    response_start_node_id: Optional[int] = None
    response_end_node_id: Optional[int] = None
    error_msg: Optional[str] = None

    if center_node:
        # get_node_centric_data returns (center_node_obj, edges_list, nodes_list)
        center_node_obj, edges_list, nodes_list = get_node_centric_data(center_node, depth=node_centric_depth)
        if center_node_obj:
            nodes = nodes_list
            edges = edges_list
            response_center_node_id = center_node_obj['id']
        else:
            error_msg = f"Center node '{center_node}' not found."
            nodes, edges = [], [] # Return empty lists on error
    elif start_node and end_node:
        # get_path_graph_data returns (nodes_list, edges_list, start_node_id, end_node_id)
        nodes_list, edges_list, s_id, e_id = get_path_graph_data(start_node, end_node, max_depth=path_max_depth)
        if nodes_list is not None: # Can be empty list if nodes found but no path
            nodes = nodes_list
            edges = edges_list if edges_list is not None else []
            response_start_node_id = s_id
            response_end_node_id = e_id
            if not edges_list and (s_id and e_id): # Nodes found but no path
                 error_msg = f"No paths found between '{start_node}' and '{end_node}' (max depth {path_max_depth})."
            elif not s_id or not e_id:
                 error_msg = f"One or both path nodes ('{start_node}', '{end_node}') not found."
                 nodes, edges = [], []
        else: # nodes_list is None, critical error in fetching
            error_msg = f"Error fetching data for path between '{start_node}' and '{end_node}'."
            nodes, edges = [], []
    else:
        nodes, edges = get_all_nodes_and_edges()

    if nodes is None: # Should generally not happen if logic above is correct, but as a fallback
        app_logger.error("Fallback: Nodes data is None.")
        nodes = []
        error_msg = error_msg or "Failed to fetch node data."
    if edges is None:
        app_logger.info("Edges data is None, defaulting to empty list.")
        edges = []
        # error_msg = error_msg or "Failed to fetch edge data." # Less critical if nodes are present

    return GraphDataResponse(
        nodes=[NodeInfo(**n) for n in nodes], 
        edges=[EdgeInfo(**e) for e in edges],
        center_node_id=response_center_node_id,
        start_node_id=response_start_node_id,
        end_node_id=response_end_node_id,
        error_message=error_msg
    )

@app.get("/api/nodes", response_model=List[NodeInfo])
async def get_nodes_for_dropdown():
    """
    Returns a list of all nodes for populating dropdowns in the UI.
    """
    nodes_data, _ = get_all_nodes_and_edges()
    if nodes_data is None:
        app_logger.error("Failed to fetch nodes for dropdown.")
        raise HTTPException(status_code=500, detail="Failed to fetch node list.")
    
    # Sort nodes by normalized name for consistent dropdown order
    # The 'name' field in nodes_data is already normalized as per db_tools.get_or_create_node
    sorted_nodes = sorted(nodes_data, key=lambda x: x.get('name', '').lower())
    return sorted_nodes


# --- HTML Serving ---
# Create a 'templates' directory in the same directory as web_server.py
# and place graph_view.html inside it.
# For simplicity, we'll define HTML content directly here first, then move to a file.

HTML_CONTENT_PATH = os.path.join(os.path.dirname(__file__), "templates", "graph_view.html")

@app.get("/", response_class=HTMLResponse)
async def serve_graph_page():
    # This will be replaced by serving an HTML file.
    # For now, keeping it simple.
    # Ensure the 'templates' directory exists at the same level as web_server.py
    # e.g., your_project_root/linkbase/web_server.py
    # your_project_root/linkbase/templates/graph_view.html
    
    # Create templates directory if it doesn't exist
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        app_logger.info(f"Created templates directory: {templates_dir}")

    # The actual HTML content will be in graph_view.html (next step)
    # This endpoint will read and return that file.
    # For now, a placeholder if file doesn't exist.
    if os.path.exists(HTML_CONTENT_PATH):
        with open(HTML_CONTENT_PATH, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        placeholder_html = """
        <!DOCTYPE html><html><head><title>Graph Placeholder</title></head>
        <body><h1>Graph View HTML not found</h1><p>Please create linkbase/templates/graph_view.html</p></body></html>
        """
        app_logger.warning(f"HTML file not found at {HTML_CONTENT_PATH}. Serving placeholder.")
        return HTMLResponse(content=placeholder_html)

# --- Main Execution ---
if __name__ == "__main__":
    app_logger.info("Starting FastAPI server for Linkbase graph display.")
    # Ensure the templates directory and a basic graph_view.html exist for testing.
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    if not os.path.exists(HTML_CONTENT_PATH):
        with open(HTML_CONTENT_PATH, "w") as f:
            f.write("<!DOCTYPE html><html><head><title>Graph Loading...</title></head><body><h1>Loading graph...</h1><p>If this persists, graph_view.html might be misconfigured.</p></body></html>")
            app_logger.info(f"Created placeholder {HTML_CONTENT_PATH}")
            
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
