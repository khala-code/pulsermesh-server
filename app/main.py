from fastapi import FastAPI
from app.routers import node, stewards, pulses, health
from app.database import init_db

app = FastAPI(
    title="Pulser Mesh T3 Node",
    description="Reference T3 node server for the Pulser Mesh protocol.",
    version="0.1.0",
)

@app.on_event("startup")
async def startup():
    init_db()

app.include_router(health.router)
app.include_router(node.router, prefix="/node", tags=["node"])
app.include_router(stewards.router, prefix="/stewards", tags=["stewards"])
app.include_router(pulses.router, prefix="/pulses", tags=["pulses"])
