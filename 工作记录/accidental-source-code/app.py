#!/usr/bin/env python
"""Local Gradio prototype for Chinese continuous speech recognition."""

from __future__ import annotations

import argparse
from functools import lru_cache
from pathlib import Path

import gradio as gr

from src.inference import WhisperASR


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_DIR = PROJECT_ROOT / "models" / "asr_model"
IMPROVED_ADAPTER = PROJECT_ROOT / "checkpoints" / "improved" / "best"
SUBMISSION_ADAPTER = PROJECT_ROOT.parent / "model" / "improved_adapter"
CUSTOM_CSS = """
.gradio-container { max-width: 1280px !important; margin: 0 auto !important; padding: 24px 32px !important; }
#intro { margin: 0 !important; padding: 0 !important; }
"""


@lru_cache(maxsize=2)
def get_recognizer(model_choice: str) -> WhisperASR:
    if not MODEL_DIR.is_dir():
        raise FileNotFoundError(
            f"本地模型不存在：{MODEL_DIR}。请先运行 python scripts/download_model.py。"
        )
    adapter = None
    if model_choice == "Improved":
        adapter = IMPROVED_ADAPTER if IMPROVED_ADAPTER.is_dir() else SUBMISSION_ADAPTER
        if not adapter.is_dir():
            raise FileNotFoundError(
                f"改进模型 checkpoint 不存在：{IMPROVED_ADAPTER} 或 {SUBMISSION_ADAPTER}。"
                "请先完成微调，或选择 Baseline。"
            )
    return WhisperASR(MODEL_DIR, adapter_dir=adapter, device="auto")


def recognize(audio_path: str | None, model_choice: str):
    if not audio_path:
        return "", 0.0, 0.0, 0.0, "请先上传音频或使用麦克风录音。"
    try:
        result = get_recognizer(model_choice).transcribe(audio_path)
    except Exception as exc:
        return "", 0.0, 0.0, 0.0, f"识别失败：{exc}"
    return (
        result.text,
        round(result.duration_seconds, 3),
        round(result.inference_seconds, 3),
        round(result.real_time_factor, 4),
        f"模型：{model_choice}；设备：{result.device}；完全本地推理",
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="汉语连续语音识别系统") as demo:
        gr.Markdown(
            "# 汉语连续语音识别系统\n"
            "### Chinese Continuous Speech Recognition System\n\n"
            "上传 WAV/MP3/FLAC，或直接用麦克风录音。模型从本机 `models/` 加载，不调用远程 API。",
            elem_id="intro",
        )
        with gr.Row():
            audio = gr.Audio(
                sources=["upload", "microphone"],
                type="filepath",
                label="音频输入 / Audio Input",
            )
            with gr.Column():
                model_choice = gr.Dropdown(
                    choices=["Baseline", "Improved"],
                    value="Baseline",
                    label="模型 / Model",
                )
                recognize_button = gr.Button("开始识别 / Transcribe", variant="primary")
                clear_button = gr.ClearButton(value="清空 / Clear")
        transcript = gr.Textbox(label="识别结果 / Transcript", lines=4)
        with gr.Row():
            duration = gr.Number(label="音频时长（秒）", precision=3)
            elapsed = gr.Number(label="推理耗时（秒）", precision=3)
            rtf = gr.Number(label="Real-Time Factor", precision=4)
        status = gr.Textbox(label="系统状态", interactive=False)
        outputs = [transcript, duration, elapsed, rtf, status]
        recognize_button.click(recognize, inputs=[audio, model_choice], outputs=outputs)
        audio.stop_recording(recognize, inputs=[audio, model_choice], outputs=outputs)
        clear_button.add([audio, model_choice, *outputs])
        gr.Markdown(
            "**说明：** Baseline 为预训练 Whisper-small；Improved 为本课程数据上训练的本地 LoRA adapter。"
            "如果尚未完成微调，请选择 Baseline。"
        )
    return demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--inbrowser", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_app().launch(
        server_name=args.host,
        server_port=args.port,
        share=False,
        inbrowser=args.inbrowser,
        allowed_paths=[str(PROJECT_ROOT)],
        css=CUSTOM_CSS,
    )

