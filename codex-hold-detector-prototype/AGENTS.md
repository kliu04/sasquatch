# AGENTS.md
## Project
Climbing hold detection pipeline for a hackathon. YOLO + SAM + LiDAR + Claude API.

## Setup
- Python 3.11+, pip install ultralytics
- Dataset: Climbuddy Kaggle (VIA JSON format, needs conversion to YOLO)

## Conventions
- All scripts go in project root
- Use ultralytics YOLOv8 library
- Train at imgsz=1280, not 640
- Merge all annotation classes into single "hold" class (class 0)

## Verification
- After conversion: spot-check 5 random label files against source images
- After training: mAP50 should be > 0.7
- After inference: visually inspect annotated output on test images