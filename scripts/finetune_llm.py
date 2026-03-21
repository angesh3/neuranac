#!/usr/bin/env python3
"""
LoRA Fine-Tuning Script for NeuraNAC NAC LLM.

Fine-tunes Llama 3.1 8B with LoRA adapters using training data collected
by collect_training_data.py. Produces a LoRA adapter that can be loaded
into Ollama via a Modelfile.

Requirements (GPU host only — not needed on NeuraNAC servers):
  pip install unsloth datasets trl transformers torch

Usage:
  # Generate training data first
  python3 scripts/collect_training_data.py --output /data/training/finetune_pairs.jsonl

  # Run fine-tuning
  python3 scripts/finetune_llm.py \
    --input /data/training/finetune_pairs.jsonl \
    --output /data/models/neuranac-nac-lora \
    --epochs 3 \
    --base-model unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit

  # Or run via Docker (recommended):
  docker run --gpus all -v /data:/data neuranac/finetune-llm:latest

After fine-tuning, deploy the adapter:
  1. Copy /data/models/neuranac-nac-lora/ to the Ollama host
  2. Create Modelfile referencing the adapter (see deploy/ollama/Modelfile.neuranac-nac)
  3. Run: ollama create neuranac-nac -f deploy/ollama/Modelfile.neuranac-nac
  4. Set AI_LLM_MODEL=neuranac-nac in the AI Engine environment
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path


def check_dependencies():
    """Verify fine-tuning dependencies are installed."""
    missing = []
    for pkg in ["unsloth", "datasets", "trl", "transformers", "torch"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"ERROR: Missing packages: {', '.join(missing)}")
        print("Install with: pip install unsloth datasets trl transformers torch")
        print("Or use the Docker image: docker run --gpus all neuranac/finetune-llm:latest")
        sys.exit(1)


def load_training_data(input_path: str) -> list:
    """Load JSONL training data."""
    pairs = []
    with open(input_path) as f:
        for line in f:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    print(f"Loaded {len(pairs)} training pairs from {input_path}")
    return pairs


def format_as_llama_chat(pairs: list) -> list:
    """Format training pairs as Llama 3.1 chat template strings."""
    formatted = []
    for p in pairs:
        text = (
            f"<|begin_of_text|>"
            f"<|start_header_id|>system<|end_header_id|>\n\n"
            f"You are the NeuraNAC AI Assistant, an expert in Network Access Control (NAC), "
            f"RADIUS, TACACS+, 802.1X, and enterprise network security.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"{p['instruction']}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            f"{p['output']}<|eot_id|>"
        )
        formatted.append({"text": text})
    return formatted


def run_finetune(args):
    """Run the LoRA fine-tuning process."""
    check_dependencies()

    from unsloth import FastLanguageModel
    from datasets import Dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments
    import torch

    print(f"\n{'='*60}")
    print(f"NeuraNAC NAC LLM Fine-Tuning")
    print(f"{'='*60}")
    print(f"  Base model:  {args.base_model}")
    print(f"  Input:       {args.input}")
    print(f"  Output:      {args.output}")
    print(f"  Epochs:      {args.epochs}")
    print(f"  Batch size:  {args.batch_size}")
    print(f"  LoRA rank:   {args.lora_rank}")
    print(f"  LR:          {args.learning_rate}")
    print(f"  Max seq len: {args.max_seq_length}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  Device:      {device}")
    if device == "cpu":
        print("  WARNING: Training on CPU will be very slow. GPU recommended.")
    print()

    # 1. Load training data
    pairs = load_training_data(args.input)
    if len(pairs) < 10:
        print(f"ERROR: Need at least 10 training pairs, got {len(pairs)}")
        sys.exit(1)

    formatted = format_as_llama_chat(pairs)
    dataset = Dataset.from_list(formatted)
    print(f"Dataset: {len(dataset)} examples")

    # 2. Load base model with 4-bit quantization
    print("\nLoading base model (4-bit quantized)...")
    t0 = time.time()
    model, tokenizer = FastLanguageModel.from_pretrained(
        args.base_model,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
        dtype=None,  # auto-detect
    )
    print(f"  Model loaded in {time.time() - t0:.1f}s")

    # 3. Add LoRA adapter
    print("Adding LoRA adapter...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_rank,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=args.lora_rank,  # alpha = rank is a common default
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Count trainable params
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # 4. Train
    print(f"\nStarting training ({args.epochs} epochs)...")
    t0 = time.time()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        warmup_steps=max(5, len(dataset) // (args.batch_size * 10)),
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        fp16=not torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False,
        bf16=torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False,
        logging_steps=max(1, len(dataset) // (args.batch_size * 10)),
        save_strategy="epoch",
        save_total_limit=2,
        seed=42,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        tokenizer=tokenizer,
        args=training_args,
    )

    stats = trainer.train()
    duration = time.time() - t0

    print(f"\nTraining complete in {duration:.0f}s")
    print(f"  Loss: {stats.training_loss:.4f}")
    print(f"  Steps: {stats.global_step}")

    # 5. Save LoRA adapter
    print(f"\nSaving LoRA adapter to {output_dir}...")
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # 6. Write metadata
    metadata = {
        "base_model": args.base_model,
        "lora_rank": args.lora_rank,
        "epochs": args.epochs,
        "training_samples": len(dataset),
        "training_loss": float(stats.training_loss),
        "training_steps": stats.global_step,
        "training_duration_seconds": round(duration, 1),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "max_seq_length": args.max_seq_length,
    }
    with open(output_dir / "training_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Fine-tuning COMPLETE")
    print(f"{'='*60}")
    print(f"  Adapter saved to: {output_dir}")
    print(f"  Metadata:         {output_dir / 'training_metadata.json'}")
    print()
    print("Next steps:")
    print("  1. Copy the adapter to the Ollama host")
    print("  2. Update deploy/ollama/Modelfile.neuranac-nac with the ADAPTER path")
    print("  3. Run: ollama create neuranac-nac -f deploy/ollama/Modelfile.neuranac-nac")
    print("  4. Set AI_LLM_MODEL=neuranac-nac in the AI Engine environment")
    print("  5. Restart the AI Engine: docker compose restart ai-engine")


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune Llama 3.1 8B for NeuraNAC NAC domain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", default="/data/training/finetune_pairs.jsonl",
                        help="Input JSONL training data file")
    parser.add_argument("--output", default="/data/models/neuranac-nac-lora",
                        help="Output directory for LoRA adapter")
    parser.add_argument("--base-model", default="unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
                        help="Base model from Hugging Face")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=2,
                        help="Per-device training batch size")
    parser.add_argument("--gradient-accumulation", type=int, default=4,
                        help="Gradient accumulation steps")
    parser.add_argument("--learning-rate", type=float, default=2e-4,
                        help="Learning rate")
    parser.add_argument("--lora-rank", type=int, default=16,
                        help="LoRA rank (higher = more capacity, more VRAM)")
    parser.add_argument("--max-seq-length", type=int, default=4096,
                        help="Maximum sequence length")

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"ERROR: Input file not found: {args.input}")
        print("Run collect_training_data.py first:")
        print(f"  python3 scripts/collect_training_data.py --output {args.input}")
        sys.exit(1)

    run_finetune(args)


if __name__ == "__main__":
    main()
