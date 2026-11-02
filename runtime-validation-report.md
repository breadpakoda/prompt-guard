# Runtime Validation Report

**Updated:** 2026-11-02  
**Target:** `D:\Academics\5th sem\Minor project\PBL\prompt-guard`

## Summary

| Step | Status | Exit code | Details |
|---|---|---:|---|
| Startup | PASS | n/a | Node API, FastAPI, MongoDB, and Vite responded locally. Both API `/health` endpoints and the Vite page returned 200. |
| Server integration tests | PASS | 0 | `npm test` in `server`: 5 passed, 0 failed. Tests cover prompt flow, persistence, concurrent requests, pending-state recovery, request validation, and security alerts. |
| AI engine tests | PASS | 0 | `python -m pytest -q`: 65 passed, including common greeting variants. |
| Client build and lint | PASS | 0 | `npm run build` and `npm run lint` in `client` passed. |
| Browser E2E | PASS | 0 | `npm run test:e2e` in `client`: 3 Playwright tests passed against live services. |

**Overall: PASS for the exercised flows.** The previous server regression is fixed, and browser behavior now has repeatable tests. Remaining limitations are listed below.

## Fixes Applied

1. **Conversation blocks are now monotonic.** Only a malicious Layer 3 alert can block a conversation. A non-malicious Layer 3 result and Layer 1/2 advisory alerts cannot clear a block. Layer 1/2 refusals no longer block a whole conversation.
2. **Concurrent chat requests are serialized per conversation in the Node process.** Conversation creation uses an atomic MongoDB upsert; blocked/pending status updates do not overwrite a block.
3. **Common exact greetings bypass known Layer 1/2 false positives.** Live checks previously scored `hi` at 0.867, `hello` at 0.946, and `hello there` at 0.899 Layer 1 attack confidence. Exact greeting variants now bypass Layers 1/2; additional text still goes through detection.
4. **Blocked conversations are visibly unavailable in the client.** The message input and Send button are disabled. Pending conversations preserve the prompt and allow retry; the server checks FastAPI's current status before forwarding it.
5. **Internal security-alert endpoints remain restricted to loopback callers.**

See [server/index.js](./server/index.js), [bot.py](./ai_engine/llm/bot.py), [App.jsx](./client/src/App.jsx), and [README.md](./ai_engine/README.md).

## Browser Requests

The client at `http://localhost:5173` was exercised in the integrated browser and automated with Playwright:

| Flow | Observed result |
|---|---|
| Send `hi` in a new conversation | AI responded normally; status remained clear. |
| Send an injection attempt | AI returned the refusal; conversation remained clear as required for a Layer 1/2 refusal. |
| Send `What is 2 plus 2?` after that refusal | AI responded `2 + 2 = 4`; the conversation remained usable. |
| Reopen an existing Layer 3-blocked conversation | UI showed blocked status and disabled both input and Send. |
| Refresh and reopen a normal conversation | Earlier messages were restored from MongoDB. |

The old conversations blocked by the earlier Layer 1/2 behavior remain blocked in MongoDB: their records do not distinguish old Layer 1/2 blocks from genuine Layer 3 blocks, so they are not automatically unblocked. Start a new chat to continue.

## Automated Tests

Run the server integration tests with:

```powershell
cd "D:\Academics\5th sem\Minor project\PBL\prompt-guard\server"
npm test
```

Run the AI-engine tests with:

```powershell
cd "D:\Academics\5th sem\Minor project\PBL\prompt-guard"
python -m pytest -q
```

| Test file | Coverage | Result |
|---|---|---|
| [chat-flow.test.js](./server/test/chat-flow.test.js) | Multiple prompts, greeting regression, ordered persistence, and concurrent requests. | PASS |
| [request-validation.test.js](./server/test/request-validation.test.js) | Missing conversation ID and blank prompt validation; no invalid messages persisted. | PASS |
| [security-block.test.js](./server/test/security-block.test.js) | Layer 3 block persistence and 403; Layer 1/2 alerts do not block; no false alert clears an existing block. | PASS |
| [pending-recovery.test.js](./server/test/pending-recovery.test.js) | Pending Node status is reconciled with FastAPI; a verified clear status permits retry and persistence. | PASS |
| [chat.spec.js](./client/e2e/chat.spec.js) | Browser flows for multi-turn persistence/reload, refusal and safe follow-up, and blocked UI/server 403 enforcement. | 3 passed |
| AI-engine Python suite | Security, API, conversation tests, and common greeting false-positive regressions. | 65 passed |

Install the browser once with `npx playwright install chromium` from `client`, then run:

```powershell
cd "D:\Academics\5th sem\Minor project\PBL\prompt-guard\client"
npm run test:e2e
```

The Node API, FastAPI, MongoDB, and Vite must be running. Run the E2E suite
separately from integration suites that mutate the same MongoDB database.

## Known Limitations

- Greeting handling is an exact allowlist, not a general classifier recalibration. Other unseen benign prompts can still be false positives; retraining or validating the detector against a broader benign corpus is still recommended.
- Per-conversation request serialization is in-process; a horizontally scaled Node deployment would need a distributed lock or equivalent coordination.
- The engine's Layer 3 state is in-memory. MongoDB preserves Node's block decision, but restarting FastAPI loses its in-memory analysis history. A pending Mongo status whose engine state no longer exists stays fail-closed; users can start a new conversation.

## Verdict

```text
environment:
  docker: UNAVAILABLE — Docker CLI was not present; local MongoDB was reachable
  node: AVAILABLE — v24.20.0
  playwright: AVAILABLE — Chromium installed; `npm run test:e2e` passed
startup: PASS — Node/FastAPI health endpoints and Vite page returned 200; MongoDB port was reachable
integration: PASS — exit_code: 0; passed: 5, failed: 0; live Node + MongoDB + FastAPI flows
ai_engine: PASS — exit_code: 0; passed: 65, failed: 0
client: PASS — exit_code: 0; build and lint succeeded
e2e: PASS — exit_code: 0; passed: 3, failed: 0; persistence/reload, refusal/follow-up, blocked UI and 403
overall: PASS — reported failures are fixed and regression tests pass; known limitations remain
```
