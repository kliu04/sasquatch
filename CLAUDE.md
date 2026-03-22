# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sasquatch is a climbing wall hold detection and route generation system. It combines Detectron2 (instance segmentation), Open3D (3D point cloud processing), Google Gemini (hold classification), and FastAPI to detect holds from LiDAR scans and generate climbing routes of varying difficulty. An iOS app captures LiDAR scans and consumes the API.

## Setup

Python 3.11 required. Create the virtualenv and install dependencies:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install --no-build-isolation 'git+https://github.com/facebookresearch/detectron2.git'
```

## Commands

**CLI hold detection** (run from `hold-detector/`):
```bash
.venv/bin/python detectron_infer.py                    # all demo images
.venv/bin/python detectron_infer.py path/to/image.jpg  # specific images
.venv/bin/python detectron_infer.py --tape-filter --classify --output-dir detectron-output-gemini
```

Useful flags: `--score-threshold`, `--max-detections`, `--tape-filter`, `--no-dedupe`, `--classify`, `--concurrency`

**Unified API server** (run from project root):
```bash
PYTHONPATH=.:hold-detector .venv/bin/uvicorn database.server:app --host 0.0.0.0 --port 8000
```

**Run tests:**
```bash
PYTHONPATH=.:hold-detector .venv/bin/python tests/test_api.py
```

## Environment Variables

Stored in `.env` at project root (gitignored):

- `HOLD_CLASSIFICATION_KEY_GEMINI` — Google Gemini API key
- `DATABASE_URL` — PostgreSQL connection string (defaults to cloud instance at `34.11.229.123:5432/sasquatch`)
- `GCS_BUCKET` — Google Cloud Storage bucket name (default: `sasquatch-scans`)
- `GOOGLE_APPLICATION_CREDENTIALS` — path to GCS service account JSON key (relative paths resolved from project root)
- `OPEN3D_CPU_RENDERING=true` — required for headless/Docker environments

## Architecture

### Layered Architecture

```
API Layer (FastAPI routers)           <- HTTP, auth, validation
  database/routers/walls.py
  database/routers/climbs.py
  database/routers/users.py

Service Layer                         <- Business logic, background work
  database/scan_worker.py             <- Orchestrates SasquatchEngine
  database/storage.py                 <- GCS signed URLs, upload, download

SasquatchEngine (hold-detector/api/)  <- ML pipeline, purely functional
  prepare_scan() -> ScanState
  process_scan() -> list[Hold]        <- Hold detection
  build_routes(holds) -> routes       <- Path generation
  draw_*_overlay() -> image           <- Visualization

Database Layer                        <- SQLAlchemy models, session mgmt
  database/schema.py
  database/db.py
```

**Key principle:** API routers never import from `hold_detector` directly. They go through `scan_worker.py`. The SasquatchEngine doesn't know about the database, GCS, or HTTP.

### Two-Phase Scan Pipeline (`hold-detector/api/`)

1. **prepare_scan** (main thread): Load PLY point cloud with Open3D -> auto-detect wall orientation via PCA -> render to 2D image
2. **process_scan** (background): Run Detectron2 detection -> post-process (deduplication, tape filtering) -> optional Gemini classification -> back-project 2D detections to 3D world coordinates -> compute hold depth

The `SasquatchEngine` class in `api/main.py` is the library entry point that loads the model once and exposes `create_scan(ply_path, png_path)`.

### Route Generation (`api/route_service.py`)

Builds a directed graph of holds with difficulty scores, then uses DFS with budget constraints. Returns top-k routes for a given difficulty (easy/medium/hard) and style (static/dynamic).

### Unified API (`database/`)

- `server.py` — FastAPI app entrypoint, lifespan, CORS, router mounting
- `routers/walls.py` — wall CRUD, GCS signed upload URLs, process trigger, long polling, holds endpoint
- `routers/climbs.py` — route generation, climb CRUD, save/favourite/sent, filtered listing
- `routers/users.py` — user profile (wingspan, username)
- `schema.py` — SQLAlchemy models: User, Wall (with WallStatus enum), Climb
- `auth.py` — Google OAuth2 token verification, auto-creates users on first sign-in
- `storage.py` — GCS client (signed URLs, upload, download, delete)
- `scan_worker.py` — background scan processing, in-memory scan state cache, long-poll events

### Database Schema

**User:** id, google_id, username, wingspan
**Wall:** id, user_id, name, status (pending_upload/processing/ready/error), error_message, hold_count, holds_json, wall_img_url, wall_ply_url, holds_image_url, created_at
**Climb:** id, wall_id, difficulty, classification, route_hold_ids, is_saved, is_favourite, date_sent, climb_img_url, created_at

### Hold Detection Package (`hold-detector/hold_detector/`)

- `app.py` — `HoldDetectionApp` orchestrates the full pipeline
- `detectron_service.py` — Detectron2 inference wrapper
- `postprocess.py` — mask deduplication and tape filtering
- `gemini_service.py` — Gemini-based false positive classification
- `config.py` — typed dataclasses for all configuration

### iOS LiDAR Capture (`lidar/`)

Swift/Xcode project for capturing LiDAR point clouds on iOS devices.

## API Reference

See `API.md` for the complete API specification including auth flow, all endpoints, request/response shapes, and iOS integration guide.

Key flow: `POST /walls` (get signed URLs) -> upload to GCS -> `POST /walls/{id}/process` -> long-poll `GET /walls/{id}?poll=true` -> `POST /walls/{id}/climbs` -> `PATCH` to save/favourite.

## Conventions

- All hold detection classes are merged into a single "hold" class (class 0)
- Model training uses imgsz=1280
- Model weights live in `hold-detector/archive/model/` (`model_final.pth`, `experiment_config.yml`)
- Open3D's offscreen visualizer must run on the main thread; ML inference runs in background threads
- All endpoints return JSON; images are GCS URLs (never raw bytes)
- `GET /walls/{id}/climbs` returns saved climbs only; `POST` returns all generated (unsaved)
- `is_favourite=true` auto-sets `is_saved=true`; `is_saved=false` clears `is_favourite`
- Service account JSON keys are gitignored (`gen-lang-client-*.json`)
