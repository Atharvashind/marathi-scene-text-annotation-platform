# Marathi model bundle review

The supplied ZIP is an integration asset bundle, not a built APK or Android project.
Both model files are byte-identical to the previously supplied exports.

## Verified

- Contract has 117 ordinary tokens, EOS=0, BOS=118, PAD=119; all 120 table entries are unique and special-token indices agree.
- Input contract: RGB float32 NCHW [1,3,32,128], resize to width 128 / height 32, normalize each channel with (pixel/255 - 0.5)/0.5.
- The TorchScript export ran on desktop PyTorch 2.6.0 CPU with a zero tensor, returning finite float32 [1,26,118] scores. This is a runtime smoke test, not an accuracy test.
- ONNX passes structural validation, but the installed desktop ONNX CPU runtime fails to load Where_15. No Android runtime test has been completed.

## Issues before enabling this model in the app

1. The traced forward graph contains exactly five unrolled autoregressive head calls before refinement. Refinement returns 26 positions, but uses the fixed short context. Output shape alone does not establish correct recognition of longer words. Re-export with scripted/data-independent decoding, or provide evidence that the export matches the original model on representative short and long words.
2. The supplied example removes all EOS tokens and continues decoding. PARSeq decoding should stop at the first EOS; later positions must not be appended. decode.py implements this and retains repeated characters.
3. This is a cropped text recognizer. The app accepts full camera/gallery photos, so word detection/cropping and reading order must precede recognition.
4. No charset_test or CharsetAdapter implementation was supplied. The training vocabulary is available, but any evaluation/output filtering remains unspecified.
5. Desktop TorchScript success does not establish compatibility with an Android runtime. The archive has no Lite Interpreter bytecode. PyTorch Mobile is no longer actively supported: https://docs.pytorch.org/tutorials/recipes/mobile_interpreter.html

## Needed to finish integration reliably

Provide the original model/export source or notebook (including charset_test and preprocessing interpolation), plus sample cropped Marathi words and expected text. Correct the traced decoding or validate it against the original model, then test the selected mobile runtime on a device before routing Marathi scans through it.

The existing app OCR remains unchanged pending these checks.
