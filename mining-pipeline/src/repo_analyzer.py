import json
from datetime import datetime
from dotenv import load_dotenv
from logger import setup_logger
import logging

setup_logger()
logger = logging.getLogger(__name__)

load_dotenv()


class RepositoryInfo:
    def __init__(
        self,
        name,
        owner,
        description,
        stars,
        url,
        created_at,
        contributors_count,
        commits_count,
        last_commit_date,
    ):
        self.name = name
        self.owner = owner
        self.description = description
        self.stars = stars
        self.url = url
        self.contributors_count = contributors_count
        self.commits_count = commits_count
        self.created_at = created_at
        self.last_commit_date = last_commit_date

    def is_valid(self):
        if not self.last_commit_date or self.last_commit_date in (
            "Error",
            "No commits",
        ):
            return False

        try:
            today = datetime.now()
            last_commit_date = datetime.strptime(
                self.last_commit_date, "%Y-%m-%dT%H:%M:%SZ"
            )
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
            "contributors_count": self.contributors_count,
            "commits_count": self.commits_count,
            "created_at": self.created_at,
            "last_commit_date": self.last_commit_date,
            "description": self.description,
            "url": self.url,
            "stars": getattr(self, "stars", 0),
        }


class RepositoryAnalyzer:
    def __init__(self):
        self.repositories = []

    def enrich_from_json(self, filename):
        print("[DEBUG] enrich_from_json INICIO")

        try:
            print(f"[DEBUG] Lendo JSON: {filename}")
            with open(filename, "r") as f:
                data = json.load(f)
            print("[DEBUG] JSON carregado:", len(data))
        except Exception as e:
            print("[ERRO] Falha ao ler JSON:", repr(e))
            return

        for idx, item in enumerate(data, start=1):
            try:
                owner = item["owner"]
                name = item["name"]

                print(f"[DEBUG] ({idx}) {owner}/{name}")

                repo = RepositoryInfo(
                    name=name,
                    owner=owner,
                    contributors_count=item.get("contributors", 0),
                    commits_count=item.get("total_commits", 0),
                    created_at=item.get("first_commit", "1970-01-01T00:00:00Z"),
                    description=item.get("description", "No description"),
                    url=item.get("url", ""),
                    last_commit_date=item.get("last_commit"),
                    stars=item.get("stars", 0),
                )

                if repo.is_valid():
                    print(
                        f"[DEBUG] VALIDO: {owner}/{name} | score={repo._latest_score}"
                    )
                    self.repositories.append(repo)
                else:
                    print(f"[DEBUG] INVALIDO: {owner}/{name}")

            except Exception as e:
                print(f"[ERRO] {item.get('owner')}/{item.get('name')}: {repr(e)}")

        print("[DEBUG] FIM. Total válidos:", len(self.repositories))

    def save_results_to_json(self, filename):
        with open(filename, "w") as f:
            json.dump([r.obj_to_dict() for r in self.repositories], f, indent=4)

        print(f"Results saved to {filename}")


if __name__ == "__main__":
    print("[DEBUG] Entrou no main")

    analyzer = RepositoryAnalyzer()

    analyzer.enrich_from_json("dsl_models_found.json")

    print("\nValid repositories found:", len(analyzer.repositories))

    for repo in analyzer.repositories:
        print(
            f"- {repo.name} | Owner: {repo.owner} | Commits: {repo.commits_count} | Contributors: {repo.contributors_count}"
        )

    analyzer.save_results_to_json("analyzed_repos.json")
