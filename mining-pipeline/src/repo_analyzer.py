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
        tier,
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
        self.tier = tier

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

        if stars >= 50:
            score += 10
        elif stars >= 20:
            score += 7
        elif stars >= 5:
            score += 4
        elif stars >= 1:
            score += 2

        if days_last_commit <= 180:
            score += 15
        elif days_last_commit <= 365:
            score += 10
        elif days_last_commit <= 720:
            score += 6
        elif days_last_commit <= 1095:
            score += 3

        if self.contributors_count >= 5:
            score += 10
        elif self.contributors_count >= 3:
            score += 7
        elif self.contributors_count >= 2:
            score += 4
        elif self.contributors_count == 1:
            score += 2

        if self.commits_count >= 100:
            score += 15
        elif self.commits_count >= 50:
            score += 10
        elif self.commits_count >= 20:
            score += 6
        elif self.commits_count >= 5:
            score += 3

        self._latest_score = score

        if self._latest_score >= 30:
            self.tier = "A"
        elif self._latest_score >= 20:
            self.tier = "B"
        elif self._latest_score >= 10:
            self.tier = "C"
        else:
            self.tier = None
            return False

        return True

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
            "tier": self.tier,
        }


def extract_from_json(filename):
    with open(filename, "r") as f:
        return json.load(f)


def transform_repositories(data):
    repositories = []

    for item in data:
        try:
            repo = RepositoryInfo(
                name=item["name"],
                owner=item["owner"],
                contributors_count=item.get("contributors", 0),
                commits_count=item.get("total_commits", 0),
                created_at=item.get("first_commit"),
                description=item.get("description"),
                url=item.get("url"),
                last_commit_date=item.get("last_commit"),
                stars=item.get("stars", 0),
                tier=item.get("tier"),
            )

            if repo.is_valid():
                repositories.append(repo)

        except Exception as e:
            logger.error(f"Error processing repo: {repr(e)}")

    return repositories


def generate_output_filename(prefix="analyzed_repos"):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{prefix}_{timestamp}.json"


def load_results_grouped(repositories, filename):
    grouped = {"A": [], "B": [], "C": []}

    for repo in repositories:
        if repo.tier:
            grouped[repo.tier].append(repo.obj_to_dict())

    with open(filename, "w") as f:
        json.dump(grouped, f, indent=4)

    logger.info(f"Grouped results saved to {filename}")


def update_latest(filename):
    with open("../dataset/latest.json", "w") as f:
        json.dump({"latest": filename}, f)


def run_pipeline(input_file, output_file):
    logger.info("Starting ETL pipeline")

    data = extract_from_json(input_file)
    logger.info(f"Extracted {len(data)} items")

    repos = transform_repositories(data)
    logger.info(f"Transformed: {len(repos)} valid repositories")

    load_results_grouped(repos, output_file)

    logger.info("Pipeline finished")


if __name__ == "__main__":
    output_file = generate_output_filename()
    run_pipeline("../dataset/dsl_models_found.json", output_file)
    update_latest(output_file)
