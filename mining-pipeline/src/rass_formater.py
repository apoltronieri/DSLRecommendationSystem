import json
import os
from dotenv import load_dotenv

load_dotenv()

# HF_TOKEN removido — não era usado em nenhuma linha deste arquivo
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN não encontrado")


FRAMEWORK_MAP = {
    "mps": {
        "artifact_type": "DSL",
        "modeling_ecosystem": "JetBrains MPS",  # typo corrigido: ecossystem → ecosystem
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
        domain = gem.get("domain", "unknown")
        purpose = gem.get("purpose", "unknown")
        return domain, purpose
    except Exception:
        return "unknown", "unknown"


def build_rass(saida_path, enriched_path):
    # classifier_path removido da assinatura — os campos que vinha dele
    # (classification, artifacts_detected, framework_detected) nunca eram
    # produzidos pelo repo_analyzer.py, então o map sempre retornava "unknown"/[]
    # Se no futuro você adicionar um classificador real, reintroduza o parâmetro.

    with open(saida_path, "r") as f:
        base_repos = json.load(f)

    with open(enriched_path, "r") as f:
        enriched = json.load(f)

    enriched_map = {f'{c["owner"]}/{c["name"]}': c for c in enriched}

    # o pipeline é MPS-only, então cfg nunca vai ser None aqui,
    # mas mantemos a guarda por robustez caso FRAMEWORK_MAP seja expandido
    cfg = FRAMEWORK_MAP["mps"]

    assets = []

    for repo in base_repos:
        repo_id = f'{repo["owner"]}/{repo["name"]}'

        domain, purpose = infer_domain_purpose_from_gemini(repo_id, enriched_map)

        asset = {
            "ArtifactID": repo_id,
            "ArtifactType": cfg["artifact_type"],
            "ModelingEcosystem": cfg["modeling_ecosystem"],
            "ConformsTo": cfg["conforms_to"],
            "View": cfg["abstraction"],
            "FileFormats": cfg["file_format"],
            "ToolRequired": cfg["modeling_ecosystem"],
            "Domain": domain,
            "Purpose": purpose,
            "Owner": repo["owner"],
            "RepositoryURL": repo["url"],
            "EngagementMetrics": {
                "Commits": repo.get("commits_count", 0),
                "Contributors": repo.get("contributors_count", 0),
                "Stars": repo.get("stars", 0),
                "CreatedAt": repo.get("created_at"),
                "LastCommitDate": repo.get("last_commit_date"),
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
        enriched_path="analyzed_repos_enriched.json",
    )
    save_rass(assets, "rass++.json")
