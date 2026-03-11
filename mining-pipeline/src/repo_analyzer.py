import json
import time
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

class RepositoryInfo:
    def __init__(self, name, owner, framework, contributors_count, commits_count, created_at, description, url, last_commit_date):
        self.name = name
        self.owner = owner
        self.framework = framework
        self.contributors_count = contributors_count
        self.commits_count = commits_count
        self.created_at = created_at
        self.description = description
        self.url = url
        self.last_commit_date = last_commit_date

    def enrich_from_json(self, filename):
        print("[DEBUG] enrich_from_json INICIO")

        self.repositories = []

        try:
            print(f"[DEBUG] Lendo JSON: {filename}")
            with open(filename, "r") as f:
                data = json.load(f)
            print("[DEBUG] JSON carregado, quantidade de itens:", len(data))
        except Exception as e:
            print("[ERRO] Falha ao ler JSON:", repr(e))
            return

        for idx, item in enumerate(data, start=1):
            try:
                owner = item["owner"]
                name = item["name"]

                print(f"[DEBUG] ({idx}/{len(data)}) Carregando repo {owner}/{name} (SEM API)")

                repo = RepositoryInfo(
                    name=name,
                    owner=owner,
                    framework=item["framework"],
                    contributors_count=item.get("contributors", 0),
                    commits_count=item.get("total_commits", 0),
                    created_at=item.get("created_at", "1970-01-01T00:00:00Z"),
                    description=item.get("description", "No description"),
                    url=item.get("url", ""),
                    last_commit_date=item.get("last_commit", None)
                )

                repo.stars = item.get("stars", 0)

                print(f"[DEBUG] {owner}/{name} -> contrib:{repo.contributors_count}, commits:{repo.commits_count}, last:{repo.last_commit_date}")

                if repo.is_valid():
                    print(f"[DEBUG] Repo VALIDO: {owner}/{name}")
                    print(f"[DEBUG] SCORE deste repo: {repo._latest_score}")
                    self.repositories.append(repo)
                else:
                    print(f"[DEBUG] Repo INVALIDO: {owner}/{name} -> score={repo._latest_score}")

            except Exception as e:
                print(f"[ERRO] Problema ao processar {item.get('owner')}/{item.get('name')}: {repr(e)}")
                continue

        print("[DEBUG] enrich_from_json FIM. Total válidos:", len(self.repositories))

    def is_valid(self):
        if not self.last_commit_date or self.last_commit_date in ("Error", "No commits"):
            return False

        try:
            today = datetime.now()
            created_at = datetime.strptime(self.created_at, "%Y-%m-%dT%H:%M:%SZ")
            last_commit_date = datetime.strptime(self.last_commit_date, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return False

        days_last_commit = (today - last_commit_date).days
        score = 0

        stars = getattr(self, "stars", 0)

        if stars >= 500:
            score += 50
        elif stars >= 200:
            score += 40
        elif stars >= 100:
            score += 30
        elif stars >= 30:
            score += 20
        elif stars >= 10:
            score += 10

        if days_last_commit <= 90:
            score += 20
        elif days_last_commit <= 180:
            score += 15
        elif days_last_commit <= 365:
            score += 10
        elif days_last_commit <= 720:
            score += 5

        if self.contributors_count >= 5:
            score += 15
        elif self.contributors_count >= 3:
            score += 10
        elif self.contributors_count >= 2:
            score += 5
        elif self.contributors_count == 1:
            score += 2

        if self.commits_count >= 200:
            score += 15
        elif self.commits_count >= 100:
            score += 10
        elif self.commits_count >= 50:
            score += 5
        elif self.commits_count >= 10:
            score += 2

        self._latest_score = score
        return score >= 40

    def obj_to_dict(self):
        return {
            "name": self.name,
            "owner": self.owner,
            "framework": self.framework,
            "contributors_count": self.contributors_count,
            "commits_count": self.commits_count,
            "created_at": self.created_at,
            "last_commit_date": self.last_commit_date,
            "description": self.description,
            "url": self.url,
            "stars": getattr(self, "stars", 0)
        }
    
    def save_results_to_json(self, filename):
        with open(filename, 'w') as f:
            json.dump([r.obj_to_dict() for r in self.repositories], f, indent=4)
        print(f"Results saved to {filename}")


if __name__ == "__main__":
    print("[DEBUG] Entrou no main")

    analyzer = RepositoryInfo(
        name="", owner="", framework="", contributors_count=0, commits_count=0,
        created_at="2025-01-01T00:00:00Z", description="", url="", last_commit_date="2025-01-01T00:00:00Z"
    )

    print("[DEBUG] Chamando enrich_from_json")
    analyzer.enrich_from_json("dsl_models_found.json")

    print("\nValid repositories found:")
    print("[DEBUG] Repositórios válidos encontrados:", len(analyzer.repositories))
    for repo in analyzer.repositories:
        print(f"- {repo.name} | Owner: {repo.owner} | Framework: {repo.framework} | Commits: {repo.commits_count} | Contributors: {repo.contributors_count}")

    analyzer.save_results_to_json("saida.json")
