import json
import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN não encontrado")

if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN não encontrado")


FRAMEWORK_MAP = {
    "mps": {
        "artifact_type": "DSL",
        "modeling_ecossystem": "JetBrains MPS",
        "conforms_to": "MPS Metamodeling Environment",
        "abstraction": "PIM",
        "file_format": [".mps", ".mpl", ".msd"],
    }
}


def infer_domain_purpose_from_gemini(repo_id, enriched_map):
    enriched = enriched_map.get(repo_id)

    if not enriched:
        return "unknown", "unknown"

    gemini_raw = enriched.get("gemini_analysis", "")

    if isinstance(gemini_raw, str):
        gemini_raw = gemini_raw.replace("```json", "").replace("```", "").strip()

    try:
        gem = json.loads(gemini_raw)
        dominio = gem.get("domain", "unknown")
        proposito = gem.get("purpose", "unknown")
        return dominio, proposito
    except Exception:
        return "unknown", "unknown"


def build_rass(saida_path, classifier_path, enriched_path):
    with open(saida_path, "r") as f:
        base_repos = json.load(f)

    with open(classifier_path, "r") as f:
        classified = json.load(f)

    with open(enriched_path, "r") as f:
        enriched = json.load(f)

    classified_map = {f'{c["owner"]}/{c["name"]}': c for c in classified}
    enriched_map = {f'{c["owner"]}/{c["name"]}': c for c in enriched}

    assets = []

    for repo in base_repos:
        repo_id = f'{repo["owner"]}/{repo["name"]}'
        fw = repo["framework"]

        cfg = FRAMEWORK_MAP.get(fw)
        if not cfg:
            continue

        extra = classified_map.get(repo_id, {})

        domain, purpose = infer_domain_purpose_from_gemini(repo_id, enriched_map)

        asset = {
            "ArtifactID": repo_id,
            "ArtifactType": cfg["artifact_type"],
            "ModelingEcosystem": cfg["modeling_ecossystem"],
            "ConformsTo": cfg["conforms_to"],
            "View": cfg["abstraction"],
            "FileFormats": cfg["file_format"],
            "ToolRequired": cfg["modeling_ecossystem"],
            "Domain": domain,
            "Purpose": purpose,
            "Owner": repo["owner"],
            "RepositoryURL": repo["url"],
            "EngagementMetrics": {
                "Commits": repo["commits_count"],
                "Contributors": repo["contributors_count"],
                "Stars": repo.get("stars", 0),
                "CreatedAt": repo["created_at"],
                "LastCommitDate": repo["last_commit_date"],
            },
            "AdditionalInsights": {
                "ClassifierCategory": extra.get("classification", "unknown"),
                "DetectedArtifacts": extra.get("artifacts_detected", []),
                "FrameworkDetected": extra.get("framework_detected", "unknown"),
            },
            "Description": repo.get("description", ""),
        }

        assets.append(asset)

    return assets


def save_rass(assets, filename):
    with open(filename, "w") as f:
        json.dump(assets, f, indent=4)
    print(f"[OK] RASS++ salvo em {filename}")


if __name__ == "__main__":
    assets = build_rass(
        saida_path="rass.json",
        classifier_path="analyzed_repos.json",
        enriched_path="analyzed_repos_enriched.json",
    )
    save_rass(assets, "rass++.json")
