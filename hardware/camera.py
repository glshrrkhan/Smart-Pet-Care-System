# hardware/camera.py — Smart Pet Care
# CSI clone Pi camera — MJPEG live stream via picamera2
# Install: sudo apt install -y python3-picamera2 libcamera-apps

import io
import time
import threading

try:
    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder
    from picamera2.outputs import FileOutput
    CAMERA_MODE = "picamera2"
except ImportError:
    CAMERA_MODE = "mock"
    print("[Camera] picamera2 not found — running in mock mode.")


class StreamOutput(io.BufferedIOBase):
    """Thread-safe buffer that holds the latest MJPEG frame."""

    def __init__(self):
        self.frame     = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class PetCamera:
    """
    Manages the Pi CSI camera and produces an MJPEG stream.

    Usage:
        camera = PetCamera()
        camera.start()
        # In Flask route:
        return Response(camera.generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
        camera.stop()   # on shutdown
    """

    def __init__(self, width=640, height=480, framerate=24):
        self.width     = width
        self.height    = height
        self.framerate = framerate
        self._camera   = None
        self._output   = None
        self._running  = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if CAMERA_MODE == "mock":
            self._running = True
            print("[Camera] Mock mode — no real stream.")
            return

        if self._running:
            return  # already started

        try:
            self._camera = Picamera2()
            config = self._camera.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                controls={"FrameRate": self.framerate},
            )
            self._camera.configure(config)
            self._output = StreamOutput()
            self._camera.start_recording(MJPEGEncoder(), FileOutput(self._output))
            self._running = True
            print(f"[Camera] Started — {self.width}x{self.height} @ {self.framerate}fps")
        except Exception as exc:
            self._running = False
            print(f"[Camera] Failed to start: {exc}")
            raise

    def stop(self):
        if CAMERA_MODE == "mock" or not self._running:
            return
        try:
            self._camera.stop_recording()
            self._camera.close()
        except Exception as exc:
            print(f"[Camera] Stop error: {exc}")
        finally:
            self._running = False
            self._camera  = None
            print("[Camera] Stopped.")

    # ── Stream generator ──────────────────────────────────────────────────────

    def generate_frames(self):
        """
        Generator yielded by Flask's Response for MJPEG streaming.
        Each iteration waits for a new frame then yields it.
        """
        if CAMERA_MODE == "mock":
            # Yield a tiny placeholder JPEG so the browser gets something
            import base64
            # 1x1 grey JPEG (valid minimal JPEG bytes)
            placeholder = (
                b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
                b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
                b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
                b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e!'
                b'\x1f\x00;\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
                b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00'
                b'\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08'
                b'\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03'
                b'\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12'
                b'!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1'
                b'\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJ'
                b'STUVWXYZ\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\x0a\xff\xd9'
            )
            while True:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + placeholder + b'\r\n')
                time.sleep(1 / 10)
            return

        while self._running:
            with self._output.condition:
                self._output.condition.wait(timeout=2.0)
                frame = self._output.frame
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n'
                       + frame + b'\r\n')
