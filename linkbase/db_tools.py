import sqlite3
import os
from typing import Tuple, List, Union, Optional # Added Optional
from linkbase.logger_config import app_logger

DB_FILE = "linkbase.db" # Define the database file name

def initialize_database():
    """
    Checks if the SQLite database exists. If not, creates it with
    the 'nodes' and 'edges' tables.
    """
    db_exists = os.path.exists(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if not db_exists:
        # Create Nodes table
        cursor.execute("""
        CREATE TABLE nodes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE NOT NULL,
          label TEXT
        );
        """)

        # Create Edges table
        cursor.execute("""
        CREATE TABLE edges (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_id INTEGER NOT NULL,
          target_id INTEGER NOT NULL,
          label TEXT,
          FOREIGN KEY(source_id) REFERENCES nodes(id),
          FOREIGN KEY(target_id) REFERENCES nodes(id),
          UNIQUE(source_id, target_id, label) -- Ensure unique edges for a given label
        );
        """)
        
        conn.commit()
        app_logger.info(f"Database '{DB_FILE}' created with 'nodes' and 'edges' tables (edges.label is case-sensitive for uniqueness).")
    else:
        app_logger.info(f"Database '{DB_FILE}' already exists.")

    conn.close()

def get_db_schema():
    """
    Retrieves the schema of the SQLite database.

    Returns:
        A string containing the SQL CREATE statements for all tables
        in the database, or an error message string if an exception occurs.
    """
    conn = None
    try:
        app_logger.info(f"Retrieving schema for database '{DB_FILE}'.")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cursor.fetchall()
        
        if not tables:
            app_logger.info("No tables found in the database.")
            return "No tables found in the database."

        schema_str = f"Database Schema for '{DB_FILE}':\n\n"
        for table_name, sql_create_statement in tables:
            schema_str += f"-- Schema for table: {table_name}\n"
            schema_str += f"{sql_create_statement};\n\n"
            
            # Get column info for each table (optional, but good for more detail)
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            schema_str += f"  -- Columns for {table_name}:\n"
            for col in columns:
                # col structure: (cid, name, type, notnull, dflt_value, pk)
                schema_str += f"  --   {col[1]} {col[2]}{' NOT NULL' if col[3] else ''}{' PRIMARY KEY' if col[5] else ''}\n"
            schema_str += "\n"

        return schema_str.strip()

    except sqlite3.Error as e:
        app_logger.error(f"SQLite error while retrieving schema for '{DB_FILE}': {e}")
        return f"SQLite error while retrieving schema: {e}"
    except Exception as e:
        app_logger.error(f"Unexpected error while retrieving schema for '{DB_FILE}': {e}")
        return f"An unexpected error occurred while retrieving schema: {e}"
    finally:
        if conn:
            conn.close()

def execute_sql(sql_command: str, params: Optional[List[str]] = None) -> Union[List[Tuple], int, str]:  
    """
    Executes an arbitrary SQL command against the SQLite database.

    Args:
        sql_command: The SQL command string to execute.
        params: An optional list of string parameters to use with the SQL command. Defaults to None.

    Returns:
        A list of tuples containing the results for SELECT queries,
        the number of affected rows for DML queries (INSERT, UPDATE, DELETE),
        or an error message string if an exception occurs.
    """
    conn = None
    try:
        # If params is None, use an empty list for the database call.
        db_params = params if params is not None else []
        app_logger.debug(f"Executing SQL on '{DB_FILE}': {sql_command} with params: {db_params}")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute(sql_command, db_params)

        # For SELECT statements, fetch and return results
        if sql_command.strip().upper().startswith("SELECT"):
            results = cursor.fetchall()
            conn.commit() # Commit even for SELECT in case of any implicit changes or functions
            app_logger.info(f"SELECT query executed successfully on '{DB_FILE}'. Rows returned: {len(results)}")
            return results
        else:
            # For DML statements (INSERT, UPDATE, DELETE, etc.), commit and return row count
            affected_rows = cursor.rowcount
            conn.commit()
            app_logger.info(f"DML query executed successfully on '{DB_FILE}'. Rows affected: {affected_rows}")
            return affected_rows
    except sqlite3.Error as e:
        app_logger.error(f"SQLite error executing SQL on '{DB_FILE}': {sql_command} - {e}")
        if conn:
            conn.rollback() # Rollback changes if an error occurs
        return f"SQLite error: {e}"
    except Exception as e:
        app_logger.error(f"Unexpected error executing SQL on '{DB_FILE}': {sql_command} - {e}")
        if conn:
            conn.rollback()
        return f"An unexpected error occurred: {e}"
    finally:
        if conn:
            conn.close()

def _normalize_text(text: Optional[str]) -> Optional[str]:
    """Basic text normalization: lowercase and strip whitespace."""
    if text is None:
        return None
    return text.lower().strip()

def get_node_by_name(name: str) -> Optional[dict]:
    """Retrieves a node by its normalized name."""
    normalized_name = _normalize_text(name)
    if not normalized_name:
        app_logger.warning("Attempted to get node with empty or None name.")
        return None
        
    # Use LOWER() for case-insensitive matching on the 'name' column.
    # normalized_name is already lowercased by _normalize_text.
    sql = "SELECT id, name, label FROM nodes WHERE LOWER(name) = ?"
    result = execute_sql(sql, [normalized_name])
    if isinstance(result, list) and result:
        node_data = result[0]
        return {"id": node_data[0], "name": node_data[1], "label": node_data[2]}
    elif isinstance(result, str): # Error message from execute_sql
        app_logger.error(f"Error in get_node_by_name for '{normalized_name}': {result}")
    return None

def get_or_create_node(name: str, label: Optional[str] = None) -> Optional[int]:
    """
    Retrieves a node by its normalized name. If it doesn't exist, creates it.
    Returns the node ID.
    Node names are stored normalized (lowercase, stripped).
    Labels are stored as provided but compared normalized if a node with the same name exists.
    """
    normalized_name = _normalize_text(name)
    normalized_label = _normalize_text(label) if label is not None else None

    if not normalized_name:
        app_logger.error("Cannot get or create node with empty or None name.")
        return None

    existing_node = get_node_by_name(normalized_name) # Uses normalized name

    if existing_node:
        app_logger.info(f"Node '{normalized_name}' found with ID {existing_node['id']}.")
        # Optionally, update label if provided and different (normalized comparison)
        if normalized_label is not None and _normalize_text(existing_node.get('label')) != normalized_label:
            app_logger.info(f"Updating label for node '{normalized_name}' from '{existing_node.get('label')}' to '{label}'.")
            update_sql = "UPDATE nodes SET label = ? WHERE id = ?"
            execute_sql(update_sql, [label, str(existing_node['id'])])  
        return existing_node['id']
    else:
        app_logger.info(f"Node '{normalized_name}' not found. Creating new node.")
        insert_sql = "INSERT INTO nodes (name, label) VALUES (?, ?)"
        result = execute_sql(insert_sql, [normalized_name, label]) 
        if isinstance(result, int) and result > 0:
            new_node_data = get_node_by_name(normalized_name)
            if new_node_data:
                app_logger.info(f"Node '{normalized_name}' created with ID {new_node_data['id']}.")
                return new_node_data['id']
            else:
                app_logger.error(f"Failed to retrieve newly created node '{normalized_name}'.")
                return None
        else:
            app_logger.error(f"Failed to create node '{normalized_name}'. execute_sql result: {result}")
            return None

def add_edge_if_not_exists(source_name: str, target_name: str, label: Optional[str] = None) -> Optional[int]:
    """
    Adds an edge between two nodes if it doesn't already exist with the same normalized label.
    Node names and edge labels are normalized for checking and storage where appropriate.
    Returns the edge ID if created or found, or None on error.
    """
    normalized_source_name = _normalize_text(source_name)
    normalized_target_name = _normalize_text(target_name)
    normalized_label = _normalize_text(label) # Normalize label for uniqueness check

    source_id = get_or_create_node(normalized_source_name) # Uses normalized name
    if source_id is None:
        app_logger.error(f"Could not get or create source node '{normalized_source_name}' for edge.")
        return None
    
    target_id = get_or_create_node(normalized_target_name) # Uses normalized name
    if target_id is None:
        app_logger.error(f"Could not get or create target node '{normalized_target_name}' for edge.")
        return None
    
    insert_sql = "INSERT OR IGNORE INTO edges (source_id, target_id, label) VALUES (?, ?, ?)"
    # Store original label
    result = execute_sql(insert_sql, [str(source_id), str(target_id), normalized_label])

    if isinstance(result, str) and "UNIQUE constraint failed" in result:
        app_logger.info(f"Edge from '{normalized_source_name}' to '{normalized_target_name}' with label '{label}' likely already exists due to UNIQUE constraint.")
        # Try to fetch the existing edge ID
        fetch_sql = "SELECT id FROM edges WHERE source_id = ? AND target_id = ? AND "
        fetch_params = [str(source_id), str(target_id)]
        if label is None:
            fetch_sql += "label IS NULL"
        else:
            fetch_sql += "label = ?"
            fetch_params.append(label)
        
        existing_edge_id_result = execute_sql(fetch_sql, fetch_params)
        if isinstance(existing_edge_id_result, list) and existing_edge_id_result:
            return existing_edge_id_result[0][0]
        return None # Could not fetch existing

    elif isinstance(result, int) and result > 0: 
        fetch_sql = "SELECT id FROM edges WHERE source_id = ? AND target_id = ? AND "
        fetch_params = [str(source_id), str(target_id)]
        if label is None: # Handle NULL labels in query
            fetch_sql += "label IS NULL"
        else:
            fetch_sql += "label = ?"
            fetch_params.append(label)

        new_edge_id_result = execute_sql(fetch_sql, fetch_params)
        if isinstance(new_edge_id_result, list) and new_edge_id_result:
            new_edge_id = new_edge_id_result[0][0]
            app_logger.info(f"Edge from '{normalized_source_name}' to '{normalized_target_name}' with label '{label}' created/found with ID {new_edge_id}.")
            return new_edge_id
        else:
            app_logger.warning(f"Edge from '{normalized_source_name}' to '{normalized_target_name}' with label '{label}' was inserted (or ignored), but could not retrieve its ID. This might happen if it was ignored and the fetch query is too strict.")
            # If INSERT OR IGNORE resulted in 0 affected rows (meaning it was ignored), we still try to fetch.
            # This path suggests the fetch failed.
            return None
            
    elif isinstance(result, int) and result == 0: # INSERT OR IGNORE did nothing, edge already exists
        app_logger.info(f"Edge from '{normalized_source_name}' to '{normalized_target_name}' with label '{label}' already exists (INSERT OR IGNORE).")
        fetch_sql = "SELECT id FROM edges WHERE source_id = ? AND target_id = ? AND "
        fetch_params = [str(source_id), str(target_id)]
        if label is None:
            fetch_sql += "label IS NULL"
        else:
            fetch_sql += "label = ?"
            fetch_params.append(label)
        
        existing_edge_id_result = execute_sql(fetch_sql, fetch_params)
        if isinstance(existing_edge_id_result, list) and existing_edge_id_result:
            return existing_edge_id_result[0][0]
        return None # Could not fetch existing

    else:
        app_logger.error(f"Failed to add edge from '{normalized_source_name}' to '{normalized_target_name}' with label '{label}'. execute_sql result: {result}")
        return None

if __name__ == '__main__':
    app_logger.info("Starting db_tools.py script for advanced demonstration.")
    initialize_database()
    
    app_logger.info("\n--- Demonstrating Node Creation/Retrieval ---")
    node1_id = get_or_create_node(" New York City ", "City")
    node2_id = get_or_create_node("new york city", "Location") # Same node, label might update
    node3_id = get_or_create_node("San Francisco", "City")
    node4_id = get_or_create_node("California", "State")
    
    app_logger.info(f"Node IDs: NYC1={node1_id}, NYC2={node2_id} (should be same), SF={node3_id}, CA={node4_id}")

    app_logger.info("\n--- Demonstrating Edge Creation/Retrieval ---")
    edge1_id = add_edge_if_not_exists("New York City", "USA", "is_in_country") # USA node will be created
    edge2_id = add_edge_if_not_exists("San Francisco", "California", "is_in_state")
    edge3_id = add_edge_if_not_exists("SAN FRANCISCO", "california", "IS_IN_STATE") # Should be same as edge2
    edge4_id = add_edge_if_not_exists("California", "USA", "is_in_country")
    edge5_id = add_edge_if_not_exists("New York City", "USA", "is_in_country") # Duplicate, should not create new
    edge_no_label_id = add_edge_if_not_exists("Test Node A", "Test Node B") # Edge with NULL label
    edge_no_label_id2 = add_edge_if_not_exists("test node a", "test node b") # Same as above

    app_logger.info(f"Edge IDs: E1={edge1_id}, E2={edge2_id}, E3={edge3_id} (should be same as E2), E4={edge4_id}, E5={edge5_id} (should be same as E1)")
    app_logger.info(f"Edge with no label ID1: {edge_no_label_id}, ID2: {edge_no_label_id2} (should be same)")

    app_logger.info("\n--- Final DB Schema ---")
    schema = get_db_schema()
    app_logger.info(f"Schema:\n{schema}")
    
    app_logger.info("\n--- All Nodes ---")
    all_nodes = execute_sql("SELECT * FROM nodes;", [])
    app_logger.info(f"Nodes: {all_nodes}")

    app_logger.info("\n--- All Edges ---")
    all_edges = execute_sql("SELECT * FROM edges;", [])
    app_logger.info(f"Edges: {all_edges}")

    app_logger.info("Finished db_tools.py script advanced demonstration.")
