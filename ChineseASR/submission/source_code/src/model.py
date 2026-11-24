"""Whisper model loading with explicit offline/local behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_device(requested: str = "auto") -> tuple[str, int, Any]:
    import torch

    requested = requested.lower()
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested, but torch.cuda.is_available() is False.")
    if requested not in {"cpu", "cuda"}:
        raise ValueError("device must be one of: auto, cpu, cuda")
    if requested == "cuda":
        return requested, 0, torch.float16
    return requested, -1, torch.float32


def load_whisper_pipeline(
    model_dir: str | Path,
    *,
    device: str = "auto",
    adapter_dir: str | Path | None = None,
    chunk_length_s: float = 30.0,
):
    """Load a local Whisper model as an ASR pipeline without network access."""

    from transformers import (
        AutoModelForSpeechSeq2Seq,
        AutoProcessor,
        pipeline,
    )

    local_path = Path(model_dir).expanduser().resolve()
    if not local_path.is_dir():
        raise FileNotFoundError(
            f"Local model not found: {local_path}. Run scripts/download_model.py first."
        )
    device_name, pipeline_device, dtype = resolve_device(device)
    processor = AutoProcessor.from_pretrained(local_path, local_files_only=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        local_path,
        local_files_only=True,
        dtype=dtype,
        low_cpu_mem_usage=True,
    )
    if adapter_dir:
        try:
            from peft import PeftModel
        except ImportError as exc:
            raise RuntimeError("PEFT is required to load an improved-model adapter.") from exc
        adapter_path = Path(adapter_dir).expanduser().resolve()
        if not adapter_path.is_dir():
            raise FileNotFoundError(f"Adapter checkpoint not found: {adapter_path}")
        model = PeftModel.from_pretrained(model, adapter_path, is_trainable=False)

    asr_pipeline = pipeline(
        task="automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        device=pipeline_device,
        dtype=dtype,
        chunk_length_s=float(chunk_length_s),
        ignore_warning=True,
    )
    return asr_pipeline, device_name

