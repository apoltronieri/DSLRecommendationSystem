import time
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import urllib.parse
import logging

from config import (
    TIMEOUT,
    RETRIES,
    PER_PAGE,
    MAX_PAGES,
    SAVE_EVERY,
    CACHE_FILE,
    DATASET_FILE,
    CB_FAILURE_THRESHOLD,
    CB_RECOVERY_TIME,
)

logging.basicConfig(level=logging.INFO)

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN não encontrado.")

HEADERS = {"Authorization": f"token {TOKEN}"}

cb_state = "closed"
cb_failures = 0
cb_last_failure_time = None


def circuit_breaker_allow():
    global cb_state, cb_last_failure_time

    if cb_state == "closed":
        return True

    if cb_state == "open":
        if time.time() - cb_last_failure_time >= CB_RECOVERY_TIME:
            cb_state = "half-open"
            return True
        return False

    if cb_state == "half-open":
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


def handle_rate_limit(response):
    if "X-RateLimit-Remaining" in response.headers:
        remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
        if remaining <= 1:
            reset_ts = int(response.headers.get("X-RateLimit-Reset", time.time() + 5))
            wait = max(reset_ts - int(time.time()), 1)
            logging.warning(f"Rate limit reached. Waiting {wait}s")
            time.sleep(wait)


def robust_get(url, headers=None, params=None, retries=RETRIES, timeout=TIMEOUT):
    global cb_state

    if not circuit_breaker_allow():
        time.sleep(2)
        raise RuntimeError("Circuit breaker open.")

    attempt = 0

    while attempt < retries:
        try:

            resp = requests.get(url, headers=headers, params=params, timeout=timeout)

            if resp.status_code == 429:
                handle_rate_limit(resp)

            if resp.status_code >= 500:
                raise requests.exceptions.RequestException()

            circuit_breaker_on_success()
            return resp

        except requests.exceptions.RequestException:

            attempt += 1
            time.sleep(2**attempt)
            circuit_breaker_on_failure()

    raise RuntimeError("Failure after multiple attempts.")


QUERY = {
    "mps": {
        "queries": [
            "structure.mps in:path",
            "behavior.mps in:path",
            "typesystem.mps in:path",
            "constraints.mps in:path",
            "editor.mps in:path",
            "jetbrains.mps in:file",
            "languages/ in:path",
            "models/ in:path",
            "language:mps jetbrains mps",
            "extension:mps mps",
            "extension:mpl jetbrains",
        ],
    },
}

found_models = []


def search_repositories_with_pagination(query, per_page, max_pages):

    url = "https://api.github.com/search/repositories"
    all_items = []

    for page in range(1, max_pages + 1):

        params = {"q": query, "per_page": per_page, "page": page}

        r = robust_get(url, headers=HEADERS, params=params)

        if r.status_code != 200:
            break

        data = r.json()
        items = data.get("items", [])

        if not items:
            break

        all_items.extend(items)

        if len(items) < per_page:
            break

    return all_items


def get_total_commits(owner, repo_name):

    url = f"https://api.github.com/repos/{owner}/{repo_name}/commits"

    r = robust_get(url, headers=HEADERS, params={"per_page": 1})

    if r.status_code != 200:
        return 0

    link = r.headers.get("Link", "")

    if 'rel="last"' in link:

        last_part = [part for part in link.split(",") if 'rel="last"' in part][0]

        last_url = last_part[last_part.find("<") + 1 : last_part.find(">")]

        parsed = urllib.parse.urlparse(last_url)

        params = urllib.parse.parse_qs(parsed.query)

        return int(params["page"][0])

    return len(r.json())


def get_contributors_count(owner, repo):

    url = f"https://api.github.com/repos/{owner}/{repo}/contributors"

    total = 0
    page = 1

    while True:

        r = robust_get(url, headers=HEADERS, params={"per_page": 100, "page": page})

        if r.status_code != 200:
            break

        data = r.json()

        if not data:
            break

        total += len(data)
        page += 1

    return total


def get_last_commit_date(owner, repo):

    url = f"https://api.github.com/repos/{owner}/{repo}/commits"

    r = robust_get(url, headers=HEADERS, params={"per_page": 1})

    if r.status_code != 200:
        return None

    data = r.json()

    if not data:
        return None

    return data[0]["commit"]["committer"]["date"]


def get_first_commit_date(owner, repo):

    url = f"https://api.github.com/repos/{owner}/{repo}/commits"

    r = robust_get(url, headers=HEADERS, params={"per_page": 1})

    if r.status_code != 200:
        return None

    link = r.headers.get("Link", "")

    if 'rel="last"' in link:

        last_url = [part for part in link.split(",") if 'rel="last"' in part][0]

        last_url = last_url[last_url.find("<") + 1 : last_url.find(">")]

        parsed = urllib.parse.urlparse(last_url)

        params = urllib.parse.parse_qs(parsed.query)

        last_page = int(params["page"][0])

        r_last = robust_get(
            url, headers=HEADERS, params={"per_page": 1, "page": last_page}
        )

        if r_last.status_code != 200:
            return None

        data = r_last.json()

        if data:
            return data[0]["commit"]["committer"]["date"]

        return None

    data = r.json()

    if data:
        return data[-1]["commit"]["committer"]["date"]

    return None


def is_mps_repo(tree):

    has_mps = False
    has_mpl_or_msd = False

    for item in tree:

        path = item["path"]

        if path.endswith(".mps"):
            has_mps = True

        if path.endswith(".mpl") or path.endswith(".msd"):
            has_mpl_or_msd = True

        if "/languages/" in path and path.endswith("structure.mps"):
            return True

    return has_mps and has_mpl_or_msd


def is_potential_model_repo(owner, repo_name, framework):

    tree_url = (
        f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/HEAD?recursive=1"
    )

    response = robust_get(tree_url, headers=HEADERS)

    if response.status_code != 200:
        return False

    tree = response.json().get("tree", [])

    if framework == "mps":
        return is_mps_repo(tree)

    return False


def load_cache():

    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    return {}


def save_cache(cache):

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def finding_dsl_models(cache):

    for framework, cfg in QUERY.items():

        logging.info(f"Framework: {framework}")

        for query in cfg["queries"]:

            logging.info(f"Searching: {query}")

            items = search_repositories_with_pagination(query, PER_PAGE, MAX_PAGES)

            logging.info(f"Repos returned: {len(items)}")

            for repo in items:

                owner = repo["owner"]["login"]
                name = repo["name"]

                repo_id = f"{owner}/{name}"

                last_push = repo["pushed_at"]

                if repo_id in cache and cache[repo_id] == last_push:
                    continue

                if not is_potential_model_repo(owner, name, framework):
                    continue

                model_info = {
                    "owner": owner,
                    "name": name,
                    "description": repo.get("description") or "No description",
                    "stars": repo.get("stargazers_count", 0),
                    "url": repo["html_url"],
                    "found_at": datetime.now().isoformat(),
                    "query": query,
                    "total_commits": get_total_commits(owner, name),
                    "contributors": get_contributors_count(owner, name),
                    "last_commit": get_last_commit_date(owner, name),
                    "first_commit": get_first_commit_date(owner, name),
                }

                found_models.append(model_info)

                cache[repo_id] = last_push

                logging.info(f"{owner}/{name} - stars {model_info['stars']}")

                if len(found_models) % SAVE_EVERY == 0:

                    with open(DATASET_FILE, "w") as f:
                        json.dump(found_models, f, indent=2)

                    logging.info(f"Saved intermediate results ({len(found_models)})")


if __name__ == "__main__":

    cache = load_cache()

    finding_dsl_models(cache)

    save_cache(cache)

    logging.info(f"Total models found: {len(found_models)}")

    found_models.sort(key=lambda x: x["stars"], reverse=True)

    for i, model in enumerate(found_models[:5]):
        logging.info(
            f"{i+1}. {model['owner']}/{model['name']} - {model['stars']} stars"
        )

    with open(DATASET_FILE, "w") as f:
        json.dump(found_models, f, indent=2)
