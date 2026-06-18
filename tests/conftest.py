"""
Shared pytest fixtures.

All tests that need a database get a fresh in-memory SQLite session.
The session is rolled back after each test so tests are isolated.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base

# Import all models so Base.metadata is populated before create_all()
from app.models import steward, pulse, checkpoint, node  # noqa: F401
from app.models import domain_vector, identity  # noqa: F401


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
