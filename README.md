# Rebind

*Books that AI cut apart, read back together as art.*

Rebind reads a whole book without destroying it and turns it into a 3D landscape in which every element, every decision and every pixel traces back to the passage it came from. Project 2 for AIPI 590 (Responsible AI / Explainable AI), Duke.

Status: reading pipeline done; first version of the map (stage 2 of 3).

## Run the reading pipeline

Needs Python 3.11+, [uv](https://docs.astral.sh/uv/) and, for local models, [Ollama](https://ollama.com).

```bash
uv sync
uv run rebind segment                                  # passages with source offsets
ollama pull olmo-3:7b-instruct
uv run rebind read --chapters 1-3                      # cited facts, checked against the text
uv run rebind summary out/pride-and-prejudice/runs/<run>
uv run rebind resolve out/pride-and-prejudice/runs/<run>  # merge names into characters
uv run rebind locate out/pride-and-prejudice/runs/<run>   # where each passage takes place
uv run rebind compose out/pride-and-prejudice/runs/<run>  # layout for the site
python3 scripts/serve.py                                  # then open http://localhost:8737
uv run rebind trace out/pride-and-prejudice/runs/<run> <fact-id>
```

Other models: `--model openai-compat:<model>@<url>` for any OpenAI-compatible server (LM Studio or llama.cpp, for example), with the key in `REBIND_API_KEY`.

## How traceability works

1. **Source.** The book is the Project Gutenberg file, pinned by SHA-256 in `books/<slug>.json`. Every offset in every output points into that exact file.
2. **Passages.** Whole paragraphs grouped into ~350-word passages. Illustration captions and the printer's colophon are excluded, and each exclusion is logged with its reason in `excluded.jsonl`.
3. **Facts.** A reader model sees each passage with its sentences numbered and returns characters, interactions, places, objects, events and tone in four focused calls. Every item cites sentence numbers rather than quoting, so it cannot invent a quotation (asked for free quotes, OLMo 3 7B fabricated about 45% of them). Code, not a model, decides what is accepted:
   - *Found:* the cited sentences must exist in that passage. Each resolves to exact file offsets.
   - *Supports:* for characters, the cited sentences must contain the exact words the passage uses for them (`called_here`), as whole words; for places and objects, they must name the thing. A sentence about Elizabeth Bennet is not evidence for Mrs. Bennet.
   - *Not a pronoun:* a character "called" only "her", "you" or "the others" is refused. Those words are in nearly every sentence, so finding one proves nothing about who is meant. Descriptions such as "her sister" are still checked as words; the entity pass treats them as references, not names.
   - *Repair:* items that fail get one round in which the model is told why and may cite again or withdraw. Both attempts are kept.
   - The checker cannot catch a misreading of a correctly cited sentence (a 7B model said Darcy's "She is tolerable" was about Jane). That is what the hand-checked evaluation chapters are for.
   - Rejected items stay in `rejected.jsonl` with the reason, so the rejection rate is itself a measurement.
   - *Recheck:* the checker has a version number in `run.json`. `rebind recheck <run>` applies the current checker to an older run without calling a model: facts it now refuses move to `rejected.jsonl` with their old record, and the old `facts.jsonl` is kept as `facts.checker-<n>.jsonl`. Applying checker 2 to the full Qwen read moved 374 of 2,502 character facts (15%), 373 of them pronoun-only.
4. **Entities.** `rebind resolve <run>` merges the names the reader used ("Lizzy", "Miss Elizabeth Bennet") into one entity per character. It never edits the facts; it writes `entities/decisions.jsonl`, one line per name saying which step placed it and why:
   - *R1 spelling (code):* case, curly quotes and spacing are ignored.
   - *M1 anchors (model):* each name with 5+ mentions points at the fullest name of the same character; linked names form one entity.
   - *M2 tail (model):* rarer names are attached to an existing entity or start a new one, a few at a time.
   - *R2 titles (code):* male and female titles (Mr/Sir/Colonel vs Mrs/Miss/Lady) cannot be one person; the smaller side is split off.
   - *R3 default (code):* a name the model skipped keeps its own entity.
   - *R4 references (code):* descriptions and pronouns ("her sister", "the late Mr. Darcy", "me") mean different people in different passages, so they are never merged and never shown to the model; plural ones are groups.
   - *R5 given names (code):* two different first names cannot be one person, except standard nicknames (Lizzy/Eliza for Elizabeth, Kitty for Catherine).
   - *R6 Miss/Mrs (code):* "Miss X" and "Mrs. X" are two women.
   - *R7 fixed surnames (code):* a man's surname and a woman's maiden name cannot differ within one entity; married forms (Mrs., Lady) are exempt, so Lydia can be Mrs. Wickham. This caught the model claiming Lady Catherine's "full name is Georgiana Darcy".
   - *R8 same name (code):* the same first name and surname with compatible titles are one person (Kitty Bennet and Catherine Bennet).
   - Where a code rule overrules the model, the decision keeps the model's original answer under `overrode`.
   - The model also states what each merge rests on. Merges resting on "knowledge of the novel" rather than the example sentences, and merges of two major names, are flagged for the hand check.
5. **Settings.** `rebind locate` decides where each passage physically takes place, because a place that is mentioned is often not where the scene is (Collins talks about Rosings while at Longbourn). The choices are the book's own named places from verified facts. The model picks one per passage and cites sentences; if it claims the place is named, code checks the sentence names it, and if it claims the scene continues, code checks the previous setting matches. Failed claims are downgraded and flagged. Output: `settings/settings.jsonl`.
6. **The map.** `rebind compose` lays the facts out as a survey map, by the rules written into `layout.json` (L1–L10) and shown on the site under "How it was drawn". Chapters run left to right; each place is a band; ground height is the reader's tension score, so one contour is one point of tension; the paper's tint is warmth; the most-mentioned people walk paths through the places they are named in; interactions are knots; letters and carriages are symbols; roads mark scene changes. The viewer (`site/`, three.js) draws only what `layout.json` says. Clicking any mark shows its rule, its fact ids and the cited sentences; clicking bare ground breaks its height into each passage's share, using the same formula that built it.
7. **Audit trail.** `calls.jsonl` stores every model call verbatim. `run.json` records the model, prompt hash, schema and decoding parameters.

**macOS note.** If `uv run rebind` says `No module named 'rebind'`, macOS has marked the virtualenv as hidden and Python skips hidden `.pth` files. Fix with `chflags -R nohidden .venv`.
