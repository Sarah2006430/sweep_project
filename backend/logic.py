"""Litter items, cleanliness index and ticket triggers. Pure Python, so it can be unit-tested."""


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def inside(poly, x, y):
    c, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def area(poly):
    n = len(poly)
    return abs(sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))) / 2


def band(idx):
    return "Clean" if idx >= 85 else "Fair" if idx >= 60 else "Poor"


PRIORITY = {"overflow": "High", "bag": "Medium", "litter": "Low", "debris": "Low"}


class Item:
    def __init__(self, id, cls, box, t, zone, conf):
        self.id, self.cls, self.box, self.zone, self.conf = id, cls, box, zone, conf
        self.first = self.last = t
        self.anchor = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        self.seen, self.ticketed = 1, False

    @property
    def age(self):
        return self.last - self.first


class Logic:
    def __init__(self, cfg):
        self.r, self.sc = cfg["rules"], cfg["score"]
        self.zones = [dict(id=z["id"], name=z["name"], poly=z["poly"], area=area(z["poly"]) or 1) for z in cfg["zones"]]
        self.reset()

    def reset(self):
        self.items, self.nid = {}, 0

    def zone_of(self, box):
        cx, cy = (box[0] + box[2]) / 2, box[3] - (box[3] - box[1]) * 0.2  # near the floor contact point
        return next((z for z in self.zones if inside(z["poly"], cx, cy)), None)

    def confirmed(self, i):
        return i.age >= self.r["confirm_s"] and i.seen >= 3

    def update(self, dets, t):
        """dets: list of (class, confidence, (x1, y1, x2, y2)). Returns (events, zone stats)."""
        r, ev, w = self.r, [], self.sc["weights"]
        pairs = sorted(((iou(i.box, d[2]), i, k) for i in self.items.values() for k, d in enumerate(dets)),
                       key=lambda p: -p[0])
        used, matched = set(), set()
        for s, i, k in pairs:
            if s < r["iou_match"]:
                break
            if i.id in used or k in matched:
                continue
            cls, conf, box = dets[k]
            a0, a1 = (i.box[2] - i.box[0]) * (i.box[3] - i.box[1]), (box[2] - box[0]) * (box[3] - box[1])
            if not 0.5 <= a1 / max(a0, 1) <= 2:
                continue  # blob grew or shrank a lot: something merged with it (a person walking past), not the same item
            used.add(i.id)
            matched.add(k)
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            if ((cx - i.anchor[0]) ** 2 + (cy - i.anchor[1]) ** 2) ** 0.5 > r["still_px"]:
                i.first, i.seen, i.anchor = t, 0, (cx, cy)  # it moved: people and carried bags are not litter until they stop
            i.box = tuple(0.6 * a + 0.4 * b for a, b in zip(i.box, box))
            i.last, i.seen, i.conf = t, i.seen + 1, max(i.conf, conf)
            if w.get(cls, 0) > w.get(i.cls, 0):
                i.cls = cls
        for k, (cls, conf, box) in enumerate(dets):
            if k in matched:
                continue
            z = self.zone_of(box)
            if z:
                self.nid += 1
                self.items[self.nid] = Item(self.nid, cls, box, t, z["id"], conf)
        names = {z["id"]: z["name"] for z in self.zones}
        for i in list(self.items.values()):
            gone = t - i.last
            if gone > r["clean_after_s"]:
                del self.items[i.id]
                if i.ticketed:
                    ev.append(dict(action="clean", key=f"item:{i.id}", zone=names[i.zone], cls=i.cls))
            elif not i.ticketed and gone <= r["gap_s"] and self.confirmed(i) and i.age >= r["ticket_after_s"]:
                i.ticketed = True
                ev.append(dict(action="open", key=f"item:{i.id}", zone=names[i.zone], cls=i.cls,
                               priority=PRIORITY.get(i.cls, "Low"), box=i.box, age=round(i.age)))
        stats = []
        for z in self.zones:
            its = [i for i in self.items.values() if i.zone == z["id"] and self.confirmed(i) and t - i.last <= r["gap_s"]]
            pen = sum(w.get(i.cls, 6) * (1 + min(i.age / self.sc["age_ref"], 2)) for i in its)
            cover = sum((i.box[2] - i.box[0]) * (i.box[3] - i.box[1]) for i in its) / z["area"]
            dens = min(self.sc["density_cap"], self.sc["density"] * cover)
            idx = round(max(0, 100 - pen - dens))
            stats.append(dict(id=z["id"], name=z["name"], index=idx, band=band(idx), items=len(its),
                              oldest=round(max((i.age for i in its), default=0)), coverage=round(cover * 100, 1)))
        return ev, stats

    def view(self, t):
        return [dict(id=i.id, cls=i.cls, box=[round(v) for v in i.box], age=round(i.age),
                     confirmed=self.confirmed(i), ticketed=i.ticketed) for i in self.items.values()
                if t - i.last <= self.r["gap_s"]]
