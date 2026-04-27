from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy import or_
from dotenv import load_dotenv
from pathlib import Path
import os

from src.database import engine, get_db, Base
from src.models.dsls import DSL

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)
print("ENV path:", Path(__file__).parent.parent.parent / ".env")
print("API_KEY loaded:", repr(os.getenv("API_KEY")))

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DSL Recommender API", version="0.1.0")

API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key")


def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dsls")
def list_dsls(
    tier: str = None,
    domain: str = None,
    artifact_type: str = None,
    min_stars: int = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """List DSLs with optional filters."""
    query = db.query(DSL)

    if tier:
        query = query.filter(DSL.tier == tier.upper())
    if domain:
        query = query.filter(DSL.domain.ilike(f"%{domain}%"))
    if artifact_type:
        query = query.filter(DSL.artifact_type == artifact_type)
    if min_stars is not None:
        query = query.filter(DSL.stars >= min_stars)

    total = query.count()
    results = query.order_by(DSL.score.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [dsl_to_dict(d) for d in results],
    }


@app.get("/dsls/{artifact_id:path}")
def get_dsl(
    artifact_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Get a single DSL by owner/name."""
    dsl = db.query(DSL).filter(DSL.artifact_id == artifact_id).first()
    if not dsl:
        raise HTTPException(status_code=404, detail="DSL not found")
    return dsl_to_dict(dsl)


@app.get("/dsls/search/{query}")
def search_dsls(
    query: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Search DSLs by name, description, domain or purpose."""
    results = (
        db.query(DSL)
        .filter(
            or_(
                DSL.name.ilike(f"%{query}%"),
                DSL.description.ilike(f"%{query}%"),
                DSL.domain.ilike(f"%{query}%"),
                DSL.purpose.ilike(f"%{query}%"),
            )
        )
        .order_by(DSL.score.desc())
        .limit(limit)
        .all()
    )
    return {"total": len(results), "results": [dsl_to_dict(d) for d in results]}


def dsl_to_dict(dsl: DSL):
    return {
        "artifact_id": dsl.artifact_id,
        "name": dsl.name,
        "owner": dsl.owner,
        "repository_url": dsl.repository_url,
        "artifact_type": dsl.artifact_type,
        "modeling_ecosystem": dsl.modeling_ecosystem,
        "tier": dsl.tier,
        "score": dsl.score,
        "domain": dsl.domain,
        "purpose": dsl.purpose,
        "description": dsl.description,
        "stars": dsl.stars,
        "contributors": dsl.contributors,
        "commits": dsl.commits,
        "created_at": dsl.created_at,
        "last_commit_date": dsl.last_commit_date,
    }
