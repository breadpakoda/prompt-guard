# AI Engine Detection Flow

## Combined Layer 1 + Layer 2 scoring

For each non-empty chat prompt, Layer 1 and Layer 2 run concurrently. Layer 1
provides an attack score `p1` in `[0, 1]`; Layer 2 provides cosine similarity
`s2` in `[-1, 1]`.

Layer 2 similarity is converted to soft evidence using a sigmoid centered on
the configured similarity threshold `t2 = 0.45`, with temperature `T = 0.05`:

```text
e2 = 1 / (1 + exp(-(s2 - t2) / T))
```

The combined score uses noisy-OR:

```text
combined = 1 - (1 - p1) * (1 - e2)
```

This is a risk-fusion heuristic, not a calibrated probability. Either strong
signal can trigger a detection; moderate evidence from both layers can also
combine. The request is treated as an injection when `combined >= 0.5`.

On detection, the AI engine does not call the target LLM. It returns a
user-facing refusal, forwards both detector scores and the combined score to
the Node server's internal `/security-alert` endpoint, and does not mark the
conversation blocked. The next request in that conversation can proceed
through detection normally. A failed alert forward is logged and reported in
the API response as `alert_forwarded: false`; it does not change the refusal.

Layer 3's existing conversation-level block behavior is unchanged.
