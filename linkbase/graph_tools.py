from typing import List, Tuple, Dict, Any, Optional
from linkbase.db_tools import execute_sql, get_node_by_name, _normalize_text
from linkbase.logger_config import app_logger

def get_all_nodes_and_edges() -> Tuple[Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]]:
    nodes_data = []
    edges_data = []
    sql_nodes = "SELECT id, name, label FROM nodes;"
    nodes_result = execute_sql(sql_nodes, [])
    if isinstance(nodes_result, list):
        for row in nodes_result:
            nodes_data.append({"id": row[0], "name": row[1], "label": row[2]})
    elif isinstance(nodes_result, str): 
        app_logger.error(f"Error fetching nodes: {nodes_result}")
        return None, None
    sql_edges = "SELECT id, source_id, target_id, label FROM edges;"
    edges_result = execute_sql(sql_edges, [])
    if isinstance(edges_result, list):
        for row in edges_result:
            edges_data.append({"id": row[0], "source_id": row[1], "target_id": row[2], "label": row[3]})
    elif isinstance(edges_result, str): 
        app_logger.error(f"Error fetching edges: {edges_result}")
        return nodes_data, None
    return nodes_data, edges_data

def generate_dot_graph() -> Optional[str]:
    nodes, edges = get_all_nodes_and_edges()
    if nodes is None:
        app_logger.error("Cannot generate DOT graph: failed to fetch nodes.")
        return None
    dot_lines = ["digraph KnowledgeGraph {", "  rankdir=LR; // Left to Right layout"]
    for node in nodes:
        node_id_str = f"n{node['id']}"
        node_label_text = node['name'] # DOT still uses name + label
        if node.get('label'):
            node_label_text += f"\\n({node['label']})" 
        dot_lines.append(f'  {node_id_str} [label="{node_label_text}"];')
    if edges: 
        for edge in edges:
            source_node_id_str = f"n{edge['source_id']}"
            target_node_id_str = f"n{edge['target_id']}"
            edge_label = edge.get('label', '')
            dot_lines.append(f'  {source_node_id_str} -> {target_node_id_str} [label="{edge_label}"];')
    dot_lines.append("}")
    app_logger.info("DOT graph string generated successfully.")
    return "\\n".join(dot_lines)

def generate_mermaid_graph() -> Optional[str]:
    nodes, edges = get_all_nodes_and_edges()
    if nodes is None:
        app_logger.error("Cannot generate Mermaid graph: failed to fetch nodes.")
        return None
    mermaid_lines = ["graph TD;"] 
    for node in nodes:
        node_mermaid_id = f"N{node['id']}"
        node_display_text = node.get('label') if node.get('label') else node['name'] # Prioritize label
        mermaid_lines.append(f'  {node_mermaid_id}["{node_display_text}"];')
    if edges: 
        for edge in edges:
            source_mermaid_id = f"N{edge['source_id']}"
            target_mermaid_id = f"N{edge['target_id']}"
            edge_label = edge.get('label', '')
            if edge_label:
                mermaid_lines.append(f'  {source_mermaid_id} --"{edge_label}"--> {target_mermaid_id};')
            else:
                mermaid_lines.append(f'  {source_mermaid_id} --> {target_mermaid_id};')
    app_logger.info("Mermaid graph string generated successfully.")
    return "\\n".join(mermaid_lines)

def get_node_centric_data(center_node_name: str, depth: int = 1) -> Tuple[Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]]:
    normalized_center_name = _normalize_text(center_node_name)
    if not normalized_center_name:
        app_logger.error("Center node name cannot be empty for node-centric graph.")
        return None, None, None
    center_node = get_node_by_name(normalized_center_name) 
    if not center_node:
        app_logger.warning(f"Center node '{normalized_center_name}' not found.")
        return None, None, None
    center_node_id = center_node['id']
    app_logger.info(f"Fetching data for graph centered on node ID {center_node_id} ('{normalized_center_name}') up to depth {depth}.")
    collected_nodes_map: Dict[int, Dict[str, Any]] = {center_node_id: center_node}
    collected_edges_map: Dict[int, Dict[str, Any]] = {}
    queue: List[Tuple[int, int]] = [(center_node_id, 0)]
    visited_nodes_for_bfs = {center_node_id} 
    head = 0
    while head < len(queue):
        current_bfs_node_id, current_depth = queue[head]; head += 1
        if current_depth >= depth: continue
        sql_out_edges = "SELECT id, source_id, target_id, label FROM edges WHERE source_id = ?;"
        out_edges_res = execute_sql(sql_out_edges, [str(current_bfs_node_id)])
        if isinstance(out_edges_res, list):
            for row in out_edges_res:
                edge = {"id": row[0], "source_id": row[1], "target_id": row[2], "label": row[3]}
                if edge['id'] not in collected_edges_map: collected_edges_map[edge['id']] = edge
                collected_nodes_map.setdefault(edge['target_id'], {}) 
                if edge['target_id'] not in visited_nodes_for_bfs:
                    visited_nodes_for_bfs.add(edge['target_id']); queue.append((edge['target_id'], current_depth + 1))
        sql_in_edges = "SELECT id, source_id, target_id, label FROM edges WHERE target_id = ?;"
        in_edges_res = execute_sql(sql_in_edges, [str(current_bfs_node_id)])
        if isinstance(in_edges_res, list):
            for row in in_edges_res:
                edge = {"id": row[0], "source_id": row[1], "target_id": row[2], "label": row[3]}
                if edge['id'] not in collected_edges_map: collected_edges_map[edge['id']] = edge
                collected_nodes_map.setdefault(edge['source_id'], {}) 
                if edge['source_id'] not in visited_nodes_for_bfs:
                    visited_nodes_for_bfs.add(edge['source_id']); queue.append((edge['source_id'], current_depth + 1))
    if collected_nodes_map:
        node_ids_to_fetch = [nid for nid in collected_nodes_map.keys() if not collected_nodes_map[nid] or nid == center_node_id]
        node_ids_to_fetch = list(set(node_ids_to_fetch))
        if node_ids_to_fetch:
            placeholders = ', '.join(['?'] * len(node_ids_to_fetch))
            sql_nodes_details = f"SELECT id, name, label FROM nodes WHERE id IN ({placeholders});"
            nodes_details_res = execute_sql(sql_nodes_details, [str(nid) for nid in node_ids_to_fetch])
            if isinstance(nodes_details_res, list):
                for row in nodes_details_res: collected_nodes_map[row[0]] = {"id": row[0], "name": row[1], "label": row[2]}
            else: app_logger.error(f"Error fetching details for collected nodes: {nodes_details_res}")
    final_edges = list(collected_edges_map.values())
    final_nodes = [node_data for node_data in collected_nodes_map.values() if node_data.get('name')]
    return center_node, final_edges, final_nodes

def generate_node_centric_dot_graph(center_node_name: str, depth: int = 1) -> Optional[str]:
    center_node, edges, graph_nodes = get_node_centric_data(center_node_name, depth)
    normalized_name_for_title = _normalize_text(center_node_name) if center_node_name else "unknown_node"
    if not center_node:
        app_logger.warning(f"Center node '{center_node_name}' (normalized: {normalized_name_for_title}) not found for DOT graph generation.")
        return f"// Error: Center node '{center_node_name}' not found."
    if graph_nodes is None: 
        app_logger.error(f"Cannot generate DOT graph: graph_nodes data is None for center node '{center_node_name}'.")
        return f"// Error: Could not retrieve complete graph data for center node '{center_node_name}'."
    dot_lines = [f"digraph NodeCentric_{normalized_name_for_title}_depth{depth} {{", "  rankdir=LR;"]
    for node in graph_nodes:
        node_id_str = f"n{node['id']}"
        node_label_text = node['name'] # DOT still uses name + label
        if node.get('label'): node_label_text += f"\\n({node['label']})"
        if node['id'] == center_node['id']:
            dot_lines.append(f'  {node_id_str} [label="{node_label_text}", style=filled, fillcolor=lightblue];')
        else: dot_lines.append(f'  {node_id_str} [label="{node_label_text}"];')
    if edges:
        for edge in edges:
            source_node_id_str = f"n{edge['source_id']}"; target_node_id_str = f"n{edge['target_id']}"
            edge_label = edge.get('label', ''); dot_lines.append(f'  {source_node_id_str} -> {target_node_id_str} [label="{edge_label}"];')
    dot_lines.append("}")
    app_logger.info(f"Node-centric DOT graph for '{center_node_name}' (depth {depth}) generated successfully.")
    return "\\n".join(dot_lines)

def generate_node_centric_mermaid_graph(center_node_name: str, depth: int = 1) -> Optional[str]:
    center_node, edges, graph_nodes = get_node_centric_data(center_node_name, depth)
    normalized_name_for_title = _normalize_text(center_node_name) if center_node_name else "unknown_node"
    if not center_node:
        app_logger.warning(f"Center node '{center_node_name}' (normalized: {normalized_name_for_title}) not found for Mermaid graph generation.")
        return f"%% Error: Center node '{center_node_name}' not found. %%"
    if graph_nodes is None:
        app_logger.error(f"Cannot generate Mermaid graph: graph_nodes data is None for center node '{center_node_name}'.")
        return f"%% Error: Could not retrieve complete graph data for center node '{center_node_name}'. %%"
    mermaid_lines = ["graph TD;"]
    for node in graph_nodes:
        node_mermaid_id = f"N{node['id']}"
        node_display_text = node.get('label') if node.get('label') else node['name'] # Prioritize label
        mermaid_lines.append(f'  {node_mermaid_id}["{node_display_text}"];')
        if node['id'] == center_node['id']:
            mermaid_lines.append(f'  style {node_mermaid_id} fill:#ADD8E6,stroke:#333,stroke-width:2px;')
    if edges:
        for edge in edges:
            source_mermaid_id = f"N{edge['source_id']}"; target_mermaid_id = f"N{edge['target_id']}"
            edge_label = edge.get('label', '')
            if edge_label: mermaid_lines.append(f'  {source_mermaid_id} --"{edge_label}"--> {target_mermaid_id};')
            else: mermaid_lines.append(f'  {source_mermaid_id} --> {target_mermaid_id};')
    app_logger.info(f"Node-centric Mermaid graph for '{center_node_name}' (depth {depth}) generated successfully.")
    return "\\n".join(mermaid_lines)

def _find_all_paths_bfs(start_node_id: int, end_node_id: int, max_depth: int = 5) -> List[List[Dict[str, Any]]]:
    app_logger.info(f"Finding paths from node {start_node_id} to {end_node_id} (max_depth={max_depth}).")
    paths = []
    queue: List[Tuple[int, List[Dict[str, Any]], set[int]]] = [(start_node_id, [], {start_node_id})]
    while queue:
        current_node_id, path_edges, visited_in_path = queue.pop(0)
        if len(path_edges) >= max_depth: continue
        sql_outgoing_edges = "SELECT id, source_id, target_id, label FROM edges WHERE source_id = ?;"
        edges_result = execute_sql(sql_outgoing_edges, [str(current_node_id)])
        if isinstance(edges_result, list):
            for row in edges_result:
                edge = {"id": row[0], "source_id": row[1], "target_id": row[2], "label": row[3]}
                neighbor_node_id = edge["target_id"]
                if neighbor_node_id == end_node_id:
                    paths.append(path_edges + [edge])
                elif neighbor_node_id not in visited_in_path:
                    new_visited = visited_in_path.copy(); new_visited.add(neighbor_node_id)
                    queue.append((neighbor_node_id, path_edges + [edge], new_visited))
        elif isinstance(edges_result, str): app_logger.error(f"Error fetching edges for node {current_node_id} during pathfinding: {edges_result}")
    app_logger.info(f"Found {len(paths)} paths from {start_node_id} to {end_node_id}.")
    return paths

def get_path_graph_data(start_node_name: str, end_node_name: str, max_depth: int = 5) -> Tuple[Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]], Optional[int], Optional[int]]:
    norm_start_name = _normalize_text(start_node_name); norm_end_name = _normalize_text(end_node_name)
    if not norm_start_name or not norm_end_name: return None, None, None, None
    start_node_obj = get_node_by_name(norm_start_name); end_node_obj = get_node_by_name(norm_end_name)
    if not start_node_obj: return None, None, None, None
    if not end_node_obj: return None, None, start_node_obj['id'] if start_node_obj else None, None
    start_id = start_node_obj['id']; end_id = end_node_obj['id']
    all_paths_edges = _find_all_paths_bfs(start_id, end_id, max_depth)
    if not all_paths_edges:
        nodes_to_fetch_ids = {start_id, end_id}; nodes_in_paths_list = []
        if nodes_to_fetch_ids:
            placeholders = ', '.join(['?'] * len(nodes_to_fetch_ids))
            sql_nodes = f"SELECT id, name, label FROM nodes WHERE id IN ({placeholders});"
            nodes_result = execute_sql(sql_nodes, [str(nid) for nid in nodes_to_fetch_ids])
            if isinstance(nodes_result, list):
                for row in nodes_result: nodes_in_paths_list.append({"id": row[0], "name": row[1], "label": row[2]})
        return nodes_in_paths_list, [], start_id, end_id
    unique_node_ids_in_paths = {start_id, end_id}; unique_edges_in_paths_map: Dict[int, Dict[str, Any]] = {}
    for path in all_paths_edges:
        for edge in path:
            unique_node_ids_in_paths.add(edge['source_id']); unique_node_ids_in_paths.add(edge['target_id'])
            if edge['id'] not in unique_edges_in_paths_map: unique_edges_in_paths_map[edge['id']] = edge
    edges_in_paths_list = list(unique_edges_in_paths_map.values()); nodes_in_paths_list = []
    if unique_node_ids_in_paths:
        placeholders = ', '.join(['?'] * len(unique_node_ids_in_paths))
        sql_nodes = f"SELECT id, name, label FROM nodes WHERE id IN ({placeholders});"
        nodes_result = execute_sql(sql_nodes, [str(nid) for nid in unique_node_ids_in_paths])
        if isinstance(nodes_result, list):
            for row in nodes_result: nodes_in_paths_list.append({"id": row[0], "name": row[1], "label": row[2]})
        elif isinstance(nodes_result, str): return None, edges_in_paths_list, start_id, end_id
    return nodes_in_paths_list, edges_in_paths_list, start_id, end_id

def generate_paths_dot_graph(start_node_name: str, end_node_name: str, max_depth: int = 5) -> Optional[str]:
    nodes, edges, start_id, end_id = get_path_graph_data(start_node_name, end_node_name, max_depth)
    norm_start = _normalize_text(start_node_name) or "unk_start"; norm_end = _normalize_text(end_node_name) or "unk_end"
    if nodes is None: return f"// Error: Could not fetch data for path graph between '{start_node_name}' and '{end_node_name}'. Ensure nodes exist."
    if not edges:
        s_found = any(n['id'] == start_id for n in nodes) if start_id else False; e_found = any(n['id'] == end_id for n in nodes) if end_id else False
        err = "No paths found"
        if not s_found and not e_found: err = f"Start '{start_node_name}' & end '{end_node_name}' not found."
        elif not s_found: err = f"Start node '{start_node_name}' not found."
        elif not e_found: err = f"End node '{end_node_name}' not found."
        else: err = f"No paths between '{start_node_name}' & '{end_node_name}' (depth {max_depth})."
        return f"digraph PathErr_{norm_start}_to_{norm_end} {{ error_node [label=\"{err.replace('\"', '')}\", shape=box]; }}"
    lines = [f"digraph Path_{norm_start}_to_{norm_end} {{", "  rankdir=LR;"]
    for n in nodes:
        attrs = [f'label="{n["name"]}{f"\\n({n["label"]})" if n.get("label") else ""}']
        if n['id'] == start_id: attrs.append("style=filled, fillcolor=lightgreen")
        elif n['id'] == end_id: attrs.append("style=filled, fillcolor=lightcoral")
        lines.append(f"  n{n['id']} [{', '.join(attrs)}];")
    for e in edges: lines.append(f"  n{e['source_id']} -> n{e['target_id']} [label=\"{e.get('label', '')}\"];")
    lines.append("}"); return "\\n".join(lines)

def generate_paths_mermaid_graph(start_node_name: str, end_node_name: str, max_depth: int = 5) -> Optional[str]:
    nodes, edges, start_id, end_id = get_path_graph_data(start_node_name, end_node_name, max_depth)
    if nodes is None: return f"%% Error: Could not fetch data for path graph between '{start_node_name}' and '{end_node_name}'. Ensure nodes exist. %%"
    if not edges:
        s_found = any(n['id'] == start_id for n in nodes) if start_id else False; e_found = any(n['id'] == end_id for n in nodes) if end_id else False
        err = "No paths found"
        if not s_found and not e_found: err = f"Start '{start_node_name}' & end '{end_node_name}' not found."
        elif not s_found: err = f"Start node '{start_node_name}' not found."
        elif not e_found: err = f"End node '{end_node_name}' not found."
        else: err = f"No paths between '{start_node_name}' & '{end_node_name}' (depth {max_depth})."
        return f"graph TD;\\n  error_node[\"{err.replace('\"', '').replace("'", '')}\"];" # Sanitize
    lines = ["graph TD;"]
    for n in nodes:
        display = n.get('label') if n.get('label') else n['name'] # Prioritize label
        lines.append(f"  N{n['id']}[\"{display}\"];")
        if n['id'] == start_id: lines.append(f"  style N{n['id']} fill:#90EE90,stroke:#333,stroke-width:2px;")
        elif n['id'] == end_id: lines.append(f"  style N{n['id']} fill:#F08080,stroke:#333,stroke-width:2px;")
    for e in edges:
        lbl = e.get('label', '')
        lines.append(f"  N{e['source_id']} {'--\"'+lbl+'\"-->' if lbl else '-->'} N{e['target_id']};")
    return "\\n".join(lines)

# if __name__ == '__main__':
    # ...
