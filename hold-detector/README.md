# Climbing Hold Detector

This repo is now trimmed to the pretrained Detectron2 hold detector path only.
The runtime was refactored into a thin entry script plus a small `hold_detector/` package so the pipeline is easier to read.

## Files That Actually Run The Model

The runtime path is:

- [detectron_infer.py](/Users/randyzhu/Desktop/produhacks/codex-hold-detector-prototype/detectron_infer.py)
- `hold_detector/cli.py` for argument parsing only
- `hold_detector/app.py` for top-level orchestration
- `hold_detector/detectron_service.py`, `hold_detector/postprocess.py`, `hold_detector/gemini_service.py`, and `hold_detector/rendering.py` for the main pipeline stages
- [experiment_config.yml](/Users/randyzhu/Desktop/produhacks/codex-hold-detector-prototype/archive/model/experiment_config.yml)
- [model_final.pth](/Users/randyzhu/Desktop/produhacks/codex-hold-detector-prototype/archive/model/model_final.pth)
- `.venv-d2/` for the Python 3.11 runtime
- [demo-data](/Users/randyzhu/Desktop/produhacks/codex-hold-detector-prototype/demo-data) for sample inputs

Not required for inference:

- [test_results.json](/Users/randyzhu/Desktop/produhacks/codex-hold-detector-prototype/archive/model/test_results.json)
- [triplet_network_final.pt](/Users/randyzhu/Desktop/produhacks/codex-hold-detector-prototype/archive/model/triplet_network_final.pt)

## Runtime Setup

Create the runtime virtualenv:

```bash
PYENV_VERSION=3.11.8 python -m venv .venv-d2
.venv-d2/bin/pip install -r requirements.txt
.venv-d2/bin/pip install --no-build-isolation 'git+https://github.com/facebookresearch/detectron2.git'
```

Gemini classification in [detectron_infer.py](/Users/randyzhu/Desktop/produhacks/codex-hold-detector-prototype/detectron_infer.py) uses the official `google-genai` Python SDK and submits one request per candidate.

## Run Inference

Run Detectron-only inference on the demo images:

```bash
.venv-d2/bin/python detectron_infer.py
```

Run on specific images:

```bash
.venv-d2/bin/python detectron_infer.py demo-data/IMG_7868.jpeg demo-data/IMG_7871.jpeg
```

Current default input behavior: if no images are passed, the script uses every supported image in [demo-data](/Users/randyzhu/Desktop/produhacks/codex-hold-detector-prototype/demo-data).

Run Gemini classification on the demo images after the mild tape-removal pass:

```bash
MPLCONFIGDIR=$PWD/.mplconfig .venv-d2/bin/python detectron_infer.py \
  --tape-filter \
  --classify \
  --output-dir detectron-output-gemini
```

The script loads `.env` automatically and looks for `HOLD_CLASSIFICATION_KEY_GEMINI` by default.

Useful runtime flags:

- `--score-threshold`
- `--max-detections`
- `--tape-filter`
- `--no-dedupe`
- `--classify`
- `--concurrency`

## Output

Inference writes:

- annotated images
- `predictions.json`
- `postprocess_summary.json`
- `classified_predictions.json` when Gemini is enabled
- `overlays/all-candidates/` and `overlays/holds-only/` when Gemini is enabled
