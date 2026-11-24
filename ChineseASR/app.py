#!/usr/bin/env python
"""One local workbench for Chinese speech-to-text and vocal emotion analysis."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from time import perf_counter

import gradio as gr

from src.inference import WhisperASR
from src.emotion import EMOTION_LABELS, SpeechEmotionRecognizer


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_DIR = PROJECT_ROOT / "models" / "asr_model"
IMPROVED_ADAPTER = PROJECT_ROOT / "checkpoints" / "improved" / "best"
SUBMISSION_ADAPTER = PROJECT_ROOT.parent / "model" / "improved_adapter"
CUSTOM_CSS = """
.gradio-container { max-width: 1320px !important; margin: 0 auto !important; padding: 24px 32px !important; }
#intro { margin: 0 !important; padding: 0 !important; }
#transcript textarea { font-size: 18px; line-height: 1.8; }
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


@lru_cache(maxsize=1)
def get_emotion_recognizer() -> SpeechEmotionRecognizer:
    return SpeechEmotionRecognizer()


def analyze(audio_path: str | None, model_choice: str, mode: str = "文字 + 情绪"):
    """Run independent models on one input and stream each completed result."""
    started = perf_counter()
    text, emotion, errors = None, None, {}
    asr_seconds, emotion_seconds = 0.0, 0.0

    def render(status):
        probabilities = {EMOTION_LABELS.get(k, k): v for k, v in emotion["all_probabilities"].items()} if emotion else {}
        timeline = [[s["start"], s["end"], EMOTION_LABELS.get(s["predicted_emotion"], s["predicted_emotion"]),
                     round(100 * s["confidence"], 2)] for s in emotion["segments"]] if emotion else []
        duration = text.duration_seconds if text else emotion["audio"]["duration"] if emotion else 0.0
        details = {"mode": mode, "asr_model": model_choice,
                   "transcription": text.to_dict() if text else None, "emotion": emotion, "errors": errors}
        return (
            text.text if text else "", EMOTION_LABELS.get(emotion["predicted_emotion"], emotion["predicted_emotion"]) if emotion else "",
            round(100 * emotion["confidence"], 2) if emotion else None,
            probabilities, timeline, round(duration, 3), round(asr_seconds, 3), round(emotion_seconds, 3),
            round(perf_counter() - started, 3), round(text.real_time_factor, 4) if text else 0.0, status, details,
        )

    if not audio_path:
        yield render("请先上传音频或使用麦克风录音。")
        return
    jobs = {}
    if mode in ("文字 + 情绪", "仅文字"):
        jobs["文字识别"] = lambda: get_recognizer(model_choice).transcribe(audio_path)
    if mode in ("文字 + 情绪", "仅情绪"):
        jobs["情绪识别"] = lambda: get_emotion_recognizer().predict(audio_path)
    if not jobs:
        errors["mode"] = "未知分析任务"
        yield render("请选择有效的分析任务。")
        return
    yield render("正在分析。首次使用需加载本地模型，请稍候…")

    def timed(call):
        task_started = perf_counter()
        return call(), perf_counter() - task_started

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {pool.submit(timed, call): name for name, call in jobs.items()}
        done = []
        for future in as_completed(futures):
            name = futures[future]
            try:
                result, seconds = future.result()
                if name == "文字识别":
                    text, asr_seconds = result, seconds
                else:
                    emotion, emotion_seconds = result, seconds
                done.append(name)
            except Exception as exc:
                errors[name] = str(exc)
            pending = len(jobs) - len(done) - len(errors)
            status = "；".join([*(f"{name}完成" for name in done), *(f"{name}失败：{error}" for name, error in errors.items())])
            if pending:
                status += "；另一项仍在处理中…"
            else:
                devices = {text.device if text else "", emotion.get("device", "") if emotion else ""} - {""}
                status += f"；设备：{' / '.join(sorted(devices)) or '未加载'}；完全本地推理"
                if emotion:
                    status += "；" + emotion["interpretation"]
                    warnings = emotion.get("audio", {}).get("warnings", [])
                    if warnings:
                        status += "；" + "；".join(warnings)
            yield render(status)


def build_app() -> gr.Blocks:
    with gr.Blocks(title="语音文字与情绪联合识别") as demo:
        gr.Markdown(
            "# 语音文字与情绪联合识别\n"
            "上传一次，既看说了什么，也看声音中的情绪。支持文件上传与麦克风录音，模型在本机运行。\n\n"
            "建议使用 3–10 秒的清晰普通话；情绪分析支持 0.5–60 秒音频。",
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
                    value="Improved",
                    label="文字识别模型",
                )
                mode = gr.Radio(choices=["文字 + 情绪", "仅文字", "仅情绪"], value="文字 + 情绪", label="分析任务")
                recognize_button = gr.Button("开始联合分析", variant="primary")
                clear_button = gr.ClearButton(value="清空 / Clear")
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 文字识别")
                transcript = gr.Textbox(label="识别文本", lines=8, interactive=False, elem_id="transcript")
            with gr.Column():
                gr.Markdown("### 声音情绪")
                with gr.Row():
                    emotion = gr.Textbox(label="主要情绪", interactive=False)
                    confidence = gr.Number(label="模型置信度（%）", precision=2, interactive=False)
                probabilities = gr.Label(label="六类情绪概率", num_top_classes=6)
        with gr.Row():
            duration = gr.Number(label="音频时长（秒）", precision=3, interactive=False)
            elapsed = gr.Number(label="文字任务耗时（秒）", precision=3, interactive=False)
            emotion_elapsed = gr.Number(label="情绪任务耗时（秒）", precision=3, interactive=False)
            total_elapsed = gr.Number(label="总等待时间（秒）", precision=3, interactive=False)
            rtf = gr.Number(label="文字推理 RTF", precision=4, interactive=False)
        status = gr.Textbox(label="系统状态", interactive=False)
        with gr.Accordion("分段情绪与详细结果", open=False):
            segments = gr.Dataframe(headers=["开始（秒）", "结束（秒）", "情绪", "置信度（%）"],
                                    datatype=["number", "number", "str", "number"], interactive=False)
            details = gr.JSON(label="联合分析结果")
        outputs = [transcript, emotion, confidence, probabilities, segments, duration, elapsed,
                   emotion_elapsed, total_elapsed, rtf, status, details]
        event_options = dict(fn=analyze, inputs=[audio, model_choice, mode], outputs=outputs,
                             concurrency_limit=1, concurrency_id="local_models")
        recognize_button.click(**event_options, api_name="analyze")
        audio.stop_recording(**event_options, api_name="recording_analysis", api_visibility="private")
        clear_button.add([audio, *outputs])
        sample_dir = PROJECT_ROOT / "assets" / "emotion_samples"
        samples = [[str(path)] for path in sorted(sample_dir.glob("*.wav"))]
        if samples:
            gr.Examples(examples=samples, inputs=audio, label="情绪示例音频（voice-main 公开样例）")
        gr.Markdown(
            "Baseline / Improved 使用 Whisper-small / 中文 LoRA；情绪识别使用 voice-main 的 emotion2vec 双分支模型。"
            "两项任务共用本次音频，独立计算；任一项失败时仍保留另一项结果。\n\n"
            "情绪概率描述声音表达，不是文字情感分析。首次加载时间包含在任务耗时中，后续请求复用模型。"
        )
        # Preserve the original five-field API for existing scripts and clients.
        legacy_outputs = [gr.Textbox(visible=False), gr.Number(visible=False), gr.Number(visible=False),
                          gr.Number(visible=False), gr.Textbox(visible=False)]
        gr.Button(visible=False).click(recognize, inputs=[audio, model_choice], outputs=legacy_outputs,
                                       api_name="recognize", concurrency_limit=1, concurrency_id="local_models")
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

