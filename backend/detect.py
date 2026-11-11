"""Two interchangeable detectors. Both return [(class, confidence, (x1, y1, x2, y2))]."""
import os
import cv2
import numpy as np


class DiffDetector:
    """No training needed. Compares each frame with a clean reference of the fixed camera view and
    reports blobs that are new. Works for staged demos; a trained model is the accurate option."""

    def __init__(self, cfg):
        d = cfg.get("diff", {})
        self.thr = d.get("threshold", 28)
        self.minf, self.maxf = d.get("min_area_frac", 0.0006), d.get("max_area_frac", 0.08)
        p = cfg.get("reference")
        self.ref_img = cv2.imread(p) if p and os.path.exists(p) else None
        self.ref, self.people, self.k = None, None, np.ones((5, 5), np.uint8)
        if d.get("mask_people", True) and cfg.get("person_model"):
            try:
                from ultralytics import YOLO  # AGPL-3.0, see README
                self.people = YOLO(cfg["person_model"])
            except Exception:
                self.people = None

    @staticmethod
    def _gray(f):  # kept under this name; compares colour, not grey, so blue or orange litter on a grey floor is seen
        return cv2.GaussianBlur(f, (9, 9), 0)

    def detect(self, frame):
        g = self._gray(frame)
        if self.ref is None:
            ok = self.ref_img is not None and self.ref_img.shape == frame.shape
            self.ref = (self._gray(self.ref_img) if ok else g).astype(np.float32)
            return []
        raw = cv2.absdiff(g, self.ref.astype(np.uint8)).max(axis=2) > self.thr
        pm = np.zeros(raw.shape, bool)
        if self.people is not None:  # people are not litter
            for b in self.people(frame, classes=[0], conf=0.3, verbose=False)[0].boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = [int(v) for v in b]
                pm[max(0, y1 - 15):y2 + 15, max(0, x1 - 15):x2 + 15] = True
        m = (raw & ~pm).astype(np.uint8) * 255
        m = cv2.morphologyEx(cv2.morphologyEx(m, cv2.MORPH_OPEN, self.k), cv2.MORPH_CLOSE, self.k)
        keep = ~raw & ~pm  # follow slow lighting changes, never absorb a blob or a person
        self.ref[keep] = 0.995 * self.ref[keep] + 0.005 * g[keep]
        out, total = [], frame.shape[0] * frame.shape[1]
        for c in cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            if self.minf * total <= cv2.contourArea(c) <= self.maxf * total:
                x, y, w, h = cv2.boundingRect(c)
                out.append(("litter", 0.5, (float(x), float(y), float(x + w), float(y + h))))
        return out


class YoloDetector:
    """Your fine-tuned litter model (see train/). class_map turns dataset class names into
    litter / debris / bag / overflow; ignore_classes lists things like intact bins."""

    def __init__(self, cfg):
        from ultralytics import YOLO  # AGPL-3.0, see README
        self.m, self.cfg = YOLO(cfg["model"]), cfg
        self.cmap, self.ign = cfg.get("class_map", {}), set(cfg.get("ignore_classes", []))

    def detect(self, frame):
        r = self.m(frame, conf=self.cfg["conf"], imgsz=self.cfg["imgsz"], verbose=False)[0]
        out = []
        for b, c, k in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy(), r.boxes.cls.int().cpu().tolist()):
            name = r.names[k]
            if name not in self.ign:
                out.append((self.cmap.get(name, "litter"), float(c), tuple(float(v) for v in b)))
        return out


def make(cfg):
    return YoloDetector(cfg) if cfg.get("detector") == "yolo" else DiffDetector(cfg)
