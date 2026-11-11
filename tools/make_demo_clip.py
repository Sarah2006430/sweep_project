"""Synthetic demo clip: empty floor, passers-by, a visitor drops four items, a cleaner picks them up.
Writes data/demo/floor.mp4 and data/demo/reference.jpg (frame 0, empty floor). 960x540, 15 fps, 70 s."""
import math, sys
from pathlib import Path
import cv2
import numpy as np

W, H, FPS, SECS = 960, 540, 15, 70
OUT = Path(__file__).resolve().parent.parent / "data" / "demo"

# (x, y, kind, t_appear, t_removed)
ITEMS = [(340, 428, "bottle", 14.0, 51.6), (440, 478, "wrapper", 17.7, 49.0),
         (610, 438, "can", 22.0, 46.2), (750, 398, "paper", 26.1, 43.2)]
# keyframes (t, x, y, crouch); positions are the feet
DROPPER = [(10, -30, 420, 0), (13.2, 330, 420, 0), (14.4, 330, 420, 1), (14.9, 330, 420, 0), (16.2, 430, 470, 0),
           (17.4, 430, 470, 1), (18.0, 430, 470, 0), (20.5, 600, 430, 0), (21.7, 600, 430, 1), (22.3, 600, 430, 0),
           (24.6, 740, 390, 0), (25.8, 740, 390, 1), (26.4, 740, 390, 0), (31, 1010, 390, 0)]
CLEANER = [(40, 990, 450, 0), (42.2, 750, 400, 0), (43.6, 750, 400, 1), (44.2, 750, 400, 0), (45.3, 610, 440, 0),
           (46.7, 610, 440, 1), (47.2, 610, 440, 0), (48.2, 440, 480, 0), (49.6, 440, 480, 1), (50.1, 440, 480, 0),
           (50.9, 340, 430, 0), (52.3, 340, 430, 1), (52.8, 340, 430, 0), (57, -30, 430, 0)]
# the cleaner arrives 46 s in, after every item is old enough to have a ticket
CLEANER = [(t + 6, x, y, c) for t, x, y, c in CLEANER]
ITEMS = [(x, y, k, a, r + 6) for x, y, k, a, r in ITEMS]
PASSERS = [[(4, -30, 300, 0), (11, 990, 300, 0)], [(7, 990, 350, 0), (14, -30, 350, 0)],
           [(30, -30, 480, 0), (37, 990, 480, 0)], [(33, 990, 260, 0), (40, -30, 260, 0)]]
SHIRTS = [(150, 90, 60), (70, 120, 170), (90, 140, 90), (60, 70, 160), (160, 140, 80)]


def pos(keys, t):
    if t < keys[0][0] or t > keys[-1][0]:
        return None
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0
            return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3], math.hypot(b[1] - a[1], b[2] - a[2]) > 0


def background():
    rng = np.random.default_rng(7)
    img = np.full((H, W, 3), (176, 180, 178), np.uint8)
    img[:170] = (150, 160, 166)
    for x in range(40, W, 160):  # windows
        cv2.rectangle(img, (x, 40), (x + 110, 130), (224, 232, 238), -1)
        cv2.rectangle(img, (x, 40), (x + 110, 130), (120, 128, 132), 3)
    cv2.rectangle(img, (0, 165), (W, 178), (110, 118, 122), -1)
    for x in range(0, W, 80):
        cv2.line(img, (x, 178), (x, H), (168, 172, 170), 1)
    for y in range(178, H, 70):
        cv2.line(img, (0, y), (W, y), (168, 172, 170), 1)
    cv2.rectangle(img, (915, 410), (952, 500), (70, 76, 74), -1)  # a bin, part of the scene
    cv2.rectangle(img, (910, 402), (957, 416), (50, 54, 52), -1)
    tex = rng.integers(-4, 5, img.shape)
    return np.clip(img.astype(int) + tex, 0, 255).astype(np.uint8)


def item(img, x, y, kind):
    cv2.ellipse(img, (x + 3, y + 14), (16, 5), 0, 0, 360, (140, 144, 142), -1)
    if kind == "bottle":
        cv2.rectangle(img, (x - 7, y - 20), (x + 7, y + 14), (235, 200, 120), -1)
        cv2.rectangle(img, (x - 3, y - 27), (x + 3, y - 20), (250, 250, 250), -1)
    elif kind == "wrapper":
        cv2.fillPoly(img, [np.array([(x - 16, y - 6), (x + 14, y - 10), (x + 17, y + 8), (x - 12, y + 10)])], (60, 140, 235))
        cv2.line(img, (x - 6, y - 8), (x - 4, y + 9), (30, 90, 190), 2)
    elif kind == "can":
        cv2.rectangle(img, (x - 10, y - 16), (x + 10, y + 12), (205, 205, 210), -1)
        cv2.rectangle(img, (x - 10, y - 6), (x + 10, y + 2), (70, 70, 200), -1)
    else:
        cv2.fillPoly(img, [np.array([(x - 14, y - 2), (x - 6, y - 14), (x + 8, y - 12), (x + 15, y + 2), (x + 4, y + 12), (x - 9, y + 10)])], (246, 246, 242))


def person(img, x, y, crouch, walking, t, shirt):
    s = 0.6 + 0.6 * (y - 190) / 330
    h = 130 * s * (0.62 if crouch else 1)
    ph = t * 7 if walking else 0
    sh = img.copy()
    cv2.ellipse(sh, (int(x + 5), int(y + 3)), (int(0.2 * h), int(0.05 * h)), 0, 0, 360, (120, 124, 122), -1)
    cv2.addWeighted(sh, 0.5, img, 0.5, 0, img)
    hip, th = (int(x), int(y - 0.45 * h)), max(2, int(0.07 * h))
    for d in (1, -1):
        cv2.line(img, hip, (int(x + d * math.sin(ph) * 0.12 * h), int(y)), (60, 56, 52), th)
    top = int(y - 0.85 * h)
    cv2.rectangle(img, (int(x - 0.15 * h), top), (int(x + 0.15 * h), hip[1]), shirt, -1)
    for d in (1, -1):
        cv2.line(img, (int(x + d * 0.15 * h), top + 4), (int(x + d * 0.17 * h - d * math.sin(ph) * 0.08 * h), int(y - 0.5 * h)), shirt, th)
    cv2.circle(img, (int(x), int(top - 0.08 * h)), int(0.08 * h), (140, 170, 210), -1)
    cv2.ellipse(img, (int(x), int(top - 0.1 * h)), (int(0.08 * h), int(0.07 * h)), 0, 180, 360, (40, 36, 34), -1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bg, rng = background(), np.random.default_rng(3)
    vw = cv2.VideoWriter(str(OUT / "floor.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    actors = [(DROPPER, SHIRTS[0])] + [(CLEANER, SHIRTS[1])] + [(k, SHIRTS[2 + i % 3]) for i, k in enumerate(PASSERS)]
    for n in range(FPS * SECS):
        t = n / FPS
        f = bg.copy()
        for x, y, kind, ta, tr in ITEMS:
            if ta <= t < tr:
                item(f, x, y, kind)
        for keys, col in sorted(((k, c) for k, c in actors), key=lambda a: (pos(a[0], t) or (0, 0))[1]):
            p = pos(keys, t)
            if p:
                person(f, p[0], p[1], p[2], p[3] and not p[2], t, col)
        f = np.clip(f.astype(int) + rng.integers(-2, 3, f.shape), 0, 255).astype(np.uint8)
        if n == 0:
            cv2.imwrite(str(OUT / "reference.jpg"), f, [cv2.IMWRITE_JPEG_QUALITY, 95])
        vw.write(f)
    vw.release()
    print("wrote", OUT / "floor.mp4", "and", OUT / "reference.jpg")


if __name__ == "__main__":
    main()
