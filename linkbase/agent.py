import os
import logging 
from google.adk.agents import LlmAgent
from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import LlmAgent
from .web_tools import get_text_from_url
from .db_tools import initialize_database, execute_sql, get_db_schema
from .graph_tools import generate_dot_graph, generate_mermaid_graph, generate_node_centric_dot_graph, generate_node_centric_mermaid_graph, generate_paths_dot_graph, generate_paths_mermaid_graph # Added path graph tools

# Get a logger for this module
# Since logger_config.py configures the root logger, this logger will inherit that config.
logger = logging.getLogger(__name__)

logger.info("Starting agent.py: Loading environment variables and initializing database.")
load_dotenv()
logger.debug(".env file loaded.")

initialize_database()  
try:
    root_agent = LlmAgent(
        # model=LiteLlm(model="ollama/qwen3:30b"),
        model='gemini-2.5-pro-preview-05-06',
        name='linkbase',
        instruction="You are an AI assistant that constructs a knowledge graph. Your primary role is to identify NLP entities (nodes) and infer their relationships (edges) from the overall context of provided text. You will process text, typically from URLs, extract these entities and relationships, and then store them in a structured database to build and expand the knowledge graph. Emphasize clarity in node/edge definitions and ensure connections accurately reflect the contextual meaning. You can generate full graph visualizations, visualizations centered on a specific node (showing its direct outgoing connections), or visualizations showing paths between two specified nodes (all in DOT or Mermaid format).",
        tools=[get_text_from_url, execute_sql, get_db_schema, generate_dot_graph, generate_mermaid_graph, generate_node_centric_dot_graph, generate_node_centric_mermaid_graph, generate_paths_dot_graph, generate_paths_mermaid_graph],
    )
except Exception as e:
    logger.error(f"Unexpected error': {e}")
