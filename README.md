# pulsermesh-server

`pulsermesh-server` is the reference implementation of a Pulser Mesh T3 node. T3 nodes are the institutional layer of the mesh — they maintain local scarcity data, cross-validate work registered by T2 stewards, authorize dividend pulses, and handle imports and exports at the domain boundary.

This server is designed to be self-hosted by any organization operating as a T3 within a trust scarcity domain. It is intentionally lightweight — horizontal scaling across many independent T3 instances is the architecture, not vertical scaling of a single server.

## Stack

- **Python 3.11+** / FastAPI
- **SQLite** (dev) — swap to Postgres via `DATABASE_URL` env var
- **API key auth** (v1) — ZKP identity layer planned for v2

## Quickstart

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

## Structure

```
app/
  main.py          # FastAPI app entry point
  config.py        # Settings via env vars
  database.py      # DB connection + session
  models/          # SQLAlchemy ORM models
  schemas/         # Pydantic request/response schemas
  routers/         # Route handlers by domain
  services/        # Business logic layer
  auth.py          # API key middleware
tests/
requirements.txt
.env.example
```

## License

GPL-3.0 — see [LICENSE](LICENSE)
