"""Runs the synthetic demo clip through the real pipeline: four tickets must open and close, nothing else."""
import sys, copy, json
from pathlib import Path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root / "backend")); sys.path.insert(0, str(root / "tools"))
import make_demo_clip
from pipeline import Pipeline


def test_four_tickets_open_and_close():
    make_demo_clip.main()
    cfg = json.loads((root / "backend" / "config.json").read_text())
    cfg.update(source=str(root / "data/demo/floor.mp4"), reference=str(root / "data/demo/reference.jpg"),
               loop=False, realtime=False)
    events = []
    p = Pipeline(cfg, lambda ev, jpg: events.append(ev), lambda s, f, i: None)
    p.start()
    assert p.finished.wait(120)
    p.stop = True
    for e in events:
        print(e["action"], e["zone"], e.get("cls"), e.get("age"), e["key"])
    kinds = [e["action"] for e in events]
    assert kinds.count("open") == 4 and kinds.count("clean") == 4 and len(kinds) == 8


if __name__ == "__main__":
    test_four_tickets_open_and_close()
    print("ok test_four_tickets_open_and_close")
