from fastapi import FastAPI
from app.database import engine, Base
from app.routers import stewards, pulses
from app.routers.checkpoint import router as checkpoint_router
from app.models import steward, pulse, identity, checkpoint as checkpoint_model

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Pulser Mesh T3",
    description="Trust-resource mesh node. OaZaTa-scoped steward auth with checkpoint-anchored key rotation.",
    version="0.3.0"
)

app.include_router(stewards.router, prefix="/stewards", tags=["stewards"])
app.include_router(pulses.router, prefix="/pulses", tags=["pulses"])
app.include_router(checkpoint_router, prefix="/checkpoint", tags=["checkpoint"])
