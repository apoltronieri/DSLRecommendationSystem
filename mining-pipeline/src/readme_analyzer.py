import requests
import base64
import json
from google import genai
from urllib.parse import urlparse
import os
import glob
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import time

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
output_file = f"dataset/analyzed_repos_enriched_{timestamp}.json"

load_dotenv(Path(__file__).parent.parent.parent / ".env")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN2")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def setup_gemini():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY not found in environment.")
    return genai.Client(api_key=key)


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


def analyze_with_gemini(client, readme_content):
    prompt = f"""
Act as an expert in Software Engineering and Model-Driven Engineering (MDE). Analyze the README below.

Your task is to classify this repository into ONE of the categories listed below, strictly based on the information provided in the README.

Choose exactly one value for the field 'artifact_type':
1. "dsl": If the focus is language definition, language workbenches, Xtext, MPS, Langium, DSL engineering.
2. "tutorial": If the repository is intended for teaching, examples, demos, quickstarts, or samples.
3. "libraries": If it is a reusable library, runtime, core framework, API, or plugin set.
4. "parser": If the core focus is pure grammar definition, ANTLR grammar, lexer rules, parser rules.
5. "metamodel": If the focus is defining abstract data structures, metamodels, Ecore models.
6. "other": If none of the above categories apply.

Return a STRICT JSON object with no markdown, no code fences, no extra text — only the JSON:
{{
    "domain": "MDE area (e.g., Transformation, Syntax, Validation, Parsing, Metamodeling, etc.)",
    "purpose": "One-sentence summary describing the repository's goal",
    "artifact_type": "ONE_OF_THE_ALLOWED_CATEGORIES",
    "justification": "Short explanation of why this category was selected"
}}

--- README ---
{readme_content[:30000]}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt  # era gemini-2.5-pro
        )
        return response.text
    except Exception as e:
        print(f"Gemini error: {e}")
        return None


if __name__ == "__main__":
    print("Starting automated analysis...")

    client = setup_gemini()

    files = sorted(glob.glob("dataset/analyzed_repos_[0-9]*.json"))
    if not files:
        raise FileNotFoundError("No analyzed_repos file found in dataset/")

    input_file = files[-1]
    print(f"Reading from: {input_file}")

    with open(input_file, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        repos = data
    else:
        repos = []
        for tier_repos in data.values():
            repos.extend(tier_repos)

    for repo in repos:
        url = repo["url"]
        print(f"Processing: {url}")

        try:
            readme = get_github_readme(url)
            analysis = analyze_with_gemini(client, readme)
            repo["gemini_analysis"] = analysis
            time.sleep(4)
        except Exception as e:
            repo["gemini_analysis"] = {"error": str(e)}
            continue

    output_file = f"dataset/analyzed_repos_enriched_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(repos, f, indent=4, ensure_ascii=False)

    print(f"Process completed. Output saved to {output_file}.")
