import time
import requests
import json
from datetime import datetime
import os
import logging
from logger import setup_logger

from config import (
    TIMEOUT,
    RETRIES,
    PER_PAGE,
    MAX_PAGES,
    CACHE_FILE,
    CB_FAILURE_THRESHOLD,
    CB_RECOVERY_TIME,
)

# urllib.parse removido — não era usado em lugar nenhum
# load_dotenv removido — config.py já faz isso e já valida o token

setup_logger()
logger = logging.getLogger(__name__)

# TOKEN lido de config.py via variável de ambiente, sem recarregar dotenv
TOKEN = os.getenv("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN não encontrado.")

HEADERS = {"Authorization": f"token {TOKEN}"}

cb_state = "closed"
cb_failures = 0
cb_last_failure_time = None

found_models = []


# =========================
# CIRCUIT BREAKER
# =========================
def circuit_breaker_allow():
    global cb_state, cb_last_failure_time

    if cb_state == "closed":
        return True

    if cb_state == "open":
        if time.time() - cb_last_failure_time >= CB_RECOVERY_TIME:
            cb_state = "half-open"
            return True
        return False

    return True


def circuit_breaker_on_success():
    global cb_state, cb_failures
    cb_state = "closed"
    cb_failures = 0


def circuit_breaker_on_failure():
    global cb_state, cb_failures, cb_last_failure_time
    cb_failures += 1

    if cb_failures >= CB_FAILURE_THRESHOLD:
        cb_state = "open"
        cb_last_failure_time = time.time()


# =========================
# REQUEST
# =========================
def robust_get(url, headers=None, params=None, retries=RETRIES, timeout=TIMEOUT):
    if not circuit_breaker_allow():
        time.sleep(2)
        raise RuntimeError("Circuit breaker open.")

    attempt = 0

    while attempt < retries:
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)

            # 429 = rate limit: o GitHub diz exatamente quanto esperar no header Retry-After
            # tratamos antes do bloco 5xx para não penalizar o circuit breaker
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited. Sleeping {retry_after}s")
                time.sleep(retry_after)
                attempt += 1
                continue

            # 5xx = instabilidade do servidor — esses sim penalizam o circuit breaker
            if resp.status_code >= 500:
                raise requests.exceptions.RequestException(
                    f"Server error {resp.status_code}"
                )

            # 4xx que não seja 429 (ex: 403 forbidden, 422 query inválida) são erros
            # do nosso lado — não penalizamos o circuit breaker, só logamos e retornamos
            if resp.status_code >= 400:
                logger.warning(f"Client error {resp.status_code} for {url}")
                circuit_breaker_on_success()  # infraestrutura OK, erro é nosso
                return resp

            circuit_breaker_on_success()
            return resp

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error: {e} | attempt={attempt}")
            attempt += 1
            time.sleep(2**attempt)
            circuit_breaker_on_failure()

    raise RuntimeError("Failure after multiple attempts.")


# =========================
# SEARCH
# =========================
QUERY = {
    "mps": {
        "queries": [
            "structure.mps in:path",
            "behavior.mps in:path",
            "typesystem.mps in:path",
            "constraints.mps in:path",
            "editor.mps in:path",
            "jetbrains.mps in:file",
            "extension:mps",
            "extension:mpl",
        ]
    }
}


def search_repositories_with_pagination(query):
    url = "https://api.github.com/search/repositories"
    all_items = []

    for page in range(1, MAX_PAGES + 1):
        try:
            r = robust_get(
                url,
                headers=HEADERS,
                params={"q": query, "per_page": PER_PAGE, "page": page},
            )

            if r.status_code != 200:
                continue

            data = r.json()
            items = data.get("items", [])

            if not items:
                break

            all_items.extend(items)

        except Exception as e:
            logger.warning(f"Search failed page {page}: {e}")
            continue

    return all_items


# =========================
# FILTER
# =========================
def is_potential_mps_repo(owner, repo_name):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/HEAD?recursive=1"

    try:
        r = robust_get(url, headers=HEADERS)
    except Exception as e:
        logger.warning(f"Skipping {owner}/{repo_name}: {e}")
        return False

    if r.status_code != 200:
        return False

    tree = r.json().get("tree", [])

    has_mps = False
    has_language_structure = False

    for item in tree:
        path = item["path"]

        if path.endswith(".mps"):
            has_mps = True

        if "/languages/" in path and path.endswith("structure.mps"):
            has_language_structure = True

    return has_language_structure or has_mps


def fetch_repo_metadata(owner, repo_name):
    base = f"https://api.github.com/repos/{owner}/{repo_name}"
    result = {
        "last_commit": None,
        "first_commit": None,
        "total_commits": 0,
        "contributors": 0,
        "description": None,
    }

    # descrição vem do endpoint do repo
    r = robust_get(f"{base}", headers=HEADERS)
    if r.status_code == 200:
        result["description"] = r.json().get("description")

    # último commit + estimativa de total via header Link
    r2 = robust_get(f"{base}/commits?per_page=1", headers=HEADERS)
    if r2.status_code == 200 and r2.json():
        result["last_commit"] = r2.json()[0]["commit"]["committer"]["date"]
        link = r2.headers.get("Link", "")
        import re

        match = re.search(r'page=(\d+)>; rel="last"', link)
        result["total_commits"] = int(match.group(1)) if match else 1

    # contributors via header Link
    r3 = robust_get(f"{base}/contributors?per_page=1&anon=true", headers=HEADERS)
    if r3.status_code == 200:
        link3 = r3.headers.get("Link", "")
        match3 = re.search(r'page=(\d+)>; rel="last"', link3)
        result["contributors"] = int(match3.group(1)) if match3 else len(r3.json())

    return result


# =========================
# CACHE
# =========================
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # JSONDecodeError = arquivo corrompido
            # OSError = permissão, disco cheio, etc.
            logger.warning("Cache file unreadable, starting fresh.")
            return {}
    return {}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


# =========================
# SAVE (CRÍTICO)
# =========================
def generate_filename():
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"dataset/dsl_models_found_{ts}.json"


def save_partial():
    filename = "dataset/_partial.json"

    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w") as f:
        json.dump(found_models, f, indent=2)

    logger.info(f"[CHECKPOINT] Saved partial: {len(found_models)}")


def save_final():
    filename = generate_filename()

    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w") as f:
        json.dump(found_models, f, indent=2)

    os.makedirs("dataset", exist_ok=True)

    with open("dataset/latest.json", "w") as f:
        json.dump({"latest": filename}, f)

    logger.info(f"[FINAL] Saved: {filename}")


# =========================
# PIPELINE
# =========================
def finding_dsl_models(cache):
    for framework, cfg in QUERY.items():

        for query in cfg["queries"]:
            logger.info(f"Searching: {query}")

            repos = search_repositories_with_pagination(query)

            for repo in repos:
                try:
                    owner = repo["owner"]["login"]
                    name = repo["name"]
                    repo_id = f"{owner}/{name}"

                    last_push = repo["pushed_at"]

                    if repo_id in cache and cache[repo_id] == last_push:
                        continue

                    if repo.get("size", 0) > 50000:
                        continue

                    # renomeado para deixar explícito que é validação MPS
                    if not is_potential_mps_repo(owner, name):
                        continue

                    meta = fetch_repo_metadata(owner, name)

                    model_info = {
                        "owner": owner,
                        "name": name,
                        "stars": repo.get("stargazers_count", 0),
                        "url": repo["html_url"],
                        "found_at": datetime.now().isoformat(),
                        "description": meta["description"],
                        "last_commit": meta["last_commit"],
                        "total_commits": meta["total_commits"],
                        "contributors": meta["contributors"],
                    }

                    found_models.append(model_info)
                    cache[repo_id] = last_push

                    if len(found_models) % 10 == 0:
                        save_partial()

                except Exception as e:
                    logger.warning(f"Error processing repo: {e}")
                    continue


# =========================
# MAIN (CRÍTICO)
# =========================
if __name__ == "__main__":
    logger.info("Starting DSL mining pipeline")

    cache = load_cache()

    try:
        finding_dsl_models(cache)

    except Exception as e:
        logger.error(f"PIPELINE FAILED: {e}")

    finally:
        save_cache(cache)
        save_final()
        logger.info(f"Total models: {len(found_models)}")
