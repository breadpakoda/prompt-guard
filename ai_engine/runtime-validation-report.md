# AI Engine Runtime Validation Report

**Generated:** 2026-11-01T19:17:32+05:30  
**Target:** `ai_engine/`  
**Python:** 3.14.7  
**Docker:** Unavailable  
**Node.js:** v24.20.0 (browser E2E is not applicable to this API-only service)

## Summary

| Validation | Status | Exit code | Results |
|---|---:|---:|---|
| Full pytest suite (rerun) | PASS | 0 | 51 passed in 17.31s |
| Layer 1 local model | PASS | 0 | 5 runtime tests, including malicious, benign, empty, and boolean-return cases |
| Layer 2 model/index script (rerun) | PASS | 0 | 10/10 scenarios; persisted index loaded with 22 vectors |
| Layer 3 offline contract tests | PASS | 0 | 6 tests cover YES/NO parsing, invalid verdicts, and invalid-input short-circuit |
| Layer 3 configured-provider script (retry) | PASS | 0 | 8/8 scenarios; provider connection recovered |
| API startup/readiness | PASS | 0 | Uvicorn started; `/health` returned `ok`; OpenAPI listed all five routes |
| Live Layer 3 empty-input path | PASS | 0 | `/layer3-check` returned `is_danger=false`, `security_status=clear` |
| Python syntax compilation | PASS | 0 | `python -m compileall -q ai_engine` |

**Overall: PASS** — the full local test suite, Layer 2 model evaluation, and live Layer 3 provider evaluation all passed on rerun. The earlier Layer 3 connection errors were transient; the retry completed all eight scenarios.

## Coverage

| Endpoint | Exercised behavior |
|---|---|
| `GET /health` | Live readiness response and in-process contract |
| `POST /chat` | Successful response, persisted conversation, input validation, L1/L2 blocks, L3-triggered block, and failure handling |
| `GET /status/{conversation_id}` | Existing conversation read-back and unknown conversation |
| `POST /layer3-check` | Benign and malicious verdicts, blocked-state enforcement, invalid LLM response mapping, and live empty-input short-circuit |
| `POST /layer3-alert` | Local block-state update and forwarding behavior with an HTTP stub |

The API tests isolate the external target LLM and Node.js alert service; these dependencies were not called during the test suite. Live L3 tests did attempt the configured LLM provider.

## Evaluation Reports Reviewed

- **Layer 1** — The report describes 1,528 prior evaluation samples. Its out-of-domain results show 97.8% attack recall but 76.8% accuracy and 55.8% specificity at the default threshold; it recommends threshold `0.8` as a precision/recall trade-off. This run verified local inference on a smaller runtime set, not the full historical datasets.
- **Layer 2** — The report describes 445 prior benchmark cases. Curated-template performance is reported as 31/33; for the balanced 400-case task-specific dataset, the confusion matrix reports only 2/200 attacks detected at threshold `0.45` (1% recall) while accepting 199/200 benign prompts. The live 10-case script passed, including its injection, benign, and empty-input cases.
- **Layer 3** — The report describes 36 prior cases with 34/36 accuracy, 20/22 attack recall, and two missed attacks. The current live script could not reproduce provider-backed classification because of the connection errors above; its empty-input short-circuit passed.

Historical evaluation metrics are reported as documented and were not regenerated from the original full datasets in this run.

## Commands and Evidence

- `pytest -q ai_engine` — exit 0; **51 passed** in 17.31s. Includes 25 pre-existing tests and 26 added runtime tests.
- `python ai_engine\layer2\test_layer2.py` — exit 0; **10/10 passed**.
- `python ai_engine\layer3\test_layer3.py` — exit 0; **8/8 passed**, including all live provider-backed cases.
- `python -m compileall -q ai_engine` — exit 0.
- Uvicorn startup and readiness probe — exit 0; `/health` returned HTTP 200 and OpenAPI exposed `/chat`, `/health`, `/layer3-alert`, `/layer3-check`, and `/status/{conversation_id}`.

The pytest rerun emitted a `pytest-asyncio` fixture-loop-scope deprecation warning and LangSmith `asyncio.iscoroutinefunction` deprecation warnings. Neither caused test failures. The earlier Layer 3 attempt failed with provider connection errors but the retry passed.

## Test Assets Added

- `layer1/test_classifier_runtime.py`
- `layer2/test_detector_runtime.py`
- `layer3/test_detector_runtime.py`
- `api/test_endpoints_runtime.py`

No production source files were changed for this validation.
