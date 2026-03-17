import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN não encontrado.")

TIMEOUT = 10
RETRIES = 5

PER_PAGE = 100
MAX_PAGES = 3

SAVE_EVERY = 10

CACHE_FILE = "repo_cache.json"
DATASET_FILE = "dsl_models_found.json"

CB_FAILURE_THRESHOLD = 5
CB_RECOVERY_TIME = 30
