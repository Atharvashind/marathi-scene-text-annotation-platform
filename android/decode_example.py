import json
import re
from pathlib import Path

import torch

ROOT = Path(r"D:\AUS_TEXT")
MODEL_PATH = ROOT / "android_agent_bundle" / "marathi_finetuned_trace.pt"
CONTRACT_PATH = ROOT / "android_agent_bundle" / "model_contract.json"

with CONTRACT_PATH.open("r", encoding="utf-8") as f:
    contract = json.load(f)

token_table = contract["model"]["token_table"]
charset_test = contract["model"]["charset_test"]


def decode_logits(logits, tokens, target_charset):
    token_ids = logits[0].argmax(dim=-1).tolist()
    output = []
    for token_id in token_ids:
        token = tokens[token_id]
        if token == "[E]":
            break
        if token not in {"[B]", "[P]"}:
            output.append(token)

    text = "".join(output)
    if target_charset == target_charset.lower():
        text = text.lower()
    elif target_charset == target_charset.upper():
        text = text.upper()
    return re.sub(f"[^{re.escape(target_charset)}]", "", text)

model = torch.jit.load(str(MODEL_PATH), map_location="cpu")
model.eval()

# Zero input is only a runtime smoke test, not an accuracy sample.
example = torch.zeros(1, 3, 32, 128)
with torch.no_grad():
    logits = model(example)

print("output_shape:", tuple(logits.shape))
print("classes:", logits.shape[-1])

text = decode_logits(logits, token_table, charset_test)
print("decoded_preview:", text)
