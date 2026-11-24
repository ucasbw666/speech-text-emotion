#!/usr/bin/env python
"""Assemble a compact course-submission directory without duplicating raw audio/base weights."""

from __future__ import annotations

from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = PROJECT_ROOT / "submission"


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path, *, ignore=None) -> None:
    if source.exists():
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)


def main() -> None:
    SUBMISSION.mkdir(parents=True, exist_ok=True)
    source_code = SUBMISSION / "source_code"
    for directory in ("src", "scripts", "configs", "assets", "tests", "docs", "third_party"):
        copy_tree(
            PROJECT_ROOT / directory,
            source_code / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for filename in (
        "app.py",
        "README.md",
        "requirements.txt",
        "requirements-emotion.txt",
        "environment.yml",
        "MODEL_DOWNLOAD.md",
        "PROJECT_PLAN.md",
        "pytest.ini",
        ".gitignore",
    ):
        copy_file(PROJECT_ROOT / filename, source_code / filename)

    model_dir = SUBMISSION / "model"
    copy_tree(PROJECT_ROOT / "checkpoints" / "improved" / "best", model_dir / "improved_adapter")
    copy_tree(PROJECT_ROOT / "checkpoints" / "augmented" / "best", model_dir / "augmentation_ablation_adapter")
    copy_tree(PROJECT_ROOT / "models" / "emotion" / "production", model_dir / "emotion_production")
    (model_dir / "README.md").write_text(
        "# Model files\n\n"
        "`improved_adapter/` 是最终选用的 LoRA checkpoint（test CER 6.80%）。"
        "`augmentation_ablation_adapter/` 是增强消融（CER 8.19%）。两者均需配合 "
        "`openai/whisper-small` 基模型；运行 source_code/scripts/download_model.py 获取基模型。"
        "预训练基模型约 1 GB，为避免提交包重复膨胀未复制到此目录。\n\n"
        "`emotion_production/` 为 voice-main 的原始情绪双分支模型。情绪骨干约 1.81 GiB，"
        "请在 source_code 中运行 `python scripts/download_emotion_model.py` 下载和校验。"
        "统一 UI 自动查找本目录中的 ASR adapter 与情绪 production。来源和原许可见 "
        "source_code/third_party/voice-main/。\n",
        encoding="utf-8",
    )

    dataset_dir = SUBMISSION / "dataset"
    copy_file(PROJECT_ROOT / "data" / "README.md", dataset_dir / "README.md")
    copy_file(PROJECT_ROOT / "scripts" / "download_dataset.py", dataset_dir / "download_dataset.py")
    copy_tree(PROJECT_ROOT / "data" / "manifests", dataset_dir / "manifests")

    copy_tree(PROJECT_ROOT / "report", SUBMISSION / "experiment_report")
    copy_tree(PROJECT_ROOT / "results", SUBMISSION / "results")
    for filename in ("README.md", "requirements.txt", "requirements-emotion.txt", "environment.yml", "MODEL_DOWNLOAD.md"):
        copy_file(PROJECT_ROOT / filename, SUBMISSION / filename)
    checklist = PROJECT_ROOT / "FINAL_CHECKLIST.md"
    if checklist.is_file():
        copy_file(checklist, SUBMISSION / checklist.name)

    print(f"Submission assembled at: {SUBMISSION}")
    print("Raw audio and both large pretrained backbones were intentionally not duplicated.")


if __name__ == "__main__":
    main()

