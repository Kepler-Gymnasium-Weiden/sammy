# Vision

The robot's vision pipeline is split into two engine-side modules and a
single student-facing namespace.

## Pipeline

```
       USB camera
            │  cv2.VideoCapture (CAP_DSHOW on Windows)
            ▼
    _CaptureThread    in pib/_engine/modules/camera_backend.py
            │  pulls frames at the configured FPS, converts BGR→RGB
            ├──────────► CameraBackend.frame_ready  (Qt signal)
            │               │
            │               ▼
            │       CameraSettingsPanel (live preview, with optional overlay)
            │
            └──► CameraBackend.latest_frame()      (consumer-pulled, thread-safe)
                       │
                       ▼
        VisionBackend.detect()      in pib/_engine/modules/vision_backend.py
                       │  YOLOv8n via ultralytics; CPU; 80 COCO classes
                       ▼
                List[{label, confidence, box}]

       client side:                   engine side:
       robot.eyes.what_do_you_see() ─► EyesBackend.what_do_you_see()
                                          │
                                          ├── camera_on() if not running
                                          └── VisionBackend.detect_labels()
```

## Student API

Vision lives under `robot.eyes` because, from a student's perspective, "the
eyes" are both output (animation) and input (perception). All methods block:

```python
robot.eyes.camera_on()          # explicit; called automatically by what_do_you_see()
robot.eyes.camera_off()
labels = robot.eyes.what_do_you_see()     # list[str]
robot.eyes.can_see("person")              # bool
```

The first call to `what_do_you_see()` may take a few seconds because YOLO
weights (~6 MB) are downloaded into the ultralytics cache. Subsequent calls
take <100 ms on a typical laptop CPU.

## Privacy

A camera in a classroom captures children. Per the organisation's information
security policy, GDPR, and the EU AI Act, frames must not be sent to external
AI services. This is enforced **by design**, not by configuration:

- `VisionBackend` uses YOLOv8n via the local `ultralytics` package only. No
  cloud client libraries are imported anywhere in the codebase.
- Frames are kept inside the engine process. There is no current mechanism
  to send raw frames to the client; `robot.eyes.see()` is intentionally
  not implemented for v1.
- A "REC" indicator on the eye display whenever the capture thread is
  running makes it visually obvious when the camera is reading frames.
  *(Implementation note: indicator currently absent in the prototype — easy
  follow-up: add a small dot overlay in `eye_widget.py` driven by
  `CameraBackend.frame_ready`.)*

If a cloud model is ever needed (richer scene descriptions, OCR, etc.):

- Must be opt-in per call, not globally configurable.
- Must run a local face-blur pass on the frame before upload.
- Must log every upload to a local audit file.
- Must surface a visible warning in the GUI while active.

None of that is in v1. The 80 COCO classes (person, cup, dog, laptop, book,
bottle, …) cover the teaching use cases without ever sending data anywhere.

## Graceful degradation

Both `opencv-python` and `ultralytics` are optional dependencies:

| Installed?               | What works                                                  |
|--------------------------|-------------------------------------------------------------|
| Neither                  | Camera tab shows "OpenCV not installed". `what_do_you_see` returns `[]`. |
| `opencv-python` only     | Live preview works. `what_do_you_see` returns `[]`.         |
| Both                     | Full pipeline: detection labels, preview overlay.           |

`camera_backend.py` and `vision_backend.py` each gate their heavy imports
behind `try/except ImportError` and expose `is_available()` so the UI and
the dispatcher can react appropriately.

## Where shared-memory frames will go

Eventually `robot.eyes.see()` will return the latest frame to the student
as a numpy array. Sending 900 KB of RGB over JSON per call is wasteful, so
the plan is:

1. `pib/_engine/ipc/frame_server.py` publishes RGB frames into a
   `multiprocessing.shared_memory.SharedMemory` block + a small lock-free
   sequence counter.
2. `pib/api/_frames.py:FrameReader` opens the same shared memory by name
   (negotiated during the engine handshake) and exposes `latest()`.
3. `robot.eyes.see()` simply returns `FrameReader.latest()` — no IPC call.

For v1 both files are intentionally minimal placeholders so the structure
is in place but no shared-memory code runs until it's actually needed.
