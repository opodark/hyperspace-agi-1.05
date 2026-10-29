#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Script di Fine-Tuning QLoRA con Unsloth per Nodi HyperSpace Mesh (HP OMEN / ASUS WSL2).

Esegue l'addestramento ultra-rapido (2x-5x più veloce con 70% meno memoria) su GPU
NVIDIA con 8 GB VRAM (RTX 3070 Laptop), producendo un adapter LoRA o pesi fusi esportati
direttamente in formato GGUF per Ollama.

Requisiti (solo su OMEN/ASUS sotto Linux o WSL2 con CUDA):
    pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
    pip install --no-deps trl peft accelerate bitsandbytes

Uso:
    python scripts/unsloth/train_hyperspace_lora.py --dataset data/unsloth_dataset.json --epochs 1
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check_cuda_environment():
    """Verifica che l'ambiente supporti CUDA e GPU NVIDIA."""
    try:
        import torch
        if not torch.cuda.is_available():
            print("⚠️ CUDA non disponibile. Questo script richiede una GPU NVIDIA (OMEN/ASUS con CUDA).")
            return False
        device_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        print(f"✓ GPU Rilevata: {device_name} ({vram_gb:.2f} GB VRAM)")
        return True
    except ImportError:
        print("⚠️ PyTorch non installato in questo ambiente.")
        return False


def main():
    parser = argparse.ArgumentParser(description="HyperSpace LoRA Fine-Tuner via Unsloth")
    parser.add_argument("--model", type=str, default="unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit", help="Modello base 4-bit")
    parser.add_argument("--dataset", type=str, default="data/unsloth_dataset.json", help="Path del dataset Alpaca JSON")
    parser.add_argument("--output-dir", type=str, default="data/lora_models/hyperspace-qwen-7b", help="Directory di output pesi")
    parser.add_argument("--export-gguf", action="store_true", default=True, help="Esporta direttamente in formato GGUF per Ollama")
    parser.add_argument("--quant-method", type=str, default="q4_k_m", help="Metodo di quantizzazione GGUF (q4_k_m, q8_0)")
    parser.add_argument("--max-seq-len", type=int, default=2048, help="Lunghezza massima contesto")
    parser.add_argument("--epochs", type=int, default=1, help="Numero di epoche di addestramento")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"🦥 UNSLOTH LORA REFINERY — HYPERSPACE AGI 1.05")
    print(f"{'='*70}\n")

    if not check_cuda_environment():
        print("\nℹ️ Nota: per eseguire il training, lanciare questo script dentro l'ambiente WSL2 di HP OMEN 16 o ASUS V16.")
        sys.exit(0)

    try:
        from unsloth import FastLanguageModel
        from datasets import load_dataset
        from trl import SFTTrainer
        from transformers import TrainingArguments
    except ImportError as e:
        print(f"❌ Dipendenze Unsloth mancanti: {e}")
        print("Installa con: pip install \"unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git\"")
        sys.exit(1)

    print(f"Caricamento modello base: {args.model}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq_len,
        dtype=None,
        load_in_4bit=True,
    )

    print("Configurazione PEFT / LoRA Adapter...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Formattazione prompt Alpaca
    alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
{}"""

    def formatting_prompts_func(examples):
        instructions = examples["instruction"]
        inputs = examples["input"]
        outputs = examples["output"]
        texts = []
        for instruction, input_text, output in zip(instructions, inputs, outputs):
            text = alpaca_prompt.format(instruction, input_text, output) + tokenizer.eos_token
            texts.append(text)
        return {"text": texts}

    print(f"Caricamento dataset: {args.dataset}...")
    dataset = load_dataset("json", data_files=args.dataset, split="train")
    dataset = dataset.map(formatting_prompts_func, batched=True)

    print("Avvio SFTTrainer ottimizzato per 8 GB VRAM...")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=args.max_seq_len,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            num_train_epochs=args.epochs,
            learning_rate=2e-4,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=42,
            output_dir=args.output_dir,
        ),
    )

    trainer.train()
    print(f"✓ Training completato! Salvataggio adapter in {args.output_dir}...")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    if args.export_gguf:
        print(f"Esportazione modello unificato in formato GGUF ({args.quant_method})...")
        gguf_dir = Path(args.output_dir) / "gguf"
        model.save_pretrained_gguf(str(gguf_dir), tokenizer, quantization_method=args.quant_method)
        print(f"✓ File GGUF salvato in: {gguf_dir}")

        # Genera Modelfile per Ollama
        modelfile_path = gguf_dir / "Modelfile"
        modelfile_content = f"FROM ./{args.quant_method}.gguf\nPARAMETER temperature 0.2\nPARAMETER stop <|im_end|>\n"
        modelfile_path.write_text(modelfile_content, encoding="utf-8")
        print(f"✓ Modelfile per Ollama generato in: {modelfile_path}")
        print(f"Per installarlo su Ollama esegui: ollama create hyperspace-coder:7b -f {modelfile_path}")


if __name__ == "__main__":
    main()
