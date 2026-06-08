# Authentication

Pulser Mesh T3 uses a two-tier API key system.

## Tier 1 — Node Key (admin)

Set in `.env` as `API_KEY_SECRET`. Used by the T3 operator for:
- Registering new stewards
- Validating pulses
- Reading node status

Header: `X-API-Key: <node_secret>`

## Tier 2 — Steward Key (OaZaTa-derived)

Issued at steward registration. Derived deterministically from the steward's
OaZaTa field position (Oa, Za, Ta) and the current checkpoint hash.

Header: `X-API-Key: pm_<sha256_of_rotor_phase>`

Used by stewards for:
- Submitting pulses (`POST /pulses/submit`)
- Reading their own pulses (`GET /pulses/mine`)
- Reading their identity (`GET /stewards/{id}/identity`)

## v2 — Interference Pattern Vibe Check

In v2 the steward key is replaced by a proof-of-position:
the steward's current rotor phase (sin/cos/tan of their Za angle)
must produce **constructive interference** with the T3 node's
reference wave at the current Heegner checkpoint.

Destructive interference = auth rejected.
Proximity to the tan(Za) pole = consent boundary signal.

The node admin key never replaces this check — it is a separate
administrative surface with no ability to impersonate a steward.

## Key Format

```
pm_<64-char hex>   — steward OaZaTa key
<raw secret>        — node admin key (set by operator)
```
