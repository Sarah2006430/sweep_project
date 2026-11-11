"""Video in, detections out, cleanliness logic applied, overlay drawn, JPEG frames published.
For video files the rules run on video time, so thresholds mean seconds of footage."""
import threading, time
import cv2
import numpy as np
import detect
from logic import Logic

GREEN, AMBER, RED, LIGHT = (152, 174, 108), (79, 176, 224), (92, 112, 229), (237, 234, 230)  # BGR
BAND = {"Clean": GREEN, "Fair": AMBER, "Poor": RED}


class Pipeline(threading.Thread):
    def __init__(self, cfg, on_event, on_stats, on_reset=lambda: None):
        super().__init__(daemon=True)
        self.cfg, self.on_event, self.on_stats, self.on_reset = cfg, on_event, on_stats, on_reset
        self.logic = Logic(cfg)
        self.latest, self.cond = None, threading.Condition()
        self.layers = {"boxes": True, "zones": True}
        self.fps, self.stop, self.restart = 0.0, False, False
        self.finished = threading.Event()
        self.stats, self.size = [], None

    def run(self):
        cfg = self.cfg
        det = detect.make(cfg)
        src = cfg["source"]
        is_file = not str(src).isdigit()
        cap = cv2.VideoCapture(src if is_file else int(src))
        vfps = cap.get(cv2.CAP_PROP_FPS) or 25
        stride = cfg.get("frame_stride", 1)
        step_t = stride / vfps
        frames, last_stats = 0, 0.0
        while not self.stop:
            if not cap.isOpened():
                print(f"[sweep] cannot open source {src!r}. Check 'source' in backend/config.json.")
                time.sleep(2)
                cap.open(src if is_file else int(src))
                continue
            if self.restart:
                self.restart = False
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.logic.reset()
                det = detect.make(cfg)
                frames = 0
                self.finished.clear()
                self.on_reset()
            t0 = time.monotonic()
            for _ in range(stride - 1):
                cap.grab()
            ok, frame = cap.read()
            if not ok:
                if frames == 0:
                    time.sleep(0.5)
                elif is_file and cfg.get("loop", True):
                    self.restart = True
                else:
                    self.finished.set()
                    time.sleep(0.2)
                continue
            self.size = (frame.shape[1], frame.shape[0])
            frames += stride
            t = frames / vfps if is_file else time.monotonic()
            events, self.stats = self.logic.update(det.detect(frame), t)
            jpg = self.render(frame, t)
            with self.cond:
                self.latest = jpg
                self.cond.notify_all()
            for ev in events:
                self.on_event(ev, jpg)
            if t0 - last_stats >= 0.5:
                last_stats = t0
                self.on_stats(self.stats, round(self.fps, 1), self.logic.view(t))
            spent = time.monotonic() - t0
            self.fps = 0.9 * self.fps + 0.1 / max(spent, 1e-3) if self.fps else 1 / max(spent, 1e-3)
            if is_file and cfg.get("realtime", True) and spent < step_t:
                time.sleep(step_t - spent)
        cap.release()

    def render(self, frame, t):
        out, L = frame.copy(), self.layers
        if L["zones"]:
            for z, s in zip(self.logic.zones, self.stats or [None] * len(self.logic.zones)):
                col = BAND[s["band"]] if s else LIGHT
                cv2.polylines(out, [np.array(z["poly"], np.int32)], True, col, 2)
        if L["boxes"]:
            for i in self.logic.view(t):
                x1, y1, x2, y2 = i["box"]
                col = RED if i["ticketed"] else AMBER if i["confirmed"] else (150, 150, 150)
                cv2.rectangle(out, (x1, y1), (x2, y2), col, 2 if i["confirmed"] else 1)
                if i["confirmed"]:
                    cv2.putText(out, f"{i['cls']} {i['age'] // 60}:{i['age'] % 60:02d}", (x1, max(12, y1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
        return cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tobytes()
