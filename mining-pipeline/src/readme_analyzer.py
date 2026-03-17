import requests
import base64
import json
import google.generativeai as genai
from urllib.parse import urlparse
import os

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN2")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def setup_gemini():
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel("gemini-2.5-flash")


def extract_repo_info(url):
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub URL.")
    return parts[0], parts[1]


def get_github_readme(repo_url):
    owner, repo = extract_repo_info(repo_url)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"

    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        return base64.b64decode(data["content"]).decode("utf-8")
    elif response.status_code == 404:
        raise Exception("README not found.")
    else:
        raise Exception(f"GitHub Error: {response.status_code}")


def analyze_with_gemini(readme_content):
    model = setup_gemini()

    prompt = f"""
Act as an expert in Software Engineering and Model-Driven Engineering (MDE). Analyze the README below.

Your task is to classify this repository into ONE of the categories listed below, strictly based on the information provided in the README.

**Allowed Categories (Choose exactly one for the field 'tipo_artefato'):**
1. "dsl": If the focus is language definition, language workbenches, Xtext, MPS, Langium, DSL engineering.
2. "tutorial": If the repository is intended for teaching, examples, demos, quickstarts, or samples.
3. "libraries": If it is a reusable library, runtime, core framework, API, or plugin set.
4. "parser": If the core focus is pure grammar definition, ANTLR grammar, lexer rules, parser rules.
5. "metamodelo": If the focus is defining abstract data structures, metamodels, Ecore models.
6. "outro": If none of the above categories apply.

Return a STRICT JSON object with the following keys:
{{
    "domain": "MDE area (e.g., Transformation, Syntax, Validation, Parsing, Metamodeling, etc.)",
    "purpose": "One-sentence summary describing the repository’s goal",
    "artifact_type": "ONE_OF_THE_ALLOWED_CATEGORIES",
    "justification": "Short explanation of why this category was selected"
}}

--- README ---
{readme_content[:30000]}
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return None


if __name__ == "__main__":
    print("Starting automated analysis...")

    with open("analyzed_repos.json", "r") as f:
        repos = json.load(f)

    for repo in repos:
        url = repo["url"]
        print(f"Processing: {url}")

        try:
            readme = get_github_readme(url)
            analysis = analyze_with_gemini(readme)
            repo["gemini_analysis"] = analysis
        except Exception as e:
            repo["gemini_analysis"] = {"error": str(e)}
            continue

    with open("analyzed_repos_enriched.json", "w") as f:
        json.dump(repos, f, indent=4, ensure_ascii=False)

    print("Process completed. Output saved to classified_output_enriched.json.")
