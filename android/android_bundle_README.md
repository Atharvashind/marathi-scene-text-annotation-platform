# Marathi OCR Android Integration Bundle

This folder contains the Marathi word-recognition model and its deployment contract. It is not a built APK or Android project.

## Files

- `marathi_finetuned_trace.pt` — TorchScript export; desktop CPU validated
- `marathi_finetuned.onnx` — experimental ONNX export; Android/ONNX Runtime compatibility is not established
- `model_contract.json` — exact model contract and token table
- `decode_example.py` — Python reference decode logic using the same tokenizer order and charset filter
- `validation_results.csv` — model-to-export comparison on 60 long test words
- `validation_samples/` — 12 real test crops, expected labels, and predictions from both paths

## Model contract

- Input: float32 RGB NCHW `[1, 3, 32, 128]`
- Output: float32 logits `[1, 26, 118]`
- Resize to 128x32 with bicubic interpolation, convert to RGB, normalize to `((pixel / 255.0) - 0.5) / 0.5`
- Token IDs: use the `token_table` in `model_contract.json`
- Special tokens: `[E]` = 0, `[B]` = 118, `[P]` = 119
- `charset_test` and the adapter filter are specified in `model_contract.json`
- Inference settings: autoregressive decoding enabled, one refinement iteration, 25 label positions plus EOS

## Android decode rule

1. Take argmax over the class dimension at each time step.
2. Read tokens in timestep order and stop at the first `[E]`.
3. Keep repeated characters; apply the `charset_test` filter from the contract.

Example:

```python
# pseudo-code
scores = output[0]                  # [26, 118]
best_ids = scores.argmax(dim=1)
chars = []
for token_id in best_ids.tolist():
	token = token_table[token_id]
	if token == '[E]':
		break
	if token not in {'[B]', '[P]'}:
		chars.append(token)
text = charset_adapter(''.join(chars))
```

This is a cropped-word recognizer: full camera/gallery images need text detection, crop extraction, and reading-order handling before recognition. The desktop comparison does not establish Android runtime compatibility; test the selected runtime on a target device before routing Marathi scans through it.

## Export validation

Run `python validate_android_export.py` from the workspace root to compare the TorchScript model against the fine-tuned checkpoint on up to 60 test words with at least six Unicode code points. The current CPU run produced identical decoded predictions for all 60 samples; both models matched the ground-truth labels for 58/60. This is a targeted parity check, not a full-dataset accuracy benchmark or Android-device test.
