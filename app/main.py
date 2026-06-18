from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine, Base, SessionLocal
from app.routers import stewards, pulses
from app.routers.checkpoint import router as checkpoint_router
from app.models import steward, pulse, identity, checkpoint as checkpoint_model
from app.models import domain_vector  # ensures table is created by metadata

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed domain vectors from config on first startup."""
    db = SessionLocal()
    try:
        from app.services.domain import seed_domain_vectors
        created = seed_domain_vectors(db)
        if created:
            import logging
            logging.getLogger(__name__).info(
                "Seeded %d domain vectors: %s",
                len(created),
                [dv.domain for dv in created],
            )
    finally:
        db.close()
    yield


app = FastAPI(
    title="Pulser Mesh T3",
    description="Trust-resource mesh node. OaZaTa-scoped steward auth with checkpoint-anchored key rotation.",
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "version": "0.3.0"}


app.include_router(stewards.router, prefix="/stewards", tags=["stewards"])
app.include_router(pulses.router, prefix="/pulses", tags=["pulses"])
app.include_router(checkpoint_router, prefix="/checkpoint", tags=["checkpoint"])
