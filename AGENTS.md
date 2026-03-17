# AGENTS.md - CamillaDSP Home Assistant Integration

## Project Overview

Custom Home Assistant integration for CamillaDSP. Python 3.11+, async throughout.
Descriptor-driven entity architecture; whole-document config editing with validation pipeline.

## Commands

### Test

```bash
# All tests (269 tests, ~0.6s)
python3 -m pytest tests/ -v

# Single test file
python3 -m pytest tests/components/camilladsp/test_normalize.py -v

# Single test by name
python3 -m pytest tests/components/camilladsp/test_normalize.py -k "test_filters_normalized" -v

# With output
python3 -m pytest tests/ -v -s
```

### Lint / Format

```bash
# Ruff lint check
ruff check custom_components/ tests/

# Ruff lint fix
ruff check --fix custom_components/ tests/

# Ruff format check
ruff format --check custom_components/ tests/

# Ruff format apply
ruff format custom_components/ tests/
```

### Type Check

```bash
# Not currently configured (no mypy/pyright in pyproject.toml)
# If adding: mypy custom_components/camilladsp/ --ignore-missing-imports
```

### Dependencies

```bash
pip install pyyaml pytest pytest-asyncio aiohttp
```

## Code Conventions

### Imports

- `from __future__ import annotations` at the top of every module
- stdlib first, then third-party (`aiohttp`, `yaml`), then HA (`homeassistant.*`), then local (`.api`, `.config`, `.entities`)
- Relative imports within the integration package; absolute for HA and stdlib

### Typing

- TypedDicts for config document schema (not dataclasses) -- keeps docs as plain dicts
- Frozen dataclasses for immutable descriptors (`EntityDescriptor`)
- `dict[str, Any]` for the normalized config document throughout
- Type aliases in `config/schema.py`: `ConfigPath = str`, `PathSegments = list[str | int]`

### Naming

- Module-private helpers prefixed with `_` (e.g., `_normalize_filters`, `_raise_for_status`)
- Constants are `UPPER_SNAKE` in `const.py`
- Service names as `SERVICE_*` constants
- Schema validators as `SCHEMA_*` constants
- Entity unique IDs: `camilladsp_{entry_id}_{category}_{sanitized_name}_{param}`

### Error Handling

- Typed exception hierarchy rooted at `CamillaDSPError` in `api/errors.py`
- `CamillaDSPConnectionError` > `CamillaDSPTimeoutError` (inherits for catch-either pattern)
- `CamillaDSPValidationError` carries `.details` from backend
- `CamillaDSPPayloadError` for unexpected response shapes
- Services wrap errors into `HomeAssistantError` or `ServiceValidationError`
- Write pipeline: mutate -> local validate -> backend validate -> apply -> save -> refresh
- On failure: cached config stays unchanged, error surfaces to caller

### Architecture Patterns

- **Descriptor-driven entities**: Builder walks normalized config, emits `EntityDescriptor` list.
  Platforms consume descriptors generically -- no per-filter-type entity classes.
- **Clone-on-write mutations**: `copy.deepcopy` before mutating; candidate doc validated before replacing cache.
- **Write serialization**: Single `asyncio.Lock` per config entry; all mutations serialized.
- **Debounce**: 500ms window for slider-style number entities via `schedule_debounced_update`.
- **Extra field preservation**: Unknown config keys captured in `extra` dicts, restored on denormalize.
- **Token detection**: `$token$` patterns mark entities as read-only.

### Testing

- HA stubs in `tests/conftest.py` -- lightweight MagicMock-based module stubs for `homeassistant.*`
- Fixture configs loaded from `docs/refs/exampleconfigs/` via PyYAML
- Parametrized `any_valid_config` fixture runs tests across all 17 reference configs
- `mock_client` fixture provides `AsyncMock` CamillaDSP client
- Pure-Python modules tested directly; config flow / platform tests need full HA env

### File Organization

```
custom_components/camilladsp/
  api/          # HTTP client, errors, transport models
  config/       # Schema, normalize, paths, mutate, validate
  entities/     # Descriptors, builder, per-platform factories
  *.py          # Integration entry, coordinator, platforms, services
tests/
  components/camilladsp/   # Unit tests with HA stubs
```

## Workflow Guidance

### Direct @plan and @build

Use `@plan` for:
- New filter type support (requires descriptor factory + builder wiring)
- New service endpoints or structural config operations
- Architecture changes to the write pipeline or coordinator
- Cross-cutting changes spanning api/, config/, entities/ layers

Use `@build` for:
- Bug fixes in existing modules
- Adding test coverage for existing functionality
- Extending descriptor factories for new parameter variants
- Documentation updates
- Single-layer changes within one module

### Orchestrated /orch-* Usage

Use `/orch-plan` when:
- Adding a major feature (e.g., websocket support, Lovelace cards, new platform)
- Refactoring multiple layers simultaneously (api + config + entities + platforms)
- Migration work (e.g., HA version compatibility changes)
- Multi-milestone delivery with dependencies

Use `/orch-decide` when:
- Unsure whether a change warrants orchestration
- Evaluating scope of a user request

### Common Risk Areas

- **Normalize/denormalize round-trip**: Any schema change must preserve unknown fields.
  Always verify with parametrized `any_valid_config` tests.
- **Unique ID stability**: Changing `sanitize_id` or path generation breaks existing entities.
- **Write pipeline atomicity**: All writes must go through coordinator's `_write_lock`.
- **HA stub drift**: Test stubs may not reflect real HA API changes; integration tests
  need actual HA environment for config flow and platform validation.
