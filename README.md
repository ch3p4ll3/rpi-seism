# RPI-SEISM

A 3‑axis geophone seismometer project for Raspberry Pi.  
Reads data from an Arduino‑based digitizer over RS-422, processes it in real‑time, and provides:

- **SDS-compliant MiniSEED archiving** (via ObsPy)
- **StationXML generation** with full GD-4.5 PAZ instrument response
- **Live waveform streaming** via WebSocket to a web frontend
- **Earthquake detection** using a STA/LTA algorithm with immediate file marking and notifications
- **Push notifications** via Telegram (and other Apprise-compatible services)

The system is built around five concurrently running threads, making it efficient and responsive even on a Raspberry Pi.

---

## Table of contents

- [RPI-SEISM](#rpi-seism)
  - [Table of contents](#table-of-contents)
  - [Features](#features)
  - [Hardware Requirements](#hardware-requirements)
  - [Software Stack](#software-stack)
  - [Installation with UV](#installation-with-uv)
  - [Configuration via YAML](#configuration-via-yaml)
    - [Default configuration](#default-configuration)
  - [Usage](#usage)
    - [Frontend](#frontend)
  - [In‑Depth Explanation of Each Thread](#indepth-explanation-of-each-thread)
    - [1. Reader Thread](#1-reader-thread)
    - [2. MSeedWriter Thread](#2-mseedwriter-thread)
    - [3. TriggerProcessor Thread](#3-triggerprocessor-thread)
    - [4. WebSocketSender Thread](#4-websocketsender-thread)
    - [5. NotifierSender Thread](#5-notifiersender-thread)
  - [Data Flow Diagram](#data-flow-diagram)
  - [Customising the STA/LTA Detector](#customising-the-stalta-detector)
  - [Troubleshooting](#troubleshooting)
  - [Contributing](#contributing)
  - [License](#license)
  - [Acknowledgements](#acknowledgements)
  - [Links](#links)

---

## Features

- **Continuous data acquisition** from a 3‑channel (EHZ, EHN, EHE) geophone at 100 Hz
- **MCU settings handshake** – sends ADC gain and sample rate to the Arduino on startup and verifies the echo before streaming begins
- **Robust RS-422 communication** with automatic heartbeat to keep the Arduino streaming
- **SDS-compliant MiniSEED archive** – writes to a standard SeisComp Data Structure directory tree, with automatic midnight splitting so each sample lands in the correct day file
- **StationXML generation** – builds a fully calibrated `station.xml` with GD-4.5 PAZ response stages; automatically manages instrument response epochs when hardware settings change
- **STA/LTA trigger** – detects earthquakes on the vertical channel and triggers an early archive flush after 5 minutes, then resumes the normal schedule
- **WebSocket live feed** – serves decimated waveform data (1 second updates) to connected clients
- **Push notifications** – dedicated `NotifierSender` thread sends an immediate Telegram (or any Apprise-compatible service) alert on detection, then collects 60 s of post-event data and attaches an interactive HTML waveform plot
- **Modular design** – each component runs in its own thread, communicating via thread‑safe queues
- **Configurable via YAML** – station metadata, channel mapping, ADC settings, sampling rate, decimation factor, and more

---

## Hardware Requirements

- **Raspberry Pi** (any model with GPIO, tested on RPi 3/4)
- **Arduino‑based digitizer** (code provided in separate repository)
  - Sampling at up to 100 Hz, 3 channels
  - Communicates over RS-422 at 250 000 baud
  - Receives a settings frame on startup, echoes it back for verification
  - Expects a heartbeat pulse every 500 ms to continue streaming
- **MAX485** or equivalent RS-422 transceiver connected to the Pi's UART and a GPIO pin (e.g., GPIO5) for direction control
- **GD-4.5 geophone** (3‑component, 4.5 Hz natural frequency) with appropriate pre‑amplifier and shielded cables

> 📌 **Arduino firmware**: [rpi-seism-reader](https://github.com/ch3p4ll3/rpi-seism-reader) – handles ADC reading, packet framing, RS-422 transmission, and settings acknowledgement.

---

## Software Stack

- Python 3.7+ (managed with [UV](https://docs.astral.sh/uv/))
- [ObsPy](https://github.com/obspy/obspy) – MiniSEED I/O, decimation, and StationXML generation
- [pyserial](https://github.com/pyserial/pyserial) – serial communication
- [websockets](https://github.com/aaugustin/websockets) – WebSocket server
- [numpy](https://numpy.org/) – data handling
- [gpiozero](https://gpiozero.readthedocs.io/) – GPIO control (with mock fallback for development)
- [PyYAML](https://pyyaml.org/) – YAML configuration loading
- [Pydantic](https://docs.pydantic.dev/) – settings validation
- [Apprise](https://github.com/caronc/apprise) – multi-platform push notifications
- [Plotly](https://plotly.com/python/) – interactive HTML waveform charts attached to notifications
- [pandas](https://pandas.pydata.org/) – buffer-to-DataFrame conversion for chart generation

---

## Installation with UV

[UV](https://docs.astral.sh/uv/) is a fast Python package installer and resolver.  
If you don't have it yet, install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then clone this repository and install dependencies:

```bash
git clone https://github.com/ch3p4ll3/rpi-seism.git
cd rpi-seism
uv sync                # install dependencies
```

---

## Configuration via YAML

All system settings are defined in `data/config.yml`. If the file is not present, one will be created automatically with the default configuration on first run.

### Default configuration

```yaml
start_date: "2025-01-01T00:00:00+00:00"

station:
  network: XX
  station: RPI3
  latitude: 0.0
  longitude: 0.0
  elevation: 0.0

decimation_factor: 4

mcu:
  sampling_rate: 100
  adc_gain: 6
  adc_sample_rate: 11
  vref: 2.5

channels:
  - name: EHZ
    adc_channel: 0
    orientation: vertical
    sensitivity: 28.8
  - name: EHN
    adc_channel: 1
    orientation: north
    sensitivity: 28.8
  - name: EHE
    adc_channel: 2
    orientation: east
    sensitivity: 28.8

notifiers:
  - url: "tgram://{bot_token}/{chat_id}/"
    enabled: true
```

| Key | Description |
|---|---|
| `start_date` | ISO-8601 timestamp marking when this instrument configuration took effect. Used as the channel epoch start in `station.xml`. **Must be updated whenever hardware settings change.** |
| `station.network` / `station.station` | SEED network and station identifiers |
| `station.latitude/longitude/elevation` | Geographic coordinates written into `station.xml` |
| `decimation_factor` | Downsampling factor applied by the WebSocket sender (e.g., 4 → 25 Hz output) |
| `mcu.sampling_rate` | Must match the Arduino's output rate (100 Hz) |
| `mcu.adc_gain` | ADS1256 programmable gain amplifier setting |
| `mcu.adc_sample_rate` | ADS1256 data rate register value |
| `mcu.vref` | ADS1256 VREF, default 2.5V |
| `channels` | List of channels with SEED names, ADC indices, sensitivity, and physical orientations |
| `notifiers` | Apprise-compatible notification URLs (Telegram, Slack, etc.) |

---

## Usage

Start the application with:

```bash
uv run python -m src.main
```

On startup the system will:

1. Validate configuration and generate `station.xml` if needed (or update epochs if settings changed)
2. Send ADC settings to the Arduino over RS-422 and wait for echo confirmation
3. Start all four threads

Stop with `Ctrl+C`. On shutdown, any buffered data is flushed to disk.

### Frontend

A companion web interface is available to display live waveforms and event notifications:

📁 **[rpi-seism-frontend](https://github.com/ch3p4ll3/rpi-seism-web)** – Angular‑based dashboard that connects to the WebSocket endpoint.

---

## In‑Depth Explanation of Each Thread

### 1. Reader Thread

- **Responsibility**: Sole owner of the serial port and the RS-422 direction-control GPIO.
- **Startup handshake**: Before entering the main loop, it serialises the current `MCUSettings` into a binary frame and transmits it to the Arduino over RS-422. It then waits up to 10 seconds for the Arduino to echo back an identical frame (identified by the `0xCC 0xDD` header). If the echo is absent or mismatched, a `MCUNoResponse` exception is raised and the application stops.
- **Operation**:
  - Sends a heartbeat byte (`0x01`) every `heartbeat_interval` (default 0.5 s) to keep the Arduino streaming. Before sending, it sets the MAX485 to transmit mode, then immediately back to receive.
  - Reads incoming bytes into a ring buffer, searches for the packet header (`0xAA 0xBB`), and validates the checksum (XOR of all payload bytes).
  - Upon a valid packet, unpacks three 32‑bit signed integers (one per channel) from the `Sample` struct.
  - Formats the decoded data as `{"timestamp": time.time(), "measurements": [{"channel": ch_obj, "value": val}, ...]}` and places it into every downstream queue.
- **Why a thread?** It must continuously poll the serial port without blocking other tasks, and the heartbeat timing must be precise.

### 2. MSeedWriter Thread

- **Responsibility**: Buffer incoming samples and write them to a SeisComp Data Structure (SDS) archive.
- **SDS layout**: Files are written to `OUTPUT_DIR/YEAR/NET/STA/CHAN.D/NET.STA.LOC.CHAN.D.YEAR.DAY` and are appended to (not overwritten) on subsequent write cycles. If the buffer spans midnight, it is automatically split so each slice lands in the correct day file.
- **Operation**:
  - Maintains a per‑channel list of raw `int32` values and the start time of the current batch.
  - Normally, writes and clears the buffer every `write_interval_sec` (default 1800 s = 30 min).
  - When the `earthquake_event` is set by the trigger, it schedules the *next* flush to happen in 5 minutes (`event_write_delay_sec`), ensuring that event waveforms are persisted promptly without waiting for the normal interval. If multiple triggers occur during the countdown, the timer resets.
  - On final shutdown, any remaining buffered data is flushed.
- **Why a thread?** Writing to disk can be I/O-bound; buffering lets the writer operate independently from the high-rate data stream.

### 3. TriggerProcessor Thread

- **Responsibility**: Detect seismic events using ObsPy's recursive STA/LTA algorithm on the vertical channel (`EHZ`).
- **Operation**:
  - Listens for packets and extracts the value for the trigger channel.
  - Appends each new sample to a rolling `deque` buffer sized at `2 × LTA window` (default: `2 × 10 s × 100 Hz = 2000 samples`). The oversized buffer ensures the algorithm has a stable long-term baseline before producing meaningful ratios.
  - Once the buffer has accumulated at least `nlta` samples, it calls `obspy.signal.trigger.recursive_sta_lta()` on the full buffer array. The last element of the returned characteristic function array is taken as the current STA/LTA ratio.
  - Uses a dual-threshold (hysteresis) scheme to prevent chattering:
    - **Rising edge** (`ratio > thr_on`, default 3.5, and not already triggered): sets the shared `earthquake_event`, logs the detection, and dispatches a push notification via Apprise.
    - **Falling edge** (`ratio < thr_off`, default 1.5, and currently triggered): clears the event.
- **Why a thread?** Processing runs for every sample and must not be blocked by the I/O-bound writer or WebSocket sender.

### 4. WebSocketSender Thread

- **Responsibility**: Provide a live data feed to web clients with decimated waveforms.
- **Operation**:
  - Runs an asyncio event loop that hosts a WebSocket server.
  - Maintains a sliding-window buffer (size = `window_seconds * sampling_rate`) per channel.
  - Every `step_seconds` (e.g., 1 s), it takes the current window for each channel, creates an ObsPy Trace, and applies decimation (with anti‑alias filtering) using `trace.decimate(decimation_factor)`.
  - Extracts only the newly added decimated samples and broadcasts them as JSON:
    ```json
    {
      "channel": "EHZ",
      "timestamp": "2025-03-23T12:34:56.789Z",
      "fs": 25,
      "data": [123, 125, ...]
    }
    ```
  - Manages client connections, sending updates only to currently active clients.
- **Why a thread?** It uses asyncio, which runs in its own thread to avoid interfering with the other synchronous threads.

### 5. NotifierSender Thread

- **Responsibility**: Send rich push notifications when a seismic event is detected, including an attached interactive waveform plot.
- **Operation**:
  - Maintains a rolling `deque` buffer sized at `2 × 60 s × sampling_rate` (default 12 000 samples per channel) — enough to hold 60 s before and 60 s after the trigger moment.
  - Continuously consumes packets from its queue and appends them to the buffer; this ensures the pre-event context is already available the moment a trigger fires.
  - When `earthquake_event` is set **and** at least 30 s have passed since the last notification (cooldown), it immediately dispatches an alert via Apprise:
    ```
    ⚠️ Earthquake Alert — Significant seismic activity detected!
    ```
  - It then enters `_handle_event()`, which waits until the buffer accumulates a further `points_per_window` samples (≈ 60 s of post-event data), or until shutdown is requested.
  - Once the 120 s window is complete, `_generate_plotly_graph()` flattens the buffer into a pandas `DataFrame`, builds a multi-subplot Plotly figure (one row per channel, shared X-axis), and serialises it as a self-contained HTML file.
  - `_send_notification()` writes the HTML to a temporary file and passes it as an Apprise attachment — a workaround for Apprise's incomplete in-memory stream support.
- **Why a thread?** Waiting for 60 s of post-event data is a long blocking operation. Running it in its own thread prevents it from starving the trigger, writer, or WebSocket threads.

On startup, the application calls `ensure_station_xml()` to maintain a calibrated `station.xml` alongside the SDS archive. This file encodes the full GD-4.5 instrument response so that recorded waveforms can be properly deconvolved by analysis tools like ObsPy or SeisComp.

The response chain consists of two stages:

1. **PAZ stage** – standard GD-4.5 poles and zeros in Laplace (rad/s) representation, with stage gain equal to the per-channel `sensitivity` (V·s/m).
2. **ADC gain stage** – converts volts to digital counts, computed as `(adc_gain × 2²³) / vref`.

**Epoch management** prevents accidental corruption of the archive's provenance:

| Scenario | Behaviour |
|---|---|
| First run – no `station.xml` | File is generated; a JSON sidecar (`.sha256`) is written to track the settings fingerprint and `start_date`. |
| Settings unchanged | Nothing happens. |
| Settings changed, `start_date` unchanged | **Application refuses to start.** You must update `start_date` to the date/time of the hardware change. |
| Settings changed, `start_date` updated | Open channel epochs are automatically closed (their `end_date` is set) and new epochs are appended. The sidecar is updated. |

> ⚠️ **Never delete `station.xml` or the `.sha256` sidecar.** Both files should be kept in version control alongside the data archive.

---

## Data Flow Diagram

```
                +-------------+
                |   Arduino   |
                |   (100 Hz)  |
                +------+------+
                       | RS-422 (250 kbaud)
                       v
+-------------------------------------------------+
|  Reader Thread                                  |
|  - Settings handshake on startup                |
|  - Reads serial, verifies checksum              |
|  - Sends heartbeat every 500 ms                 |
|  - Distributes packets to all queues            |
+--------+----------+------------+----------------+
         |          |            |            |
         v          v            v            v
   +--------+  +----------+  +------+  +----------+
   |mseed_q |  |trigger_q |  | ws_q |  |notify_q  |
   +--------+  +----------+  +------+  +----------+
         |          |            |            |
         v          v            v            v
+----------+  +----------+  +----------+  +------------------+
|MSeedWriter|  |Trigger   |  |WebSocket |  | NotifierSender   |
|- Buffers  |  |Processor |  |Sender    |  | - Rolling 120s   |
|- SDS      |  |- Recursive|  |- Sliding |  |   buffer         |
|- Midnight |  |  STA/LTA  |  |  window  |  | - Immediate text |
|  split    |  |- Sets     |  |- Decimates|  |   alert          |
|- Early    |  |  event on |  |- JSON    |  | - 60s post-event |
|  flush    |  |  trigger  |  |  broadcast|  |   data wait      |
+----------+  +-----+----+  +----------+  | - Plotly HTML    |
      ^              |                     |   attachment     |
      |   earthquake_event                 +------------------+
      +--------------------+
```

---

## Customising the STA/LTA Detector

The `TriggerProcessor` uses [ObsPy's `recursive_sta_lta`](https://docs.obspy.org/packages/autogen/obspy.signal.trigger.recursive_sta_lta.html) function, which is numerically efficient and well-suited to continuous single-sample updates. The algorithm parameters are currently defined as class attributes in `trigger_processor.py`:

| Parameter | Default | Description |
|---|---|---|
| `sta_sec` | `0.5` s | Short-term average window length |
| `lta_sec` | `10.0` s | Long-term average window length |
| `thr_on` | `3.5` | STA/LTA ratio above which an event is declared |
| `thr_off` | `1.5` | STA/LTA ratio below which the event is cleared |
| `trigger_channel` | `"EHZ"` | SEED channel name used for detection |

The rolling data buffer is sized at `2 × nlta` samples to ensure a stable LTA baseline before ratios are considered meaningful. No trigger decision is made until the buffer is at least `nlta` samples deep.

A typical starting point for a quiet site is the default configuration above. Noisy environments may require a higher `thr_on` (e.g., 5.0–8.0) or a shorter `sta_sec`. These will be moved to YAML configuration in a future release.

---

## Troubleshooting

- **MCU no response on startup**: Verify the serial port, baud rate (250 000), and that the Arduino firmware supports the settings handshake (`0xCC 0xDD` echo). Check the wiring of the MAX485 DE/RE pin.
- **No data in MiniSEED files**: Check that packets arrive with header `0xAA 0xBB` and a valid XOR checksum. Enable debug logging in the Reader.
- **`StationXMLEpochError` on startup**: You changed ADC settings or channel sensitivity without updating `start_date`. Set `start_date` in `config.yml` to the date/time of the hardware change and restart.
- **GPIO errors**: If running on a non‑Raspberry Pi (or without GPIO), the code automatically falls back to a mock pin factory. For real deployment, ensure `gpiozero` is installed and the correct GPIO pin number is set in the config.
- **WebSocket not connecting**: Verify the port (default 8765) is not blocked by a firewall and that the frontend points to the correct IP.
- **Earthquake not detected**: Tune the STA/LTA thresholds. The current implementation may need adjustment for your site's noise level and target magnitude range.
- **UV not found**: Follow the [UV installation guide](https://docs.astral.sh/uv/getting-started/installation/).

---

## Contributing

Contributions are welcome! Please open an issue or pull request for any improvements, bug fixes, or documentation updates.

---

## License

[GNU General Public License v3.0](LICENSE)

---

## Acknowledgements

- Inspired by the [Raspberry Shake](https://raspberryshake.org/) project
- STA/LTA algorithm based on common seismic processing practices
- Built with [ObsPy](https://obspy.org/) – a great toolkit for seismology

---

## Links

- [Arduino digitizer firmware](https://github.com/ch3p4ll3/rpi-seism-reader)
- [Web frontend](https://github.com/ch3p4ll3/rpi-seism-web)