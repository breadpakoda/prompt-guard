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
conversation blocked. The Node endpoint records this as an advisory detection;
only a malicious Layer 3 alert received at `/layer3-alert` blocks a conversation.
A later non-malicious alert never clears a prior Layer 3 block. The next request
after a Layer 1/2 refusal can proceed through detection normally. A failed alert
forward is logged and reported in the API response as `alert_forwarded: false`;
it does not change the refusal.

Exact common greetings (for example, `hi`, `hello there`, and `good morning`)
bypass Layers 1/2 because the configured classifier falsely labels some short
greetings as attacks. This exact-match exception does not apply to prompts that
contain additional text.
