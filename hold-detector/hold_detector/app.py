from __future__ import annotations

import numpy as np
from pathlib import Path

from hold_detector.config import AppConfig
from hold_detector.detectron_service import DetectronRunner
from hold_detector.gemini_service import GeminiClassifier
from hold_detector.io_utils import collect_images, ensure_dir, read_image, resolve_api_key, write_json
from hold_detector.models import DetectionRecord
from hold_detector.postprocess import PostProcessor
from hold_detector.rendering import OverlayRenderer


class HoldDetectionApp:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.detectron = DetectronRunner(config.detectron)
        self.postprocess = PostProcessor(config.tape_filter, config.dedupe)
        self.renderer = OverlayRenderer()
        self.gemini = GeminiClassifier(config.gemini) if config.gemini.enabled else None

    def detect(self, image_name: str, image_bgr: np.ndarray) -> tuple[list[DetectionRecord], list[np.ndarray]]:
        """Run the full detection pipeline on a single image.

        Returns (records, masks) where masks are boolean numpy arrays per hold.
        """
        import time

        t0 = time.perf_counter()
        print(f"[detect] {image_name}: starting Detectron2 inference", flush=True)
        instances = self.detectron.predict(image_bgr)
        t1 = time.perf_counter()
        print(f"[detect] {image_name}: Detectron2 done in {t1 - t0:.1f}s", flush=True)

        processed = self.postprocess.process(instances, image_bgr)
        t2 = time.perf_counter()
        print(f"[detect] {image_name}: postprocess done in {t2 - t1:.1f}s — {len(processed.records)} candidates", flush=True)

        records = processed.records
        masks = processed.masks

        if self.gemini:
            api_key = resolve_api_key(self.config.gemini)
            if api_key:
                print(f"[detect] {image_name}: starting Gemini filter for {len(records)} candidates", flush=True)
                output_dir = ensure_dir(self.config.output.output_dir.resolve())
                records, masks = self.gemini.filter_tape(
                    image_name,
                    image_bgr,
                    records,
                    masks,
                    output_dir,
                    api_key,
                )
                t3 = time.perf_counter()
                print(f"[detect] {image_name}: Gemini filter done in {t3 - t2:.1f}s — {len(records)} holds kept", flush=True)
            else:
                print(f"[detect] {image_name}: Gemini enabled but no API key found, skipping", flush=True)

        total = time.perf_counter() - t0
        print(f"[detect] {image_name}: total detect pipeline {total:.1f}s", flush=True)
        return records, masks

    def run(self) -> int:
        image_paths = collect_images(self.config.images)
        api_key = resolve_api_key(self.config.gemini) if self.config.gemini.enabled else None
        if self.config.gemini.enabled and not api_key:
            raise RuntimeError(
                "Gemini classification was requested, but no API key was found. "
                f"Set {self.config.gemini.api_key_env} in .env or pass --gemini-api-key."
            )

        output_dir = ensure_dir(self.config.output.output_dir.resolve())
        raw_summary: dict[str, list[dict[str, object]]] = {}
        classified_summary: dict[str, list[dict[str, object]]] = {}
        postprocess_summary: dict[str, dict[str, object]] = {}

        for image_path in image_paths:
            print(f"{image_path.name}: running Detectron inference", flush=True)
            image = read_image(image_path)
            instances = self.detectron.predict(image)
            processed = self.postprocess.process(instances, image)

            if self.config.dedupe.enabled:
                print(
                    f"{image_path.name}: {processed.deduped_count} candidates after dedupe "
                    f"(removed {len(processed.removed_duplicates)})",
                    flush=True,
                )
            print(
                f"{image_path.name}: {len(processed.records)} candidates after tape filter "
                f"(removed {len(processed.removed_tape)})",
                flush=True,
            )

            raw_summary[image_path.name] = [record.to_dict() for record in processed.records]
            postprocess_summary[image_path.name] = self.postprocess.build_summary(processed)

            if self.config.output.save_raw_detectron:
                self.renderer.save_raw_detectron(
                    image,
                    processed.instances,
                    output_dir / f"{image_path.stem}_annotated{image_path.suffix}",
                )

            ids_dir = ensure_dir(output_dir / "overlays" / "instance-ids")
            self.renderer.save_instance_ids(
                image,
                processed.records,
                processed.masks,
                ids_dir / image_path.name,
            )

            if self.gemini and api_key:
                filtered_records, filtered_masks = self.gemini.filter_tape(
                    image_path.name,
                    image,
                    processed.records,
                    processed.masks,
                    output_dir,
                    api_key,
                )
                classified_summary[image_path.name] = [record.to_dict() for record in filtered_records]

                filtered_dir = ensure_dir(output_dir / "overlays" / "gemini-filtered")
                self.renderer.save_instance_ids(image, filtered_records, filtered_masks, filtered_dir / image_path.name)

        predictions_path = output_dir / "predictions.json"
        write_json(predictions_path, raw_summary)
        write_json(output_dir / "postprocess_summary.json", postprocess_summary)

        if self.gemini:
            filtered_path = output_dir / "filtered_predictions.json"
            write_json(filtered_path, classified_summary)
            for image_name, records in classified_summary.items():
                print(f"{image_name}: {len(records)} holds after tape removal")
            print(f"\nSaved raw predictions to {predictions_path}")
            print(f"Saved filtered predictions to {filtered_path}")
            print(f"Saved filtered overlays to {output_dir / 'overlays'}")
        else:
            for image_name, records in raw_summary.items():
                print(f"{image_name}: {len(records)} candidates after tape filter")
            print(f"\nSaved predictions to {predictions_path}")

        if self.config.output.save_raw_detectron:
            print(f"Saved raw Detectron annotations to {output_dir}")
        return 0
