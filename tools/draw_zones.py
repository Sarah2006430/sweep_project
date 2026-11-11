"""Click polygon corners on the first frame of your footage; prints JSON for config.json.
Left click adds a point, Enter closes the polygon, Esc quits.
(This is a setup utility. The submission itself is the web dashboard.)"""
import json, sys
import cv2
import numpy as np

cap = cv2.VideoCapture(sys.argv[1])
ok, frame = cap.read()
assert ok, "could not read video"
pts, done = [], []


def click(ev, x, y, *_):
    if ev == cv2.EVENT_LBUTTONDOWN:
        pts.append([x, y])


cv2.namedWindow("zones")
cv2.setMouseCallback("zones", click)
while True:
    img = frame.copy()
    for poly in done + [pts]:
        if poly:
            cv2.polylines(img, [np.array(poly, "int32")], False, (79, 176, 224), 2)
    cv2.imshow("zones", img)
    k = cv2.waitKey(30) & 255
    if k == 13 and len(pts) > 2:
        done.append(pts[:])
        print(json.dumps(pts))
        pts.clear()
    if k == 27:
        break
