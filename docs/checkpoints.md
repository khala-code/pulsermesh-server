# Checkpoints

A checkpoint is the node's shared temporal reference — the discrete moment
all OaZaTa key projections are anchored to.

## Structure

```
index       monotonically increasing counter
hash        sha256(index | node_id | prev_hash | ta_ref)
ta_ref      the Ta value the mesh agreed on at this moment
prev_hash   links checkpoints into a chain (None for genesis)
```

## Key Rotation

Every steward key is derived as:
```
pm_ + sha256(steward_id | oa | za | ta | checkpoint_hash | node_secret)
```

When the checkpoint advances, all steward keys silently rotate. The previous
`grace_window` (default: 2) checkpoint keys remain valid so stewards aren't
hard-locked mid-session.

## Why This Works

The steward's `ta` value is frozen at registration — it's the proper-time
projection of their position on the zeta spiral at the moment they joined.
As the checkpoint advances (Ta progresses), the key derived from that frozen
projection becomes an increasingly stale approximation of their true position.

This means:
- The key can only be used to triangulate the steward's past position
- Each rotation reduces the triangulation surface available to outside observers
- A steward who pulses regularly keeps their approximation fresh
- A dormant steward's key becomes less informative over time

## v1 — Manual Advance

```bash
curl -X POST http://localhost:8000/checkpoint/advance \
  -H "X-API-Key: changeme" \
  -H "Content-Type: application/json" \
  -d '{"ta_ref": 1.0}'
```

## v2 — Mesh Consensus

Checkpoint advance will require agreement from a quorum of peer nodes,
anchored to the next nontrivial zero of the Riemann zeta function.
The checkpoint hash becomes externally verifiable, not just node-local.
