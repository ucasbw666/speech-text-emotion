#!/usr/bin/env python
"""Memory-conscious Whisper LoRA fine-tuning for an 8 GB GPU."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import csv
import json
import math
from pathlib import Path
import random
import shutil
import sys
from time import perf_counter

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.augmentation import AugmentationConfig, apply_augmentation  # noqa: E402
from src.dataset import ManifestItem, read_manifest  # noqa: E402
from src.preprocessing import load_audio  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train_manifest", type=Path, required=True)
    parser.add_argument("--dev_manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs" / "improved.yaml")
    parser.add_argument("--model_dir", type=Path, default=PROJECT_ROOT / "models" / "asr_model")
    parser.add_argument("--output_dir", type=Path, default=PROJECT_ROOT / "checkpoints" / "improved")
    parser.add_argument("--batch_size", type=int)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--learning_rate", type=float)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--num_workers", type=int, default=0)
    parser.add_argument("--smoke_test", action="store_true")
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    import torch

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class SpeechDataset:
    def __init__(
        self,
        items: list[ManifestItem],
        manifest_path: Path,
        processor,
        *,
        augment: bool,
        augmentation_config: AugmentationConfig,
        seed: int,
    ) -> None:
        self.items = items
        self.manifest_path = manifest_path
        self.processor = processor
        self.augment = augment
        self.augmentation_config = augmentation_config
        self.seed = seed

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> dict[str, object]:
        item = self.items[index]
        audio = load_audio(item.resolved_audio(self.manifest_path))
        samples = audio.samples
        if self.augment:
            samples = apply_augmentation(samples, self.augmentation_config, np.random.default_rng(self.seed + index))
        input_features = self.processor.feature_extractor(
            samples,
            sampling_rate=audio.sample_rate,
            return_tensors="pt",
        ).input_features[0]
        labels = self.processor.tokenizer(item.text).input_ids
        return {"input_features": input_features, "labels": labels}


class WhisperCollator:
    def __init__(self, processor) -> None:
        self.processor = processor

    def __call__(self, features: list[dict[str, object]]) -> dict[str, object]:
        import torch

        inputs = [{"input_features": feature["input_features"]} for feature in features]
        batch = self.processor.feature_extractor.pad(inputs, return_tensors="pt")
        label_features = [{"input_ids": feature["labels"]} for feature in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")
        labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
        decoder_start = self.processor.tokenizer.bos_token_id
        if labels.shape[1] and decoder_start is not None and (labels[:, 0] == decoder_start).all():
            labels = labels[:, 1:]
        batch["labels"] = labels
        return batch


def evaluate_loss(model, loader, device, amp_enabled: bool) -> float:
    import torch

    model.eval()
    losses: list[float] = []
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            context = torch.autocast(device_type="cuda", dtype=torch.float16) if amp_enabled else nullcontext()
            with context:
                loss = model(**batch).loss
            losses.append(float(loss.detach().cpu()))
    model.train()
    return float(np.mean(losses)) if losses else math.nan


def main() -> None:
    args = parse_args()
    import torch
    import yaml
    from peft import LoraConfig, get_peft_model
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, get_linear_schedule_with_warmup

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    training = config.get("training", {})
    augmentation = config.get("augmentation", {})
    seed = int(config.get("project", {}).get("seed", 42))
    seed_everything(seed)
    epochs = 1 if args.smoke_test else int(args.epochs or training.get("epochs", 3))
    batch_size = int(args.batch_size or training.get("batch_size", 1))
    learning_rate = float(args.learning_rate or training.get("learning_rate", 1e-4))
    accumulation = 1 if args.smoke_test else int(training.get("gradient_accumulation_steps", 8))

    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA requested but not available")
    amp_enabled = device.type == "cuda" and bool(training.get("fp16", True))

    train_items = read_manifest(args.train_manifest)
    dev_items = read_manifest(args.dev_manifest)
    if args.smoke_test:
        train_items = train_items[: min(2, len(train_items))]
        dev_items = dev_items[: min(2, len(dev_items))]
    model_dir = args.model_dir.expanduser().resolve()
    if not model_dir.is_dir():
        raise SystemExit(f"Local model missing: {model_dir}. Run scripts/download_model.py first.")

    processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_dir,
        local_files_only=True,
        dtype=torch.float16 if amp_enabled else torch.float32,
        low_cpu_mem_usage=True,
    )
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    model.config.apply_spec_augment = bool(augmentation.get("enabled", False))
    if model.config.apply_spec_augment:
        model.config.mask_time_prob = 0.05
        model.config.mask_feature_prob = 0.05
    if training.get("gradient_checkpointing", True):
        model.enable_input_require_grads()
        model.gradient_checkpointing_enable()
        model.config.use_cache = False
    lora = LoraConfig(
        r=int(training.get("lora_r", 16)),
        lora_alpha=int(training.get("lora_alpha", 32)),
        lora_dropout=float(training.get("lora_dropout", 0.05)),
        target_modules=["q_proj", "v_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora).to(device)
    model.print_trainable_parameters()

    aug_config = AugmentationConfig(**{
        key: value for key, value in augmentation.items() if key in AugmentationConfig.__dataclass_fields__
    })
    use_augmentation = bool(augmentation.get("enabled", False))
    train_dataset = SpeechDataset(
        train_items,
        args.train_manifest,
        processor,
        augment=use_augmentation,
        augmentation_config=aug_config,
        seed=seed,
    )
    dev_dataset = SpeechDataset(
        dev_items,
        args.dev_manifest,
        processor,
        augment=False,
        augmentation_config=aug_config,
        seed=seed,
    )
    collator = WhisperCollator(processor)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collator,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
    )
    dev_loader = DataLoader(dev_dataset, batch_size=batch_size, collate_fn=collator, num_workers=0)

    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    update_steps = max(1, math.ceil(len(train_loader) / accumulation) * epochs)
    warmup_steps = round(update_steps * float(training.get("warmup_ratio", 0.1)))
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, update_steps)
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, object]] = []
    best_loss = math.inf
    global_step = 0
    optimizer.zero_grad(set_to_none=True)
    started = perf_counter()

    for epoch in range(1, epochs + 1):
        model.train()
        running_losses: list[float] = []
        for step, batch in enumerate(train_loader, start=1):
            batch = {key: value.to(device) for key, value in batch.items()}
            context = torch.autocast(device_type="cuda", dtype=torch.float16) if amp_enabled else nullcontext()
            with context:
                loss = model(**batch).loss / accumulation
            scaler.scale(loss).backward()
            running_losses.append(float(loss.detach().cpu()) * accumulation)
            should_update = step % accumulation == 0 or step == len(train_loader)
            if should_update:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
                scheduler.step()
                global_step += 1

        train_loss = float(np.mean(running_losses))
        val_loss = evaluate_loss(model, dev_loader, device, amp_enabled)
        row = {
            "epoch": epoch,
            "global_step": global_step,
            "train_loss": train_loss,
            "validation_loss": val_loss,
            "learning_rate": scheduler.get_last_lr()[0],
            "elapsed_seconds": perf_counter() - started,
        }
        history.append(row)
        print(json.dumps(row, ensure_ascii=False))
        epoch_dir = output_dir / f"epoch-{epoch}"
        model.save_pretrained(epoch_dir)
        processor.save_pretrained(epoch_dir)
        if val_loss < best_loss:
            best_loss = val_loss
            best_dir = output_dir / "best"
            if best_dir.exists():
                shutil.rmtree(best_dir)
            model.save_pretrained(best_dir)
            processor.save_pretrained(best_dir)

    with (output_dir / "training_history.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    run_metadata = {
        "config": config,
        "arguments": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "device": str(device),
        "torch_version": torch.__version__,
        "train_samples": len(train_items),
        "dev_samples": len(dev_items),
        "best_validation_loss": best_loss,
        "total_seconds": perf_counter() - started,
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(run_metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Best adapter: {output_dir / 'best'}")


if __name__ == "__main__":
    main()

