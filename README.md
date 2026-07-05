# inferno

Standalone inference runtime and orchestration layer for **Potato OS**, the
on-device LLM stack for Raspberry Pi. Inferno owns everything between
*"Potato says run this model"* and *"here is the OpenAI-compatible response"*:
backend proxying, model-family classification, the model registry, runtime
(llama.cpp / ik_llama / LiteRT) lifecycle management, settings normalization,
projector resolution, and the inference-process readiness state machine.

The package name is `potato-inferno`; the import name is `inferno`.

---

## Design boundary

Inferno is extracted from Potato OS so that the inference layer can be tested
and evolved on its own. The dependency arrow points **one way**:

```
Potato (caller)  ──▶  Inferno (this package)
```

Inferno never imports from `core.model_state`, `core.runtime_state`,
`core.settings`, `core.deps`, or any `apps/` code. Everything product-specific
is injected by the caller via config dataclasses (`ModelStoreConfig`,
`RuntimeStoreConfig`) or passed as plain arguments. Functions take primitives,
dicts, and callbacks — never a FastAPI `app.state`.

> **Note on coupling.** The import boundary is clean, but Inferno still speaks
> Potato's vocabulary: it reads `POTATO_*` environment variables (see below),
> writes a `.potato-llama-runtime-bundle.json` marker, and classifies hardware
> into Raspberry Pi device classes. A consumer outside Potato OS must adopt
> these conventions.
>
> Logging is namespaced under the package's own `inferno.*` logger tree (each
> module uses `logging.getLogger(__name__)`), so a host can capture all of
> Inferno's logs by configuring the `inferno` logger.

---

## What Inferno provides

| Area | Key entry points |
| --- | --- |
| **Chat backends** | `LlamaCppRepository` (real llama.cpp HTTP proxy), `FakeLlamaRepository` (dev/test), `ChatRepositoryManager` (dispatch), `BackendResponse`, `BackendProxyError` |
| **Model families** | `is_qwen35_filename`, `is_gemma4_filename`, `projector_repo_for_model`, `recommended_runtime_for_model`, `default_projector_candidates_for_model`, `build_model_projector_status` |
| **Model registry** | `ModelStoreConfig`, `ensure_models_state`, `save_models_state`, `register_model_url`, `update_model_settings`, `delete_model`, `validate_model_url_format`, `normalize_model_settings`, `build_model_capabilities` |
| **Runtime manager** | `RuntimeStoreConfig`, `classify_runtime_device`, `discover_runtime_slots`, `check_runtime_device_compatibility`, `install_llama_runtime_bundle`, `ensure_compatible_runtime`, `build_llama_runtime_status` |
| **Launch config** | `build_llama_server_args` (pure function → llama-server CLI argv) |
| **Orchestrator** | `run_inference_tick`, `refresh_readiness`, `check_health`, `restart_inference_process`, `resolve_mmproj_for_launch`, `prepare_activation_runtime` |
| **LiteRT adapter** | `inferno.litert_adapter:app` — standalone FastAPI app |

The full public surface is enumerated in [`inferno/__init__.py`](inferno/__init__.py).

---

## Runtime families & device classes

Three runtime families are supported (`SUPPORTED_RUNTIME_FAMILIES`):

- **`llama_cpp`** — baseline llama.cpp `llama-server` binary. Works everywhere.
- **`ik_llama`** — optimized llama.cpp fork. Requires ARMv8.2-A dot-product
  instructions (Cortex-A76+), so it is **not** compatible with Pi 4.
- **`litert`** — Google LiteRT, driven through the Python adapter
  (`litert_adapter.py`) rather than an external binary. Also Pi 4 incompatible.

`classify_runtime_device` maps a Pi model name + total memory to one of:
`pi5-16gb`, `pi5-8gb`, `pi4-16gb`, `pi4-8gb`, `pi4-4gb`, `other-pi`, `unknown`.
`check_runtime_device_compatibility` then rejects `ik_llama`/`litert` on Pi 4
hardware and recommends `llama_cpp`.

---

## Installation

Requires Python 3.11+.

```bash
pip install -e ".[dev]"     # editable install with test dependencies
```

Runtime dependencies: `fastapi`, `uvicorn[standard]`, `httpx`.
Dev dependencies: `pytest`, `pytest-xdist`, `respx`.

---

## Running the LiteRT adapter

The adapter is an OpenAI-compatible HTTP shim around `litert-lm` that exposes
`/health` and `/v1/chat/completions` on the same port Potato's proxy expects
(8080), so the rest of the stack works unchanged.

```bash
POTATO_MODEL_PATH=/path/to/model.litertlm \
    uvicorn inferno.litert_adapter:app --host 0.0.0.0 --port 8080
```

The adapter requires the `litert-lm` package to be installed separately.
It keeps a single persistent conversation alive to reuse the KV cache across
turns — see the module docstring for the continuation/reset semantics.

---

## Environment variables

| Variable | Consumed by | Purpose |
| --- | --- | --- |
| `POTATO_MODEL_PATH` | `litert_adapter` | Path to the model the LiteRT engine loads at startup. |
| `POTATO_TEST_MODE` | `backend` | When `1`, fake-backend streaming uses a fast chunk delay for tests. |
| `POTATO_FAKE_PREFILL_DELAY_MS` | `backend` | Override the fake backend's prefill delay (ms, clamped 0–60000). |
| `POTATO_FAKE_STREAM_CHUNK_DELAY_MS` | `backend` | Override the fake backend's per-chunk stream delay (ms, clamped 0–60000). |
| `POTATO_LLAMA_RUNTIME_BUNDLE_ROOTS` | `runtime_manager` | `os.pathsep`-separated list of directories to search for llama runtime bundles, overriding the built-in defaults. |
| `POTATO_LLAMA_PROXY_READ_TIMEOUT_S` | `backend` | Optional read timeout (seconds) for the llama.cpp proxy. Unset/empty means unbounded (the default), since a slow device may legitimately take minutes per completion; set a positive value to bound a hung upstream. |

---

## Backends

`ChatRepositoryManager` dispatches by name:

- **`llama`** — proxies to a running llama.cpp/ik_llama server, streaming or
  buffered, preserving the upstream `content-type`.
- **`fake`** — returns deterministic-ish parody completions for local dev and
  tests, with optional artificial streaming delays. Pass a `seed` in the
  request payload for reproducible replies.

LiteRT is served by the standalone adapter app rather than through the manager.

---

## Testing

```bash
python -m ruff check inferno/ tests/   # lint
python -m mypy inferno/                 # type-check
python -m pytest -q                     # run the suite
python -m pytest -q -n auto             # parallel (as CI runs it)
```

CI (`.github/workflows/ci.yml`) installs the package and runs ruff, mypy, and
the test suite on Python 3.11, in that order.

---

## License

MIT.
