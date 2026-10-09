import os
import json
import sys
from pathlib import Path

import torch
from torch import nn

ROOT = Path(r"D:\AUS_TEXT")
INDIC_PATH = ROOT / "IndicPhotoOCR"
FINE_CKPT = ROOT / "marathi_finetuned.ckpt"
OUT_DIR = ROOT / "android_agent_bundle"
OUT_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(INDIC_PATH))
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from IndicPhotoOCR.utils.strhub.models.utils import load_from_checkpoint


class ExportablePARSeq(nn.Module):
    """Traceable export wrapper for the PARSeq recognition model."""

    def __init__(self, lightning_model):
        super().__init__()
        self.model = lightning_model.model
        self.bos_id = lightning_model.tokenizer.bos_id
        self.eos_id = lightning_model.tokenizer.eos_id
        self.pad_id = lightning_model.tokenizer.pad_id
        self.max_label_length = lightning_model.hparams.max_label_length
        self.decode_ar = lightning_model.model.decode_ar
        self.refine_iters = lightning_model.model.refine_iters

    def forward(self, images):
        bs = images.shape[0]
        num_steps = self.max_label_length + 1
        memory = self.model.encode(images)
        pos_queries = self.model.pos_queries[:, :num_steps].expand(bs, -1, -1)
        tgt_mask = query_mask = torch.triu(
            torch.ones((num_steps, num_steps), dtype=torch.bool, device=images.device),
            diagonal=1,
        )

        if self.decode_ar:
            tgt_in = torch.full((bs, num_steps), self.pad_id, dtype=torch.long, device=images.device)
            tgt_in[:, 0] = self.bos_id
            logits = []
            for i in range(num_steps):
                j = i + 1
                tgt_out = self.model.decode(
                    tgt_in[:, :j],
                    memory,
                    tgt_mask[:j, :j],
                    tgt_query=pos_queries[:, i:j],
                    tgt_query_mask=query_mask[i:j, :j],
                )
                p_i = self.model.head(tgt_out)
                logits.append(p_i)
                if j < num_steps:
                    tgt_in[:, j] = p_i[:, -1].argmax(-1)
            logits = torch.cat(logits, dim=1)
        else:
            tgt_in = torch.full((bs, 1), self.bos_id, dtype=torch.long, device=images.device)
            tgt_out = self.model.decode(tgt_in, memory, tgt_query=pos_queries)
            logits = self.model.head(tgt_out)

        if self.refine_iters:
            query_mask = query_mask[:num_steps, :num_steps]
            query_mask[torch.triu(torch.ones(num_steps, num_steps, dtype=torch.bool, device=images.device), diagonal=2)] = 0
            bos = torch.full((bs, 1), self.bos_id, dtype=torch.long, device=images.device)
            for _ in range(self.refine_iters):
                tgt_in = torch.cat([bos, logits[:, :-1].argmax(-1)], dim=1)
                tgt_padding_mask = (tgt_in == self.eos_id).int().cumsum(-1) > 0
                tgt_out = self.model.decode(
                    tgt_in,
                    memory,
                    tgt_mask,
                    tgt_padding_mask,
                    pos_queries,
                    query_mask[:, : tgt_in.shape[1]],
                )
                logits = self.model.head(tgt_out)

        return logits


print("Loading fine-tuned checkpoint...")
model = load_from_checkpoint(str(FINE_CKPT), map_location="cpu")
model.eval()

img_size = model.hparams.img_size
if isinstance(img_size, int):
    H = W = img_size
else:
    try:
        H, W = img_size
    except Exception:
        H = W = 32

print(f"Using image size: {H}x{W}")
example_input = torch.randn(1, 3, H, W)
export_model = ExportablePARSeq(model).eval()

with torch.no_grad():
    eager_logits = export_model(example_input)

# Keep the autoregressive loop fixed-length so tracing captures every step.
torchscript_path = OUT_DIR / "marathi_finetuned_trace.pt"
traced_model = torch.jit.trace(export_model, example_input, check_trace=True)
traced_model.save(str(torchscript_path))
print(f"TorchScript exported to: {torchscript_path}")
with torch.no_grad():
    traced_logits = traced_model(example_input)
if eager_logits.shape != traced_logits.shape or eager_logits.shape[1] != model.hparams.max_label_length + 1:
    raise RuntimeError(f"Unexpected export shape: eager={tuple(eager_logits.shape)}, traced={tuple(traced_logits.shape)}")
if not torch.isfinite(traced_logits).all():
    raise RuntimeError("TorchScript output contains non-finite values")
print(f"TorchScript smoke test passed: {tuple(traced_logits.shape)}")

contract = {
    "model": {
        "name": torchscript_path.name,
        "preferred_runtime": "TorchScript (desktop validated; Android runtime validation pending)",
        "input_shape": [1, 3, H, W],
        "input_dtype": "float32",
        "output_shape": [1, model.hparams.max_label_length + 1, len(model.tokenizer) - 2],
        "output_dtype": "float32 logits",
        "max_label_length": model.hparams.max_label_length,
        "charset_len": len(model.hparams.charset_train),
        "charset_test": model.hparams.charset_test,
        "decode_ar": model.model.decode_ar,
        "refine_iters": model.model.refine_iters,
        "special_tokens": {
            model.tokenizer.EOS: model.tokenizer.eos_id,
            model.tokenizer.BOS: model.tokenizer.bos_id,
            model.tokenizer.PAD: model.tokenizer.pad_id,
        },
        "preprocessing": {
            "resize": [W, H],
            "interpolation": "bicubic",
            "color_mode": "RGB",
            "normalize": "((pixel / 255.0) - 0.5) / 0.5",
        },
        "token_table": list(model.tokenizer._itos),
        "decode": {
            "selection": "argmax over classes per timestep",
            "stop_at_first_eos": True,
            "preserve_repeated_characters": True,
            "apply_charset_test_filter": True,
        },
    },
    "android_notes": {
        "recommended_model": torchscript_path.name,
        "onnx_warning": "ONNX export is experimental; Android and ONNX Runtime compatibility have not been validated.",
        "integration_note": "Input is one cropped word, not a full camera/gallery image. Detect text regions and order/crop them before recognition.",
    },
}
contract_path = OUT_DIR / "model_contract.json"
with contract_path.open("w", encoding="utf-8") as f:
    json.dump(contract, f, ensure_ascii=False, indent=2)
print(f"Model contract written to: {contract_path}")

# Optional ONNX export; TorchScript is the validated desktop artifact.
try:
    import onnx  # noqa: F401
except ImportError:
    print("onnx package not found; skipping ONNX export.")
    onnx = None

if onnx is not None:
    onnx_path = OUT_DIR / "marathi_finetuned.onnx"
    torch.onnx.export(
        export_model,
        example_input,
        str(onnx_path),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input_image"],
        output_names=["logits"],
        dynamic_axes={
            "input_image": {0: "batch_size"},
            "logits": {0: "batch_size"},
        },
    )

    print(f"ONNX exported to: {onnx_path}")
print("Export finished.")
