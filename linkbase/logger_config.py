import logging
import os

LOG_FILE_NAME = "linkbase.log"
LOG_DIR = os.path.dirname(os.path.abspath(__file__)) # Logs in the same directory as this config
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

def setup_global_logger(log_level=logging.INFO):
    """
    Sets up the root logger to write to a file.
    This will capture logs from all modules using Python's standard logging.
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level) # Set the minimum level for the root logger

    # Prevent adding multiple handlers if already configured (e.g., by other parts of an app)
    # Check specifically for our file handler to avoid removing other desired handlers.
    # A more robust check might involve handler names or types if more complex setups are expected.
    has_our_file_handler = any(isinstance(h, logging.FileHandler) and h.baseFilename == LOG_FILE_PATH for h in root_logger.handlers)

    if not has_our_file_handler:
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # File Handler - writes logs to a file
        file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a') # Use 'a' to append
        file_handler.setLevel(log_level) # Set level for this handler
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Optionally, add a console handler to the root logger as well
        # console_handler = logging.StreamHandler()
        # console_handler.setLevel(logging.DEBUG) # Or your preferred console level
        # console_handler.setFormatter(formatter)
        # root_logger.addHandler(console_handler)
        
        root_logger.info(f"Global file logger initialized. Logging to: {LOG_FILE_PATH}")
    else:
        root_logger.info(f"Global file logger to {LOG_FILE_PATH} seems to be already configured.")

    return root_logger # Return the configured root logger

# Configure the global logger when this module is imported.
# Any module can then get a logger instance via logging.getLogger(__name__)
# and its messages (at or above the root_logger's level) will be handled.
setup_global_logger()

# For specific application parts, you can still get a named logger.
# It will inherit handlers from the root logger.
app_logger = logging.getLogger('linkbase_app') # Example named logger

if __name__ == '__main__':
    # Demonstrate the logger
    # Logs from root (if setup_global_logger is called)
    logging.info("This is an info message from the root logger.")
    
    # Logs from our named application logger
    app_logger.info("Logger setup complete. This is an info message from app_logger.")
    app_logger.warning("This is a warning message from app_logger.")
    app_logger.error("This is an error message from app_logger.")
    app_logger.critical("This is a critical message from app_logger.")
    
    # Simulate a log from another library
    another_library_logger = logging.getLogger('another.library')
    another_library_logger.info("This is an info message from another.library.")
    
    print(f"Log messages should be in: {LOG_FILE_PATH}")
