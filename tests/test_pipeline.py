"""End to end with the diff detector on a synthetic clip: a 'bottle' appears at 2 s and is removed at 18 s."""
import sys, time, copy, json, tempfile
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from pipeline import Pipeline

CFG = json.loads((Path(__file__).parent.parent / "backend" / "config.json").read_text())


def make_clip(path, fps=10, secs=30, w=640, h=360):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    rng = np.random.default_rng(1)
    base = np.tile(np.linspace(90, 130, w, dtype=np.uint8), (h, 1))
    for i in range(fps * secs):
        t = i / fps
        f = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
        f = np.clip(f.astype(int) + rng.integers(-3, 4, f.shape), 0, 255).astype(np.uint8)
        if 2 <= t < 18:
            cv2.rectangle(f, (300, 220), (330, 270), (230, 230, 240), -1)
        vw.write(f)
    vw.release()


def test_ticket_opens_then_closes():
    tmp = Path(tempfile.mkdtemp())
    make_clip(tmp / "c.mp4")
    cfg = copy.deepcopy(CFG)
    cfg.update(source=str(tmp / "c.mp4"), reference=None, frame_stride=1, loop=False, realtime=False)
    cfg["diff"]["mask_people"] = False
    cfg["zones"] = [{"id": "main", "name": "Main floor", "poly": [[0, 0], [640, 0], [640, 360], [0, 360]]}]
    events, lows = [], []
    p = Pipeline(cfg, lambda ev, jpg: events.append(ev), lambda s, f, i: lows.append(s[0]["index"]))
    p.start()
    assert p.finished.wait(60), "pipeline did not finish"
    p.stop = True
    kinds = [e["action"] for e in events]
    print(kinds, "lowest index", min(lows) if lows else None)
    assert kinds == ["open", "clean"]


if __name__ == "__main__":
    test_ticket_opens_then_closes()
    print("ok test_ticket_opens_then_closes")
