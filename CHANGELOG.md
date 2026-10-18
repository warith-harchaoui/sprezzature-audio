# Changelog: sprezzature-audio

## v1.4.0 (2026-10-18): the package you can import, and the door you can find

The engine was always here. Reaching it was the problem.

`import sprezzature_audio` handed back a version string, an author and an
email — the surface `SURFACES.md` calls the easiest of the five to fake,
because `pip install` works, `import` works, and the caller still has nothing
to call. The code lived in `sprezzature_audio_scripts`, a package named for
how it was built rather than for what it does. And on the command line there
were fifteen `sprezzature-audio-*` commands and no way to learn that without
reading the README.

### Added

- **A library surface.** `sprezzature_audio` now exports the engine. What is
  importable with no extras at all is everything that needs no model: the
  shared WebVTT reader and writer (`parse`, `write_vtt`, `write_srt`, `Cue`),
  the caption audit (`audit_cues`, `Finding`), speaker attribution over an
  existing transcript (`attribute_speakers` and the three renderers), the
  word- and diarization-error rates, what accelerator this host will use, and
  which language a document is written in. That is deliberately the same set
  the HTTP API serves, and for the same reason: it is fast and pure.
- **The model-backed half, served lazily** (PEP 562): transcription,
  diarization, identification, translation and narration resolve on first
  use, each naming *its own* extra when the dependency is missing. Being told
  to install the captions extra when you asked for `synthesise` is worse than
  no message at all.
- **Two front doors**, over one table: `make-audio` (argparse) and
  `sprezzature-audio` (click). Both list the fifteen tools with a line each
  saying when to reach for them, and dispatch to the same engine. The table
  is the dispatcher *and* the help text, so a tool cannot be listed and
  unreachable, or reachable and undocumented.
- **`sprezzature-audio-benchmark`** — the measuring tool had a `main()` and
  no line in `[project.scripts]`, so it ran from a clone and from nowhere
  else. Its own docstring argues against exactly that: "a measurement tool
  that is hard to install does not get used, and one nobody runs is worse
  than none, because it lets 'it feels faster' stand unchallenged."
- **A `docker-compose.yml`**, as every brick with a Dockerfile now owes. Three
  services: the API, a `diarize` profile that is the same build with NeMo
  added, and the model server behind a `translate` profile. The image also
  gained `ffmpeg` and `espeak-ng`, the two halves pip cannot supply.

### Fixed

- **Six commands told the reader to type something that does not exist.**
  `sprezzature-audio-narrate-kokoro --help` printed `usage: narrate_kokoro`;
  `benchmark_stt.py`, `pick_voice`, `install_narrate` and the two other
  narration engines did the same. All six are module names. The guard that
  was supposed to catch this matched `prog="sprezzature-*"`, so it caught a
  command named *wrongly* and was blind to one named after nothing at all —
  now widened, and verified to fail on a sabotage.
- **Five install hints named a file a wheel does not contain.** "kokoro-onnx
  not installed; pip install -r requirements-narrate-kokoro.txt" is sound
  advice in a clone and useless to the one person who most needs it: someone
  who ran `pip install sprezzature-audio`. Each now names the extra first and
  the requirements file second, and a test holds every runtime hint to it.
- **The default Docker command printed `--help` and exited** — a container
  that looks like it works and does nothing. It serves the API now.

### Changed

- The package description and the module docstring said nothing about
  narration, which has been half of this brick since 1.3.0.
- Three narration engines described themselves as wrappers "for
  narrate_post.py", a script that moved to `sprezzature-publish` when the
  bricks left the monorepo.

## v1.3.0 (2026-10-18): a voice that reads, rather than one that impersonates

The two engines that arrived in 1.2.0 are voice-*cloning* engines, and
cloning is not what "this article should have a voice" asks for. Both want a
reference recording, both pull a multi-gigabyte torch stack, and Chatterbox
cannot even load its checkpoint without `resemble-perth` — a watermarker
nothing declared. For reading a page aloud, that is a great deal of
machinery between the text and the sound, and none of it addresses the one
thing that mattered: the result did not sound good.

### Added

- **Kokoro** — `sprezzature-audio-narrate-kokoro`, now the default engine.
  82 M parameters through ONNX Runtime, **no torch at all**, Apache-2.0 in
  code *and* weights (the bar that ruled out F5-TTS and XTTS-v2, whose
  weights are non-commercial). 54 voices across nine languages, about 340 MB
  fetched by `sprezzature-audio-install-voice --engine kokoro`. On a laptop
  CPU it synthesises at roughly a fifth of real time.
- **The voice follows the language of the text.** Nobody passes a flag:
  `_lang` (langdetect) reads the segments and the voice that speaks that
  language is chosen. This is not a convenience — the detected language is
  what the phonemiser works from, so French read as English is not French in
  an American accent, it is an American spelling the words out. When the
  language has no Kokoro voice, the result says `language_fallback: true`
  rather than passing the substitute off as a choice.
- **A record of what was ignored.** Kokoro has no emotion dial, and the
  segments carry `emotion` and `intensity` because Chatterbox does. The
  engine applies `pace`, reports the rest under `ignored_hints`, and
  reports nothing when nothing was asked for. `--voice-sample` is refused
  outright, naming the two engines that honour it.

### Changed

- **`[narrate]` is now the light extra** — it resolves to `[narrate-kokoro]`,
  and the cloning engines moved to `[narrate-openvoice]` and
  `[narrate-chatterbox]`. Installing `chatterbox-tts` into a working
  environment once downgraded torch 2.8 to 2.6 and broke an unrelated package
  that depended on it; asking for an article to be read aloud should not be
  able to do that.
- **`[all]` now includes `[narrate]`.** It was excluded when narration meant
  torch. That exclusion was about weight, not about scope.
- `[narrate-chatterbox]` declares `resemble-perth`, which Chatterbox loads
  its checkpoint through and does not declare itself. Without it
  `from_pretrained` dies on `TypeError: 'NoneType' object is not callable`,
  which names nothing that would lead anyone to the cause.

### Choosing a voice by measurement

`sprezzature-audio-voice --sample --measure` now ranks the sampled voices by
**how far their pitch moves**, in semitones between the 5th and 95th
percentile. Semitones and not hertz, because pitch is heard as a ratio: a
hundred and twenty hertz of movement is enormous on a voice centred at a
hundred hertz and unremarkable on one centred at two hundred and twenty, and
in hertz the two look the same.

This came out of asking whether the intonation could be improved, and the
answer turned out to be a measurement rather than a setting. Two things it
found:

- **The default was one of the flattest voices.** `af_heart` moves 9.8
  semitones on a test paragraph; `am_puck` moves 18.0 and `af_kore` 14.2.
  `af_heart` is the voice the model card grades A — but A rewards
  naturalness, not expressiveness, and they are not the same axis.
- **Synthesising a whole paragraph at once does nothing for intonation.**
  The hypothesis was that prosody would carry across sentences instead of
  resetting at each one. It does not: the pitch range is unchanged to within
  a tenth of a semitone. Kokoro conditions prosody on a style vector per
  utterance, and more context does not widen it. Recorded here so the
  experiment is not run twice.

The measure ranks movement, not quality — a wide voice can be wide and
unpleasant. It exists to turn fifty-four candidates into a shortlist worth
listening to, which is the part a person has to do.

### Note on espeak-ng

Kokoro turns text into phonemes with espeak-ng, and the copy bundled in the
`espeakng-loader` wheel does not find its own data on macOS: it was built on
a CI runner and resolves to that machine's home directory. The failure is not
catchable — espeak reports it from C and calls `exit(1)`, so there is no
traceback, only a path belonging to somebody else's computer. The engine
therefore prefers a system install and falls back to the wheel, and
`sprezzature-audio-install-voice` says so at install time rather than letting
it surface mid-narration. `brew install espeak-ng`, or
`apt install espeak-ng`.

## v1.2.0 (2026-10-18): the other direction, and one WebVTT

This package transcribed sound into text. It now also turns text back into
sound, because those are the same modality in opposite directions and one
package should own both: captions make sound readable, narration makes text
audible, and each lands as a timed track beside an audio file.

### Added

- **The voices**, arriving from `sprezzature-publish`:
  `sprezzature-audio-narrate-openvoice` and `-chatterbox` (OpenVoice v2 clones
  a voice from a short sample; Chatterbox renders from a voice library and
  takes emotion hints), `sprezzature-audio-voice` to choose one by listening,
  and `sprezzature-audio-install-voice` for the checkpoints. Behind a
  `[narrate]` extra, deliberately **outside `[all]`**: `all` means "every way
  to turn a recording into text", and torch is gigabytes for the opposite
  journey.
- **`sprezzature-audio-audit`** — the audit half this brick never had. Eight
  static rules over a caption track: overlapping or reversed cues, empty
  cues, reading speed, minimum and maximum duration, line width, line count.
  Defaults follow the Netflix Timed Text Style Guide and the two-line
  convention BBC and Netflix share — each one a flag, because a children's
  programme and a dense technical talk do not share a reading speed.
- **`scripts/_vtt.py`** — one WebVTT, read and written in one place, and
  exported for the siblings through `sync_helpers.py`.

### Changed

- **Four WebVTT writers became one.** Three lived here
  (`captions_from_whisper`, `caption_diarize`, `translate_captions`) and a
  fourth in `sprezzature-publish`'s narration engine. The differences were
  kept rather than flattened: `voices=False` for a translated track (W3C
  reserves `<v Name>` for the same-language `captions` track), cue
  identifiers for narration, and line structure preserved on read because the
  audit counts lines and the merger does not.
- **Milliseconds are truncated, never rounded.** The narration path had
  worked this out — "a cue must never claim to start before the sample that
  starts it" — and the caption path had not. Consolidating meant choosing the
  behaviour with a reason, not the one written first.
- **A `conftest.py`, at last.** This package had none: every test file
  inserted its own path, and nothing neutralised the content-safety scan.
  With the voices here that was a real gap — measured elsewhere in the suite
  at 19.1 s instead of 1.1 s, and a 270 MB download on any machine where
  `transformers` is installed for another reason.

## v1.1.1 (2026-10-02): the half of the dependency guard nobody runs

### Fixed

- **`mcp.py` defined `main` twice, and the two took different arguments.** One
  definition sits in the `except ImportError` branch reached when the `[mcp]`
  extra is absent, the other in the `else` branch that serves the real
  endpoint. A single console script reaches both, so to a caller they are one
  function. They were not: the fallback took nothing while the real one took
  `argv`, so `main(["--host", "127.0.0.1"])` answered on a machine with the
  extra and raised `TypeError` on a machine without it. The broken half is the
  one a reader who skipped the extra meets first.
- **Both installers advertised commands nothing installs.** The same class of
  defect this package fixed for `caption_diarize.py` in 1.1.0, in two more
  places.
- **`harchaoui.org` is gone, and every reference pointed at it.** The host now
  answers 503; the links go to `deraison.ai` and `sprezzature.ai`, including
  the `project.urls` homepage PyPI prints on the package page.
- **The quick start showed a command a PyPI reader cannot run.** `python
  scripts/...` is a path that exists in a clone and not in a wheel.

### Added

- **A type gate**, `mypy.ini` plus one CI step. The monorepo carried one while
  the skills lived there; at the split ruff came with the package and mypy did
  not, so no standalone package checked its own annotations. Run by hand, it
  found the `main` defect above in six packages at once. The step runs once, on
  3.12: this is a gate, not a test matrix.
- **Two tests for the same ground.** `test_mcp_fallback_signature.py` reads the
  source as a syntax tree, so it needs neither mypy nor an install.
  `test_console_scripts_exist.py` could previously report green while testing
  nothing when its scan found no candidates, which a new case rules out.
- **A versioned `.githooks/pre-push`** running the same lint, type and test
  steps as the workflow, in the same order, so a red state cannot reach the
  remote.

## v1.1.0 (2026-09-14): five surfaces, and the headline an MCP host shows

### Fixed

- `translate_captions.py` and `name_from_transcript.py` imported `best_engine_ai_helper.llm.chat` at module level, even though `best-engine-ai-helper` is only declared in the `translate` extra, not a base dependency. `pip install sprezzature-audio` with no extras broke both scripts' `--help` with a `ModuleNotFoundError`, before argument parsing even ran. The import now happens inside the function that needs it, matching the deferred-import policy every other script in this project already follows for NeMo, pywhispercpp, and numpy.
- `diarize_from_nemo.py`, `_normalise_predictions`: `nemo_toolkit` 2.4.0's `SortformerEncLabelModel.diarize` can return a third output shape (a compact `"0.000 5.840 speaker_0"` string form, distinct from both the RTTM-line and nested-tuple shapes already handled) that fell through every branch and was silently dropped. Running the diarization step against a real two-speaker recording on `nemo_toolkit` 2.4.0 produced this shape and printed "0 turn(s), 0 speaker(s)" on real speech, with no error. Added a third branch that parses it; verified against the same real output, now correctly producing 4 turns / 2 speakers matching the known ground truth.
- `caption_diarize.py`: its own Click command was hardcoded as `"sprezzature-audio-caption-diarize"`, a name nothing installs; `pyproject.toml` registers this script as `sprezzature-audio-pipeline`. Every other script's hardcoded name already matched its console-script entry; this one didn't, so its `--help` usage line and every epilog example command were unrunnable (`command not found`). Fixed to match, and added a regression test (`test_click_command_name_matches_its_installed_console_script`) parametrized over all six console scripts so this class of drift cannot recur silently.
- README.md's and LISEZMOI.md's "Quick start" sections showed `python scripts/caption_diarize.py meeting.mp4`, implying the combined pipeline takes a media file directly. It does not: `--captions` and `--diarization` are both required options pointing at files the two upstream steps must already have produced. Running the example as written fails immediately with `Error: Missing option '--captions'`. Fixed to show the real three-command sequence, matching what EXAMPLES.md's own "Full pipeline" section already correctly showed.

- **The API could not reach its own scripts from the wheel.** It imported them
  by bare name, which works in a checkout — `scripts/` is on `sys.path` — and
  raises `ModuleNotFoundError` once installed, where the same modules live
  under `sprezzature_audio_scripts`. Both layouts work now.
- **`…-mcp --help` started the server instead of answering.** Argument parsing
  happens before anything binds, `--host` / `--port` are options, and the
  default host moved from `0.0.0.0` to `127.0.0.1`.
- **The `BSD Software License` classifier does not exist.** PyPI would have
  refused the upload outright.

### Changed

- `translate_captions.py` and `name_from_transcript.py` now call `best_engine_ai_helper.llm.chat()` instead of the earlier `sprezzature_local` client. The LLM endpoint and model are still configured via the `SPREZZATURE_LLM_*` environment variables; only the package that implements the call changed.
- The `scripts/` package installs under the `sprezzature_audio_scripts` distribution name, so it no longer collides with the `scripts` package of sibling `sprezzature-*` repositories on `pip install`. The console-script names (`sprezzature-audio-captions`, `sprezzature-audio-diarize`, and so on) are unchanged.

### Added

- **An HTTP API and an MCP server.** `pip install 'sprezzature-audio[api]'`
  mounts the caption / diarize / identify / translate scripts as routes;
  `[mcp]` derives the MCP tools from them. With a benchmark command and a
  device report, so the machine you are on is a fact rather than a guess.
- **Every MCP tool carries a written summary.** FastAPI derives a missing
  `summary` from the function name, so the headline an MCP host displayed was
  "Wer", "Der" and "Convert" — most of what an agent reads when choosing
  between tools from several servers. Written by hand now, with a description
  that says when to call the tool and what it does *not* do, and two tests
  that fail the build if either regresses.
- **`TRIGGERS.md` routes on the four questions this package answers**, in
  order: what was said, who spoke when, who is who, what language. A phrase
  list cannot generalise; the four questions are closed. The surface rule it
  carries: **audio in → CLI, text in → MCP.**

- `tests/test_scripts.py`: grew from 7 to 76 tests across two prior passes plus this one, covering every previously-untested pure function in `caption_diarize.py`, `diarize_from_nemo.py`, `name_from_transcript.py`, `translate_captions.py`, `identify_from_titanet.py`, `_vocab.py`, `_argparse.py`, and `_click.py`, plus regression tests for the two functional bugs above (the NeMo third output shape, the `caption_diarize.py` prog-name mismatch).

## v1.0.0 (2026-07-29)

Initial standalone release, extracted from the `sprezzature` monorepo.

### Scripts included

- `captions_from_whisper.py`: WebVTT / SRT / plain transcript via local Whisper (vocal-helper backend).
- `diarize_from_nemo.py`: RTTM + JSON turns via NeMo Sortformer.
- `identify_from_titanet.py`: Speaker identity verification via NeMo TitaNet.
- `caption_diarize.py`: Combined captioning + diarization pipeline.
- `name_from_transcript.py`: Speaker name inference (regex pass + optional LLM pass).
- `translate_captions.py`: VTT/SRT translation via a local LLM.
- `install_captions.py`: Pre-download Whisper GGML weights.
- `install_diarize.py`: Pre-download NeMo Sortformer and TitaNet checkpoints.
- `_argparse.py`, `_click.py`, `_lang.py`, `_vocab.py`: Shared helpers.
