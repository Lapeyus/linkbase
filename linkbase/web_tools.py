import requests
from bs4 import BeautifulSoup
from linkbase.logger_config import app_logger

def get_text_from_url(url: str) -> str:
    """
    Fetches the plain text content of a webpage using requests and BeautifulSoup.
    
    Args:
        url: The URL of the webpage to fetch.
        
    Returns:
        The plain text content of the webpage, or an error message if fetching fails.
    """
    try:
        app_logger.info(f"Attempting to fetch text content from URL: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        app_logger.debug(f"Successfully fetched URL: {url}, status code: {response.status_code}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
            
        # Get text
        text = soup.get_text()
        
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        app_logger.info(f"Successfully extracted text content from URL: {url}")
        return text
    except requests.exceptions.RequestException as e:
        app_logger.error(f"Error fetching URL {url}: {e}")
        return f"Error fetching URL {url}: {e}"
    except Exception as e:
        app_logger.error(f"An unexpected error occurred while processing {url}: {e}")
        return f"An unexpected error occurred while processing {url}: {e}"
