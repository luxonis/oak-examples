# Visual Decisions

This standalone RVC4 example shows how to use a decision model on camera images. YOLO-E finds selected objects in the live stream, and d3-lite answers typed questions about each tracked detection crop. The default demo finds people and asks whether each person is wearing a hat. Its frontend uses Luxonis components and provides text-class, confidence, IoU, decision enablement, per-object refresh, and question controls.

The scheduler runs one decision at a time. It tries never-evaluated objects first, then the oldest result that is due. A host-side IoU matcher gives detections stable IDs. Each crop comes from the frame paired with its YOLO-E detection; old crops are never queued. The refresh slider is a target: when detections exceed model capacity, actual refresh is slower. The UI shows each visible object's last result and age.

Each of the last 20 inference entries contains a full source frame with the selected box, the exact JPEG crop sent to d3-lite, YOLO-E class/confidence, the submitted questions, answer probabilities and latency. History is held in memory and clears on app restart. There are no generated explanations or calibrated accuracy claims.

## Run

Requires an RVC4 OAK device, `oakctl`, and network access during the first app build for the pinned model and prompt assets. Tested on an OAK4-D R9 with Luxonis OS 1.45.0. From this directory:

```bash
oakctl app run . -d <DEVICE_IP> --detach
```

Open the frontend URL printed by `oakctl`. To work on the frontend locally, use Node 22 or newer:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://localhost:4173/?ws_url=ws://<DEVICE_IP>:8765`.

## Model and runtime

- YOLO-E uses the pinned RVC4 Zoo model descriptor in `backend/src/depthai_models/` and the text-prompt embedding approach from `apps/data-collection`. The preview is H.264 encoded before being published as the `Video` topic; detections are published separately as `Annotations`.
- d3-lite uses the pinned Q8_0 model and projector checksums in `backend/src/models.py`. Assets are downloaded and verified during container construction.
- The official `luxonis/oakapp-base:1.5.2-llamacpp` image supplies llama.cpp 0.7.0. The backend starts `llama-server` on loopback and calls `/v1/systemone`; d3 model and projector request HTP0. The YOLO-E text prompt encoder runs on CPU only when classes change.
- The decision model supports Yes/No, choice, and ordered score questions. One crop request may include one to four questions. Every question sees that same crop.

## Checks

```bash
python3 -m unittest discover -s backend/tests -v
cd frontend && npm run lint && npm run build
```

See `docs/brief.md` and `docs/plans/current.md` for the first-demo scope and validation plan.
