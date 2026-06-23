"""S3 independent daily flow for AI style rotation report.

This module runs the S3 AI style rotation report independently,
without depending on S1 or S2 daily flows.
"""

from __future__ import annotations

from s3.generate_report import generate_ai_style_report


def main() -> None:
    path = generate_ai_style_report()
    print(f"S3 AI风格日报已更新: {path}")


if __name__ == "__main__":
    main()
