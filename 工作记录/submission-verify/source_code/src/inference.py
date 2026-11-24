"""High-level local inference API used by CLI, evaluation and Gradio."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

from .model import load_whisper_pipeline
from .preprocessing import load_audio
from .text_normalization import normalize_text


@dataclass(frozen=True)
class TranscriptionResult:
    audio_path: str
    text: str
    normalized_text: str
    duration_seconds: float
    inference_seconds: float
    real_time_factor: float
    device: str

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)


class WhisperASR:
    def __init__(
        self,
        model_dir: str | Path,
        *,
        device: str = "auto",
        adapter_dir: str | Path | None = None,
        language: str = "zh",
        task: str = "transcribe",
        chunk_length_s: float = 30.0,
        max_new_tokens: int = 128,
    ) -> None:
        self.pipeline, self.device = load_whisper_pipeline(
            model_dir,
            device=device,
            adapter_dir=adapter_dir,
            chunk_length_s=chunk_length_s,
        )
        self.language = language
        self.task = task
        self.max_new_tokens = max_new_tokens

    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        audio = load_audio(audio_path)
        started = perf_counter()
        output = self.pipeline(
            {"array": audio.samples, "sampling_rate": audio.sample_rate},
            generate_kwargs={
                "language": self.language,
                "task": self.task,
                "max_new_tokens": self.max_new_tokens,
            },
        )
        elapsed = perf_counter() - started
        text = str(output.get("text", "")).strip()
        rtf = elapsed / audio.duration_seconds if audio.duration_seconds > 0 else 0.0
        return TranscriptionResult(
            audio_path=str(Path(audio_path).resolve()),
            text=text,
            normalized_text=normalize_text(text),
            duration_seconds=audio.duration_seconds,
            inference_seconds=elapsed,
            real_time_factor=rtf,
            device=self.device,
        )

