#!/usr/bin/env python
"""一键执行每日流程：更新数据 → 计算指标 → 生成日报"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def run_step(module: str, description: str) -> bool:
    """执行单个步骤"""
    print(f"\n{'='*50}")
    print(f"步骤: {description}")
    print('='*50)
    result = subprocess.run(
        [sys.executable, "-m", module],
        cwd=PROJECT_ROOT,
    )
    return result.returncode == 0


def main():
    steps = [
        ("wb.update_data", "更新数据"),
        ("wb.calculate_indicators", "计算指标"),
        ("wb.generate_report", "生成日报"),
    ]

    success = True
    for module, desc in steps:
        if not run_step(module, desc):
            print(f"❌ {desc}失败")
            success = False
            break
        print(f"✓ {desc}完成")

    if success:
        print(f"\n{'='*50}")
        print("✓ 全部完成，日报已更新")
        print('='*50)
    else:
        print("\n❌ 流程中断")
        sys.exit(1)


if __name__ == "__main__":
    main()
