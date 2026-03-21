from __future__ import annotations

import argparse
from pathlib import Path

from hold_detector.config import (
    AppConfig,
    DedupeConfig,
    DetectronConfig,
    GeminiConfig,
    OutputConfig,
    TapeFilterConfig,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run archived Detectron2 hold inference and optional Gemini classification."
    )
    parser.add_argument("images", nargs="*", help="Image paths. Defaults to demo-data/*.jpg|png.")

    parser.add_argument("--config", type=Path, default=Path("archive/model/experiment_config.yml"))
    parser.add_argument("--weights", type=Path, default=Path("archive/model/model_final.pth"))
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--score-threshold", "--threshold", dest="score_threshold", type=float, default=0.5)
    parser.add_argument("--max-detections", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, default=Path("detectron-output"))
    parser.add_argument("--save-raw-detectron", action="store_true")

    parser.add_argument("--tape-filter", "--filter-tape", dest="tape_filter", action="store_true")
    parser.add_argument("--tape-uniformity-std", type=float, default=18.0)
    parser.add_argument("--tape-min-fill", type=float, default=0.58)
    parser.add_argument("--tape-min-aspect", type=float, default=1.0)
    parser.add_argument("--tape-max-vertices", type=int, default=4)
    parser.add_argument("--tape-min-minrect-fill", type=float, default=0.85)

    parser.add_argument("--dedupe", dest="dedupe", action="store_true", default=True)
    parser.add_argument("--no-dedupe", dest="dedupe", action="store_false")
    parser.add_argument("--dedupe-mask-overlap", type=float, default=0.8)
    parser.add_argument("--dedupe-box-overlap", type=float, default=0.9)

    parser.add_argument("--classify", "--classify-gemini", dest="classify", action="store_true")
    parser.add_argument("--gemini-model", default="gemini-3-flash-preview")
    parser.add_argument("--gemini-api-key", default=None)
    parser.add_argument("--gemini-api-key-env", default="HOLD_CLASSIFICATION_KEY_GEMINI")
    parser.add_argument("--concurrency", "--gemini-concurrency", dest="concurrency", type=int, default=100)
    parser.add_argument("--max-retries", "--gemini-max-retries", dest="max_retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", "--gemini-timeout-seconds", dest="timeout_seconds", type=int, default=60)
    parser.add_argument("--save-crops", action="store_true")
    return parser


def parse_config(argv: list[str] | None = None) -> AppConfig:
    args = build_parser().parse_args(argv)
    return AppConfig(
        images=args.images,
        detectron=DetectronConfig(
            config_path=args.config,
            weights_path=args.weights,
            device=args.device,
            score_threshold=args.score_threshold,
            max_detections=args.max_detections,
        ),
        tape_filter=TapeFilterConfig(
            enabled=args.tape_filter,
            uniformity_std=args.tape_uniformity_std,
            min_fill=args.tape_min_fill,
            min_aspect=args.tape_min_aspect,
            max_vertices=args.tape_max_vertices,
            min_minrect_fill=args.tape_min_minrect_fill,
        ),
        dedupe=DedupeConfig(
            enabled=args.dedupe,
            mask_overlap_threshold=args.dedupe_mask_overlap,
            box_overlap_threshold=args.dedupe_box_overlap,
        ),
        gemini=GeminiConfig(
            enabled=args.classify,
            model=args.gemini_model,
            api_key=args.gemini_api_key,
            api_key_env=args.gemini_api_key_env,
            concurrency=args.concurrency,
            max_retries=args.max_retries,
            timeout_seconds=args.timeout_seconds,
            save_crops=args.save_crops,
        ),
        output=OutputConfig(
            output_dir=args.output_dir,
            save_raw_detectron=args.save_raw_detectron,
        ),
    )
