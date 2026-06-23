"""Compatibility wrapper: delegates to s3.generate_report.

This module is kept for backward compatibility. All AI style report logic
has been migrated to the s3 module. Import paths like
`from s2.generate_ai_style_report import generate_ai_style_report`
continue to work via this wrapper.
"""

from __future__ import annotations

from pathlib import Path

# Delegate to s3 module
from s3.generate_report import (
    generate_ai_style_report,
    main,
    render_ai_style_report,
)
from s3.validation import ValidationResult
from s3.style_rotation import StyleAnalysis

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDICATORS_DIR = PROJECT_ROOT / "data" / "indicators"
DEFAULT_MARKET_DAILY = PROJECT_ROOT / "data" / "processed" / "market_daily.csv"
DEFAULT_MACRO_MARKET_DAILY = PROJECT_ROOT / "data" / "processed" / "macro_market_daily.csv"
DEFAULT_S2_SCORES = PROJECT_ROOT / "s2" / "output" / "s2_scores.csv"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "s3" / "config.json"
DEFAULT_AI_CORE_VERSIONS = PROJECT_ROOT / "s3" / "versions.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "s3" / "output"
