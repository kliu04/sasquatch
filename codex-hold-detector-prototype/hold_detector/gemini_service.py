from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path
from typing import Any

import numpy as np

from hold_detector.config import GeminiConfig
from hold_detector.constants import ALLOWED_HOLD_TYPES, GEMINI_SYSTEM_PROMPT, SINGLE_GEMINI_SCHEMA
from hold_detector.gemini_grid import GeminiGridBuilder
from hold_detector.models import DetectionRecord


def load_genai_sdk():
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "Gemini classification requires the `google-genai` package in .venv-d2."
        ) from exc
    return genai, types


class GeminiClassifier:
    def __init__(self, config: GeminiConfig) -> None:
        self.config = config

    def classify_image(
        self,
        image_name: str,
        image_bgr: np.ndarray,
        records: list[DetectionRecord],
        _masks: list[np.ndarray],
        output_dir: Path,
        api_key: str,
    ) -> list[DetectionRecord]:
        crop_dir = output_dir / "crops" / Path(image_name).stem if self.config.save_crops else None
        max_workers = max(1, min(self.config.concurrency, len(records)))
        max_passes = max(1, self.config.max_retries)
        print(
            f"{image_name}: starting Gemini classification for {len(records)} candidates "
            f"with concurrency={max_workers} across up to {max_passes} pass(es)",
            flush=True,
        )

        classified: list[DetectionRecord | None] = [None] * len(records)
        pending_indices = list(range(len(records)))
        completed = 0
        final_failures = 0
        next_progress = 25
        for attempt in range(1, max_passes + 1):
            if not pending_indices:
                break
            pass_failures = 0
            if attempt > 1:
                print(
                    f"{image_name}: retrying {len(pending_indices)} failed candidate(s) on pass {attempt}/{max_passes}",
                    flush=True,
                )
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(
                        self._classify_one,
                        index,
                        records[index],
                        image_bgr,
                        api_key,
                        crop_dir,
                        attempt,
                    ): index
                    for index in pending_indices
                }
                next_pending_indices: list[int] = []
                for future in concurrent.futures.as_completed(future_map):
                    result = future.result()
                    if result["status"] == "ok":
                        classification = result["classification"]
                        record = result["prepared_record"]
                        classified[result["index"]] = record.apply_classification(
                            hold_type=classification["type"],
                            color=classification.get("color"),
                            confidence=classification.get("confidence"),
                            attempts=result["attempts"],
                        )
                        completed += 1
                        if completed >= next_progress or completed == len(records):
                            print(
                                f"{image_name}: classified {completed}/{len(records)} "
                                f"(final_failures={final_failures})",
                                flush=True,
                            )
                            while next_progress <= completed:
                                next_progress += 25
                    else:
                        pass_failures += 1
                        next_pending_indices.append(result["index"])
                        classified[result["index"]] = result["prepared_record"].mark_failed(
                            result["error"],
                            result["attempts"],
                        )
            pending_indices = next_pending_indices
            if attempt == max_passes:
                final_failures = len(pending_indices)
            elif pass_failures:
                print(
                    f"{image_name}: pass {attempt}/{max_passes} left {pass_failures} failed candidate(s) for retry",
                    flush=True,
                )

        if completed < len(records):
            print(
                f"{image_name}: classified {completed}/{len(records)} "
                f"(final_failures={final_failures})",
                flush=True,
            )
        return [record for record in classified if record is not None]

    def _classify_one(
        self,
        index: int,
        record: DetectionRecord,
        image_bgr: np.ndarray,
        api_key: str,
        crop_dir: Path | None,
        attempt: int,
    ) -> dict[str, Any]:
        grid_builder = GeminiGridBuilder(1)
        prepared_record = record.copy()
        context_crop = grid_builder.build_crop(image_bgr, prepared_record, crop_dir)
        crop_bytes = grid_builder.encode_image(context_crop, ".jpg")

        client, types = self._client_and_types(api_key)
        config = types.GenerateContentConfig(
            system_instruction=GEMINI_SYSTEM_PROMPT,
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=SINGLE_GEMINI_SCHEMA,
        )
        contents = grid_builder.build_single_contents(
            crop_bytes,
            "image/jpeg",
            types,
        )

        try:
            response = client.models.generate_content(
                model=self.config.model,
                contents=contents,
                config=config,
            )
            payload = json.loads(response.text)
            return {
                "status": "ok",
                "attempts": attempt,
                "index": index,
                "prepared_record": prepared_record,
                "classification": self._validate_one(payload),
            }
        except Exception as exc:
            return {
                "status": "failed",
                "attempts": attempt,
                "index": index,
                "prepared_record": prepared_record,
                "error": str(exc),
            }

    def _client_and_types(self, api_key: str):
        genai, types = load_genai_sdk()
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=self.config.timeout_seconds * 1000),
        )
        return client, types

    def _validate_one(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Classification response is not a JSON object.")
        hold_type = payload.get("type")
        if hold_type not in ALLOWED_HOLD_TYPES:
            raise ValueError(f"Unexpected hold type: {hold_type}")
        return {
            "type": hold_type,
        }
