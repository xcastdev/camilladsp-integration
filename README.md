# CamillaDSP Integration for Home Assistant

A custom Home Assistant integration that connects to a [CamillaDSP](https://github.com/HEnquist/camilladsp) backend, exposes common DSP settings as dynamic entities, and supports safe whole-document config editing through a validated pipeline.

## Features

- **Config flow setup** with host/port connectivity validation
- **Dynamic entities** generated from the active CamillaDSP config -- no hardcoded entity lists
- **Number entities** for filter gain, frequency, Q, delay, compressor parameters, mixer source gain, and more
- **Switch entities** for mute, inverted, pipeline bypass, soft clip, and other booleans
- **Select entities** for active config file switching and enum fields
- **Sensor entities** for runtime telemetry (DSP state, sample rate, buffer level, processing load, clipped samples, volume, mute)
- **8 services** for raw path editing, batch mutations, and structural config changes
- **Full round-trip safety** -- unsupported config fields are preserved through edits
- **Debounced slider writes** to avoid flooding the backend during rapid adjustments
- **Write serialization** via per-entry lock to prevent race conditions
- **External change detection** -- automatically reloads and rebuilds entities when the active config changes outside HA
- **Comprehensive diagnostics** for troubleshooting

## Requirements

- Home Assistant 2024.1 or later
- A running CamillaDSP instance with the backend GUI/API accessible over HTTP

## Installation

1. Copy the `custom_components/camilladsp/` directory into your Home Assistant `custom_components/` folder.
2. Restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration** and search for **CamillaDSP**.
4. Enter the host and port of your CamillaDSP backend (default port: `5005`).
5. The integration will validate the connection and create entities from your active config.

## Supported Filter Types

The integration generates entities for the following CamillaDSP filter and processor types:

### Filters

| Type | Entity Parameters |
|------|-------------------|
| **Gain** | gain (dB) |
| **Delay** | delay |
| **Biquad -- Highpass / Lowpass** | freq, q |
| **Biquad -- HighpassFO / LowpassFO** | freq |
| **Biquad -- Highshelf / Lowshelf** | freq, gain, q or slope |
| **Biquad -- HighshelfFO / LowshelfFO** | freq, gain |
| **Biquad -- Peaking** | freq, gain, q or bandwidth |
| **Biquad -- Notch** | freq, q or bandwidth |
| **Biquad -- GeneralNotch** | freq_p, freq_z, q_p, normalize_at_dc |
| **Biquad -- Bandpass** | freq, q or bandwidth |
| **Biquad -- Allpass / AllpassFO** | freq, q or bandwidth |
| **Biquad -- LinkwitzTransform** | freq_act, q_act, freq_target, q_target |
| **Biquad -- Free** | a1, a2, b0, b1, b2 |
| **BiquadCombo -- Butterworth HP/LP** | freq, order |
| **BiquadCombo -- LinkwitzRiley HP/LP** | freq, order |
| **BiquadCombo -- Tilt** | gain |
| **BiquadCombo -- FivePointPeq** | per-band freq, gain, Q (15 parameters) |
| **BiquadCombo -- GraphicEqualizer** | freq_min, freq_max (gains array via service) |
| **Dither** | bits, amplitude |
| **Conv** | read-only (coefficient files not editable as entities) |

### Processors

| Type | Entity Parameters |
|------|-------------------|
| **Compressor** | threshold, factor, attack, release, makeup_gain, clip_limit, soft_clip |

### Mixers

| Element | Entity Parameters |
|---------|-------------------|
| **Source** | gain, mute, inverted, scale |

### Pipeline

| Element | Entity Parameters |
|---------|-------------------|
| **Step** | bypassed |

### Runtime Sensors

| Sensor | Description |
|--------|-------------|
| DSP State | Current processing state |
| Capture Rate | Input sample rate |
| Buffer Level | Processing buffer fill level |
| Clipped Samples | Number of clipped samples |
| Processing Load | CPU load percentage |
| Active Config | Currently active config filename |
| Volume | Global volume level |
| Mute | Global mute state |

## Services

All services are available under the `camilladsp` domain in **Developer Tools > Services**.

### `camilladsp.reload_active_config`

Re-fetch the active config from the backend and rebuild all entities.

### `camilladsp.validate_active_config`

Run backend validation on the currently cached config document without applying it.

### `camilladsp.save_active_config`

Explicitly save the current config to disk.

### `camilladsp.set_active_config_file`

Switch the active config file and reload all entities.

```yaml
service: camilladsp.set_active_config_file
data:
  name: "my_config.yml"
```

### `camilladsp.set_config_value`

Set a single value anywhere in the config document by path.

```yaml
service: camilladsp.set_config_value
data:
  path: "filters.Bass Control.parameters.gain"
  value: -6.0
```

### `camilladsp.batch_set_config_values`

Apply multiple changes in a single atomic transaction.

```yaml
service: camilladsp.batch_set_config_values
data:
  operations:
    - path: "filters.Bass.parameters.gain"
      value: -3.0
    - path: "filters.Treble.parameters.gain"
      value: 2.0
```

### `camilladsp.add_config_node`

Add a filter, mixer, processor, or pipeline step.

```yaml
service: camilladsp.add_config_node
data:
  section: "filters"
  name: "My New Filter"
  data:
    type: "Gain"
    parameters:
      gain: 0
      inverted: false
```

### `camilladsp.remove_config_node`

Remove a named node or pipeline step.

```yaml
service: camilladsp.remove_config_node
data:
  path: "filters.My New Filter"
```

## Config Path Syntax

All path-based services and entity config paths use dot-separated notation with bracket indexing for lists:

| Path | Target |
|------|--------|
| `filters.Bass Control.parameters.gain` | Gain value of the "Bass Control" filter |
| `pipeline[1].bypassed` | Bypass flag on the second pipeline step |
| `mixers.Stereo.mapping[0].sources[0].gain` | Gain on the first source of the first mapping in the "Stereo" mixer |
| `devices.samplerate` | Device sample rate |
| `processors.democompr.parameters.threshold` | Compressor threshold |

## How Editing Works

CamillaDSP uses a whole-document API -- there is no endpoint for updating a single filter parameter. This integration handles that safely:

1. **Receive** the new value from an entity slider, switch, or service call
2. **Debounce** rapid changes (500ms window for number entities)
3. **Clone** the cached normalized config document
4. **Mutate** the target path in the cloned copy
5. **Validate locally** (type checks, path existence)
6. **Validate remotely** via `/api/validateconfig`
7. **Apply** the config to the running DSP via `/api/setconfig`
8. **Save** the config to disk via `/api/saveconfigfile`
9. **Refresh** the cached config and update entity states

If validation fails at any step, the write is rejected, the cached config remains unchanged, and an error is surfaced.

## Token Detection

CamillaDSP configs can contain tokenized values like `$samplerate$` or `filter_$channels$.txt`. The integration detects these patterns and marks affected entities as read-only to prevent accidental corruption. These fields remain editable through the raw path services.

## Known Limitations

- **No custom Lovelace cards** -- entities use standard HA controls
- **Graphic EQ gains array** is service-only (not individual entities per band)
- **Mixer mapping arrays** with complex structures are service-first for add/remove operations
- **Pipeline reordering** is service-only
- **Conv filter coefficients** (filenames, format metadata) are not exposed as editable entities
- **No waveform or filter response visualization**
- **Config flow and platform tests** require a full Home Assistant test environment; current automated tests cover the pure-Python modules

## Project Structure

```
custom_components/camilladsp/
  __init__.py              # Integration setup, coordinator bootstrap, service registration
  manifest.json            # Integration metadata
  const.py                 # Domain constants and defaults
  config_flow.py           # Host/port setup with connectivity validation
  coordinator.py           # DataUpdateCoordinator for polling and write pipeline
  entity.py                # Descriptor-backed entity base class
  number.py                # Number platform (gain, freq, Q, etc.)
  switch.py                # Switch platform (mute, bypass, etc.)
  select.py                # Select platform (active config, enums)
  sensor.py                # Sensor platform (runtime telemetry)
  services.py              # Service handlers for advanced editing
  services.yaml            # Service definitions for HA UI
  diagnostics.py           # Diagnostic data dump
  strings.json             # Config flow and service strings
  translations/en.json     # English translations
  api/
    client.py              # Async HTTP client for CamillaDSP API
    errors.py              # Typed exception hierarchy
    models.py              # Transport model dataclasses
  config/
    schema.py              # Normalized document TypedDicts
    normalize.py            # Raw config to normalized document
    paths.py               # Canonical path parsing and resolution
    mutate.py              # Clone-on-write mutation helpers
    validate.py            # Local and backend validation
  entities/
    descriptors.py         # Entity descriptor dataclass
    builder.py             # Walks config, emits descriptors
    numbers.py             # Number descriptor factories
    switches.py            # Switch descriptor factories
    selects.py             # Select descriptor factories
    sensors.py             # Sensor descriptor factories
    utils.py               # sanitize_id, token detection
```

## Development

### Running Tests

```bash
pip install pyyaml pytest pytest-asyncio
python3 -m pytest tests/ -v
```

The test suite (269 tests) covers normalization, path resolution, mutation, validation, descriptor generation, and the API client. Tests use lightweight stubs for Home Assistant imports so they run without a full HA environment.

### Adding Support for New Filter Types

1. Add a descriptor factory function in `entities/numbers.py`, `entities/switches.py`, or `entities/selects.py`
2. Call it from the corresponding `_build_filter_*` function
3. The descriptor builder, platform, and coordinator handle the rest automatically

No platform code changes are needed -- the descriptor-driven architecture makes new filter support a single-file change.

## License

See repository for license details.
