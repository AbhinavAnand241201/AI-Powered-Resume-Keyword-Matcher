import nltk
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Download required NLTK data
    logger.info("Downloading NLTK data...")
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('punkt_tab')
    nltk.download('averaged_perceptron_tagger')
    logger.info("NLTK data downloaded successfully!")
except Exception as e:
    logger.error(f"Error downloading NLTK data: {str(e)}")
    raise 