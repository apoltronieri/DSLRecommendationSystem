import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN não encontrado.")

TIMEOUT = 10
RETRIES = 5

PER_PAGE = 100
MAX_PAGES = 10

SAVE_EVERY = 10

DATASET_FILE = "dataset/dsl_models_found.json"
CACHE_FILE = "mining-pipeline/cache/repos_seen.json"

CB_FAILURE_THRESHOLD = 5
CB_RECOVERY_TIME = 30
