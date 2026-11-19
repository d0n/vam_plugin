# Local engines, Silero and voice barge-in (version 29)

Everything here runs in the companion app on your own computer. The plugin changes only by the entry "Silero" in the menu **VAD engine**.

## Ollama as a language model (no key, no cloud)

1. Install [Ollama](https://ollama.com) and pull a model, e.g. `ollama pull llama3.2` (or `qwen3:8b`, `gemma3`; for good German sentences a larger model is worth it). Ollama listens on `http://127.0.0.1:11434`.
2. In VaM: tab Voice > AI Character > **Language model** = `ollama` (or `engines.llm` in `config.json`). The mode should be **chain** (or qa / auto without an xAI key); realtime is xAI only.
3. Settings in `config.json` under `ai.ollama` (file only, restart the app): `base_url` (default `http://127.0.0.1:11434`), `model` (`llama3.2`), `max_output_tokens` (400), `temperature` (0.7), `keep_alive` (`10m`: how long the model stays in memory), `max_messages` (40 conversation messages the app sends with every question), `timeout_s` (120).

What is different from xAI: Ollama keeps no conversation, so the app keeps the history itself (persona and style rules as a system message). **No body tools** (function calls of local models are too inconsistent): expression and gesture come through a `<<happy nod>>` shorthand at the start of the answer, as usual in the chain; if the model does not stick to it, the emotion fallback takes over. Speech recognition (STT) and voice (TTS) stay xAI, ElevenLabs or the test engines; **with Ollama selected the memory is also summarized locally** (nothing goes to xAI). If Ollama is not reachable or the model is not installed, the status line says so clearly (`ollama serve` or `ollama pull <model>`) and the test engine answers as a fallback.

Not tested in VaM and not against a real Ollama (T18).

## Silero as voice activity detection (onnxruntime, without torch)

1. `python -m pip install onnxruntime` (brings NumPy).
2. Download the model file `silero_vad.onnx` (MIT license, version 5) from <https://github.com/snakers4/silero-vad/tree/master/src/silero_vad/data> and put it at `<VaM>/Saves/PluginData/AIBody/models/silero_vad.onnx` (or give the path in the environment variable `AIBODY_SILERO_MODEL`). The file does **not** belong in the package or in the repository.
3. Tab Client Character **VAD engine** = `Silero`. `Auto` takes Silero as soon as the file is there (otherwise WebRTC, otherwise the built-in detector). **VAD strictness** 0 to 3 sets the speech probability threshold (0.3 / 0.4 / 0.5 / 0.65); **VAD threshold** stays a lower limit for the level.

The info field shows what really runs (`silero (onnxruntime), strictness 2`) or why not (file missing, onnxruntime missing, wrong model version). On an error during operation the level rule decides again. Silero listens in 32 ms chunks; the app collects the 30 ms frames. With the model running on the CPU with one thread, a chunk costs fractions of a millisecond.

## Voice barge-in without headphones (loudness rule)

Key `ai.barge_in` in `config.json` (file only), **off** by default:

| Key | Default | Meaning |
|---|---|---|
| `enabled` | false | rule on |
| `ratio` | 2.0 | how much louder than the learned echo the voice must be |
| `min_ms` | 600 | how long it must be continuously louder |
| `floor` | 0.02 | below this level (0 to 1) it is never the user |

While the character speaks (from the reported `speech_started`), the app learns the echo level on the microphone as a slowly decaying peak value (the first 450 ms only teach). If a stretch of `min_ms` stays clearly above `ratio` times the echo, it counts as the user: the character stops, the echo gate opens, and the loud stretch goes on as the beginning of the utterance to the recognition (chain) or to the realtime server. Only in voice activation mode, not with push-to-talk (which interrupts anyway).

Limits: it is a rule, not echo cancellation. A quiet voice or loud speakers do not trigger it; a very loud sentence of the character, a door slam or a cough can. With headphones the toggle **Voice barge-in (headphones)** stays better. Change `ratio` and `min_ms` and compare with the level meter (T18).

## What is not there

faster-whisper (local speech recognition) and Piper (local voice) are backlog (see BACKLOG.md); so are tool calls for Ollama.
