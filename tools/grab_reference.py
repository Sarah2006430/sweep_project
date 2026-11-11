"""Save one frame as the clean reference: python tools/grab_reference.py data/demo/floor.mp4 [seconds]
Pick a moment with an empty floor and no people. The reference is what the diff detector compares against."""
import sys
import cv2

cap = cv2.VideoCapture(sys.argv[1])
cap.set(cv2.CAP_PROP_POS_MSEC, float(sys.argv[2]) * 1000 if len(sys.argv) > 2 else 0)
ok, f = cap.read()
assert ok, "could not read video"
cv2.imwrite("data/demo/reference.jpg", f)
print("saved data/demo/reference.jpg", f.shape)
