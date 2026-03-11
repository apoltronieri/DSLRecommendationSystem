import time
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import urllib.parse

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN não encontrado.")

HEADERS = {
    "Authorization": f"token {TOKEN}"
}

TIMEOUT = 10

# Circuit Breaker
CB_FAILURE_THRESHOLD = 5
CB_RECOVERY_TIME = 30
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
            time.sleep(wait)


def robust_get(url, headers=None, params=None, retries=5, timeout=10):
    global cb_state

    if not circuit_breaker_allow():
        time.sleep(2)
        raise RuntimeError("Circuit breaker aberto.")

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
            time.sleep(2 ** attempt)
            circuit_breaker_on_failure()

    raise RuntimeError("Falha persistente após múltiplas tentativas.")


FRAMEWORKS = {
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
    "xtext": {
        "queries": [
            "extension:xtext src in:path",
            "src/main/xtext in:path",
            "domainmodel.xtext in:path",
            "statechart.xtext in:path",
            "generate mwe2 in:file",
            "workflow.mwe2 in:path",
            "xtend \"grammar\" in:file",
            "extension:xtext \"grammar\"",
            "\"org.eclipse.xtext\" in:file",
            "xtext grammar language",
        ],
    },
    "emf": {
        "queries": [
            "model in:path extension:ecore",
            "model in:path extension:genmodel",
            "ecore \"model\" in:file",
            "extension:ecore plugin.xml in:path",
            "extension:ecore",
            "extension:genmodel",
            "\"org.eclipse.emf\" in:file",
        ],
    },
    "antlr": {
        "queries": [
            "grammar in:file extension:g4",
            "antlr4 in:readme",
            "parser rule in:file extension:g4",
            "lexer rule in:file extension:g4",
            "extension:g4",
            "extension:g \"grammar\"",
            "\"org.antlr\" in:file",
        ],
    },
    "langium": {
        "queries": [
            "src/grammar in:path extension:langium",
            "langium \"dsl\" in:file",
            "extension:langium grammar in:file",
            "langium \"grammar\" in:file",
            "extension:langium",
            "\"langium\" in:package.json",
        ],
    },
}

found_models = []

def search_repositories_with_pagination(query, per_page=100, max_pages=5):
    url = "https://api.github.com/search/repositories"
    all_items = []

    for page in range(1, max_pages + 1):
        params = {"q": query, "per_page": per_page, "page": page}
        r = robust_get(url, headers=HEADERS, params=params, timeout=TIMEOUT)

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
    r = robust_get(url, headers=HEADERS, params={"per_page": 1}, timeout=TIMEOUT)

    if r.status_code != 200:
        return 0

    link = r.headers.get("Link", "")
    if 'rel="last"' in link:
        last_part = [l for l in link.split(",") if 'rel="last"' in l][0]
        last_url = last_part[last_part.find("<")+1:last_part.find(">")]
        parsed = urllib.parse.urlparse(last_url)
        params = urllib.parse.parse_qs(parsed.query)
        return int(params["page"][0])

    return len(r.json())


def get_contributors_count(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
    total = 0
    page = 1

    while True:
        r = robust_get(url, headers=HEADERS, params={"per_page": 100, "page": page}, timeout=TIMEOUT)

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
    r = robust_get(url, headers=HEADERS, params={"per_page": 1}, timeout=TIMEOUT)

    if r.status_code != 200:
        return None

    data = r.json()
    if not data:
        return None

    return data[0]["commit"]["committer"]["date"]


def get_first_commit_date(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    r = robust_get(url, headers=HEADERS, params={"per_page": 1}, timeout=TIMEOUT)

    if r.status_code != 200:
        return None

    link = r.headers.get("Link", "")
    if 'rel="last"' in link:
        last_url = [l for l in link.split(",") if "rel=\"last\"" in l][0]
        last_url = last_url[last_url.find("<")+1:last_url.find(">")]
        parsed = urllib.parse.urlparse(last_url)
        params = urllib.parse.parse_qs(parsed.query)
        last_page = int(params["page"][0])

        r_last = robust_get(url, headers=HEADERS, params={"per_page": 1, "page": last_page}, timeout=TIMEOUT)
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


def is_xtext_repo(tree):
    has_xtext_grammar = False
    has_mwe2_or_plugin = False

    for item in tree:
        path = item["path"]
        if path.endswith(".xtext"):
            has_xtext_grammar = True
        if path.endswith(".mwe2") or "plugin.xml" in path:
            has_mwe2_or_plugin = True
    return has_xtext_grammar and has_mwe2_or_plugin


def is_emf_repo(tree):
    has_ecore = False
    has_genmodel = False

    for item in tree:
        if item["path"].endswith(".ecore"):
            has_ecore = True
        if item["path"].endswith(".genmodel"):
            has_genmodel = True
    return has_ecore and has_genmodel


def is_antlr_repo(tree):
    for item in tree:
        if item["path"].endswith(".g4") or item["path"].endswith(".g"):
            return True
    return False


def is_langium_repo(tree):
    for item in tree:
        if item["path"].endswith(".langium"):
            return True
    return False


def is_potential_model_repo(owner, repo_name, framework):
    tree_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/HEAD?recursive=1"
    response = robust_get(tree_url, headers=HEADERS, timeout=TIMEOUT)

    if response.status_code != 200:
        return False

    tree = response.json().get("tree", [])

    if framework == "mps":
        return is_mps_repo(tree)
    if framework == "xtext":
        return is_xtext_repo(tree)
    if framework == "emf":
        return is_emf_repo(tree)
    if framework == "antlr":
        return is_antlr_repo(tree)
    if framework == "langium":
        return is_langium_repo(tree)

    return False


def finding_dsl_models():
    quantity = 100
    max_pages = 3

    for framework, cfg in FRAMEWORKS.items():
        print(f"\n=== Framework: {framework} ===")
        for query in cfg["queries"]:
            print(f"Searching: {query}")

            items = search_repositories_with_pagination(query, per_page=quantity, max_pages=max_pages)
            print(f"  Raw repos returned for this query: {len(items)}")

            for repo in items:
                owner = repo["owner"]["login"]
                name = repo["name"]

                if not is_potential_model_repo(owner, name, framework):
                    continue

                model_info = {
                    "owner": owner,
                    "name": name,
                    "framework": framework,
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

                print(f"  {owner}/{name} [{framework}]")
                print(f"     Stars: {model_info['stars']}")
                print(f"     URL: {model_info['url']}")
                print(" ˚º˚º˚º˚º˚º˚º˚")


def remove_duplicates():
    global found_models
    seen = set()
    unique = []

    for model in found_models:
        repo_id = f"{model['owner']}/{model['name']}"
        if repo_id not in seen:
            seen.add(repo_id)
            unique.append(model)

    found_models = unique


if __name__ == "__main__":
    finding_dsl_models()
    remove_duplicates()

    print(f"\nTotal models found: {len(found_models)}")

    found_models.sort(key=lambda x: x["stars"], reverse=True)

    print("\nBy star number:")
    for i, model in enumerate(found_models[:5]):
        print(f"{i+1}. {model['owner']}/{model['name']} [{model['framework']}] - {model['stars']} stars")

    with open("dsl_models_found.json", "w") as f:
        json.dump(found_models, f, indent=2)