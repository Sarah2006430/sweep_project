"""Fine-tune a small YOLO model on a litter dataset. Run this on Google Colab (free T4 GPU), not on your laptop.

1. Colab: Runtime > Change runtime type > T4 GPU.
2. Open the Roboflow Universe dataset page (links in README), click Download Dataset, pick the
   "YOLOv8" format, choose "show download code" and run that snippet in a cell. It creates a folder with data.yaml.
3. !pip install ultralytics
4. !python train.py /content/<dataset-folder>/data.yaml
5. Download runs/litter/weights/best.pt, save it as weights/litter.pt, set "detector": "yolo" in backend/config.json.

Training prints precision, recall and mAP at the end. Put those numbers in your README.
"""
import sys
from ultralytics import YOLO

data = sys.argv[1]
model = YOLO("yolov8n.pt")
model.train(data=data, epochs=60, imgsz=640, batch=16, patience=15, project="runs", name="litter")
print(YOLO("runs/litter/weights/best.pt").val(data=data))
print("class names in this model:", YOLO("runs/litter/weights/best.pt").names)
print("Copy any class names that are not already in backend/config.json class_map / ignore_classes.")
