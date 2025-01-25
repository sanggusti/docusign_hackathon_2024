import os
from dotenv import load_dotenv

load_dotenv()

DS_CONFIG = {
    "account_id": os.getenv("DOCUSIGN_ACCOUNT_ID"),
    "base_path": os.getenv("DOCUSIGN_BASE_PATH"),
    "access_token": os.getenv("DOCUSIGN_ACCESS_TOKEN"),
    "return_url": os.getenv("APP_BASE_URL", "") + "/callback" if os.getenv("APP_BASE_URL") else None
}

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
LANCEDB_PATH = os.getenv("LANCEDB_PATH", "data/healthcare_db")