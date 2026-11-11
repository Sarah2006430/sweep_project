"""FastAPI service: REST for tickets, WebSocket for live updates, MJPEG for video."""
import asyncio, json, os, time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import store
from pipeline import Pipeline

HERE = Path(__file__).parent
CFG = json.loads((HERE / "config.json").read_text())
ROOT = HERE.parent
for _k in ("source", "reference", "model", "person_model"):  # paths in config.json are relative to the project root
    _v = CFG.get(_k)
    if _v and not str(_v).isdigit() and not Path(_v).is_absolute() and (ROOT / _v).exists():
        CFG[_k] = str(ROOT / _v)
DATA = ROOT / "data"
EVID = DATA / "evidence"
EVID.mkdir(parents=True, exist_ok=True)

loop = None
clients: set = set()
keymap: dict = {}
hist = {z["id"]: deque(maxlen=150) for z in CFG["zones"]}
last = {"zones": [], "items": [], "fps": 0, "n": 0}


def fan(msg):
    for q in list(clients):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


def push(msg):
    if loop:
        loop.call_soon_threadsafe(fan, msg)


def view(row):
    if not row:
        return row
    d = dict(row)
    d["before_url"] = f"/evidence/{d['id']}/before.jpg"
    has_after = (EVID / d["id"] / "after.jpg").exists()
    d["after_url"] = f"/evidence/{d['id']}/after.jpg" if has_after and (d["status"] == "Cleaned" or d["status"] == "Archived") else None
    return d


def save(tid, name, jpg):
    d = EVID / tid
    d.mkdir(exist_ok=True)
    (d / name).write_bytes(jpg)


def on_event(ev, jpg):
    """Runs on the pipeline thread."""
    if ev["action"] == "open":
        tid = store.add(ev["zone"], ev["cls"], ev["priority"])
        keymap[ev["key"]] = tid
        save(tid, "before.jpg", jpg)
        push({"t": "ticket", "ticket": view(store.get(tid))})
    elif ev["action"] == "clean":
        tid = keymap.pop(ev["key"], None)
        row = tid and store.get(tid)
        if row and row["status"] in ("Open", "Assigned"):
            store.update(tid, status="Cleaned", cleaned=time.time(), note="Verified: item no longer visible")
            save(tid, "after.jpg", jpg)
            push({"t": "ticket", "ticket": view(store.get(tid))})


def on_stats(stats, fps, items):
    last.update(zones=stats, items=items, fps=fps)
    last["n"] += 1
    if last["n"] % 4 == 0:  # every ~2 s
        for s in stats:
            hist[s["id"]].append(s["index"])
    push({"t": "stats", "zones": stats, "items": items, "fps": fps})


def on_reset():
    store.archive_all()
    keymap.clear()
    for h in hist.values():
        h.clear()
    push({"t": "reset", "tickets": [view(r) for r in store.recent()]})


pipe = Pipeline(CFG, on_event, on_stats, on_reset)


@asynccontextmanager
async def lifespan(app):
    global loop
    loop = asyncio.get_running_loop()
    store.init(str(DATA / "sweep.db"))
    store.archive_all()
    if not os.environ.get("SWEEP_NO_PIPELINE"):
        pipe.start()
    yield
    pipe.stop = True


app = FastAPI(title="Sweep", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])  # dev only
app.mount("/evidence", StaticFiles(directory=EVID), name="evidence")


@app.get("/api/zones")
def zones():
    return {"zones": last["zones"], "history": {k: list(v) for k, v in hist.items()}, "fps": last["fps"]}


@app.get("/api/config")
def config():
    return {"zones": [{"id": z["id"], "name": z["name"], "poly": z["poly"]} for z in CFG["zones"]], "size": pipe.size}


@app.get("/api/tickets")
def tickets(archived: bool = False):
    return [view(r) for r in store.recent(archived)]


@app.get("/api/history")
def history():
    """Tickets from earlier runs and playback loops. They stay out of the live tracker but keep their evidence."""
    return [view(r) for r in store.archived()]


@app.get("/api/staff")
def staff():
    return CFG["staff"]


class Assign(BaseModel):
    staff: str


@app.post("/api/tickets/{tid}/assign")
def assign(tid: str, body: Assign):
    row = store.get(tid)
    if not row:
        raise HTTPException(404, "Unknown ticket")
    if row["status"] != "Open":
        raise HTTPException(409, "Only open tickets can be assigned")
    if body.staff not in CFG["staff"]:
        raise HTTPException(422, "Unknown staff member")
    store.update(tid, status="Assigned", staff=body.staff, assigned=time.time())
    push({"t": "ticket", "ticket": view(store.get(tid))})
    return view(store.get(tid))


@app.post("/api/tickets/{tid}/clean")
def clean(tid: str):
    """Manual close by a supervisor. The 'after' image is the current frame."""
    row = store.get(tid)
    if not row:
        raise HTTPException(404, "Unknown ticket")
    if row["status"] not in ("Open", "Assigned"):
        raise HTTPException(409, "Ticket is already closed")
    store.update(tid, status="Cleaned", cleaned=time.time(), note="Closed manually")
    if pipe.latest:
        save(tid, "after.jpg", pipe.latest)
    push({"t": "ticket", "ticket": view(store.get(tid))})
    return view(store.get(tid))


@app.post("/api/layers")
def layers(body: dict):
    pipe.layers.update({k: bool(v) for k, v in body.items() if k in pipe.layers})
    return pipe.layers


@app.post("/api/replay")
def replay():
    pipe.restart = True
    return {"ok": True}


@app.get("/video")
def video():
    def gen():
        prev = None
        while True:
            with pipe.cond:
                pipe.cond.wait(timeout=2)
                jpg = pipe.latest
            if jpg is None or jpg is prev:
                continue
            prev = jpg
            yield b"--f\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n"
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=f")


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    q = asyncio.Queue(maxsize=100)
    clients.add(q)
    try:
        await sock.send_json({"t": "hello", "zones": last["zones"], "items": last["items"], "staff": CFG["staff"],
                              "tickets": [view(r) for r in store.recent()],
                              "history": {k: list(v) for k, v in hist.items()}})
        while True:
            await sock.send_json(await q.get())
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(q)


# Must stay last: serves the dashboard at / while the API, /video and /ws above keep priority.
app.mount("/", StaticFiles(directory=HERE.parent / "frontend", html=True), name="ui")
