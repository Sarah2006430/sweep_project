import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from logic import Logic

CFG = json.loads((Path(__file__).parent.parent / "backend" / "config.json").read_text())
BOTTLE = ("litter", 0.6, (300, 400, 330, 440))      # inside "Main floor"
OUTSIDE = ("litter", 0.6, (5, 5, 30, 30))          # outside every zone


def run(lg, dets, seconds, t0=0.0, fps=5):
    ev, st, t = [], None, t0
    for _ in range(int(seconds * fps)):
        t += 1 / fps
        e, st = lg.update(dets, t)
        ev += e
    return ev, st, t


def test_confirm_score_and_single_ticket():
    lg = Logic(CFG)
    ev, st, t = run(lg, [BOTTLE], 2)
    assert st[0]["index"] == 100 and not ev           # not confirmed yet (needs 3 s)
    ev, st, t = run(lg, [BOTTLE], 5, t)
    assert 85 < st[0]["index"] < 100 and not ev       # confirmed, score dips, no ticket yet
    ev, st, t = run(lg, [BOTTLE], 15, t)
    assert [e["action"] for e in ev] == ["open"] and ev[0]["priority"] == "Low"
    assert st[0]["index"] < 90                        # age makes the penalty grow


def test_ticket_closes_when_item_disappears():
    lg = Logic(CFG)
    ev, _, t = run(lg, [BOTTLE], 20)
    assert [e["action"] for e in ev] == ["open"]
    ev, st, t = run(lg, [], 8, t)
    assert [e["action"] for e in ev] == ["clean"] and st[0]["index"] == 100


def test_short_flicker_never_counts():
    lg = Logic(CFG)
    ev, st, t = run(lg, [BOTTLE], 2)
    ev, st, t = run(lg, [], 10, t)
    assert not ev and st[0]["index"] == 100 and not lg.items


def test_gap_in_detections_keeps_the_same_item():
    lg = Logic(CFG)
    _, _, t = run(lg, [BOTTLE], 10)
    _, _, t = run(lg, [], 1, t)                       # one second missed (hand passes in front)
    ev, _, t = run(lg, [BOTTLE], 8, t)
    assert [e["action"] for e in ev] == ["open"] and len(lg.items) == 1


def test_outside_zones_ignored_and_overflow_weighs_more():
    lg = Logic(CFG)
    _, st, _ = run(lg, [OUTSIDE], 10)
    assert st[0]["index"] == 100 and not lg.items
    lg = Logic(CFG)
    _, st, _ = run(lg, [("overflow", 0.7, (300, 400, 360, 480))], 5)
    assert st[0]["index"] <= 75


def test_moving_blob_is_not_litter():
    lg = Logic(CFG)
    t, ev = 0.0, []
    for n in range(100):                              # a blob sliding 12 px every 0.2 s (60 px/s)
        t += 0.2
        e, st = lg.update([("litter", 0.6, (100 + 12 * n, 400, 130 + 12 * n, 440))], t)
        ev += e
    assert not ev and st[0]["index"] == 100


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)
