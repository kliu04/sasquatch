#!/usr/bin/env python3
from __future__ import annotations

from hold_detector.app import HoldDetectionApp
from hold_detector.cli import parse_config


def main() -> int:
    config = parse_config()
    app = HoldDetectionApp(config)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
