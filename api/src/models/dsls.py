from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.sql import func
from src.database import Base


class DSL(Base):
    __tablename__ = "dsls"

    id = Column(Integer, primary_key=True, index=True)

    # identification
    artifact_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    repository_url = Column(String, nullable=False)

    # classification
    artifact_type = Column(String)  # dsl, tutorial, libraries, parser, metamodel, other
    modeling_ecosystem = Column(String)  # JetBrains MPS
    tier = Column(String)  # A, B, C
    score = Column(Integer)

    # semantic
    domain = Column(String)
    purpose = Column(Text)
    description = Column(Text)

    # engagement metrics
    stars = Column(Integer, default=0)
    contributors = Column(Integer, default=0)
    commits = Column(Integer, default=0)
    created_at = Column(String)
    last_commit_date = Column(String)

    # metadata
    inserted_at = Column(DateTime, server_default=func.now())
