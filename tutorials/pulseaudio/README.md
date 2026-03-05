# Audio Recorder (PulseAudio)

This example demonstrates how to record audio directly on a Luxonis device using **PulseAudio (`parec`)** while streaming video from the device cameras.  
The recording is stored on the device and can be downloaded through the web interface.

---

## Demo

When running, the frontend shows:

- live video stream from the device
- controls to start/stop recording
- ability to download the last recorded audio file

---

## Usage

Running this example requires a **Luxonis device connected to your network**.  
Refer to the official documentation if you haven’t set up your device yet:

https://docs.luxonis.com/software-v3/

This example runs entirely on the device in **Standalone mode**.

---

## Available Parameters

```python
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)

-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the video stream. (default: 30)

--audio_device AUDIO_DEVICE
                    Optional PulseAudio source name (e.g. regular0, regular1, regular2).
```

---

## Standalone Mode (RVC4 only)

In standalone mode the application runs fully on the device.  
The frontend and backend services are served from the device itself.

To run this example you need the **oakctl** tool installed.

Installation instructions:

https://docs.luxonis.com/software-v3/oak-apps/oakctl

---

## Running the Example

### Connect to the device

```bash
oakctl connect <DEVICE_IP>
```

### Run the application

```bash
oakctl app run .
```

This will build and deploy the application to the device.

---

## Audio Recording

The example records audio using **PulseAudio** via the `parec` command.

Recordings are stored on the device under:

```path
/data/recordings
```

Each recording is saved as a WAV file:

```path
recording_<timestamp>.wav
```

---

## Audio Sources

Depending on the device configuration, multiple PulseAudio sources may be available.

Common examples:

```txt
regular0   - deep buffer stream with echo cancellation
regular1   - raw audio without post-processing
regular2   - low latency stream
```

The source can be selected via the `--audio_device` argument.

---

## Frontend Controls

| Control | Description |
|-------|-------------|
| Start Recording | Starts audio recording on the device |
| Stop | Stops recording |
| Download | Downloads the most recent recording |

The **Download** button is disabled while recording to prevent incomplete files from being retrieved.

---

## How It Works

The backend provides several services exposed to the frontend:

| Service | Purpose |
|-------|---------|
| Start Recording | Starts the PulseAudio recording process |
| Stop Recording | Stops recording and saves the file |
| List Recordings | Lists available recordings |
| Download Recording | Returns the selected recording encoded in base64 |

Audio recording is implemented using:

```txt
parec
```

which connects to the device’s PulseAudio server.

---

## File Structure

```txt
backend/
  src/
    main.py
    utils/
      audioRecorder.py
      download.py
      arguments.py

frontend/
  src/
    App.tsx
```
