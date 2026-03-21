from __future__ import annotations

from detectron2.config import get_cfg
from detectron2.engine import DefaultPredictor

from hold_detector.config import DetectronConfig


class DetectronRunner:
    def __init__(self, config: DetectronConfig) -> None:
        self._predictor = self._build_predictor(config)

    def _build_predictor(self, config: DetectronConfig) -> DefaultPredictor:
        cfg = get_cfg()
        cfg.merge_from_file(str(config.config_path.resolve()))
        cfg.MODEL.WEIGHTS = str(config.weights_path.resolve())
        cfg.MODEL.DEVICE = config.device
        cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = config.score_threshold
        cfg.MODEL.RETINANET.SCORE_THRESH_TEST = config.score_threshold
        cfg.TEST.DETECTIONS_PER_IMAGE = config.max_detections
        cfg.freeze()
        return DefaultPredictor(cfg)

    def predict(self, image_bgr):
        return self._predictor(image_bgr)["instances"].to("cpu")
