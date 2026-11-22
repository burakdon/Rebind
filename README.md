# Rebind

*I don't mind the IPO, but stop ripping books…*

To learn from a book, big AI cuts it into pieces and keeps no note of where each piece came from. Rebind has an AI model that reads a book and hands back a scarf pattern in which every row leads to the sentences it was made from, fully traceable. Project 2 for AIPI 590 (Responsible AI / Explainable AI), Duke.

- **Live site:** https://burakdon.github.io/Rebind/ (the scarves, knitted on screen; click any row to unravel it)
- **Poster:** `site/poster/` draws the 36 × 24 inch poster from the same data files; `poster/` holds the printed PDF
- **Books so far:** A Christmas Carol, Pride and Prejudice, Alice's Adventures in Wonderland (all Project Gutenberg texts)
- **To look without running anything:** open the live site, or `python3 scripts/serve.py` and http://localhost:8737. The finished readings are in `site/data/`, so no model is needed to view them.

## Why a scarf

In June 2025 a court described how Anthropic built the library it trained its AI from. It bought millions of printed books, cut off their bindings, scanned the pages and threw the paper away. The judge ruled that lawful. Millions more books had come from pirate libraries, and for those the company settled with authors for $1.5 billion, approved in July 2026 (*Bartz v. Anthropic*, in the references).

Lawful or not, the picture stayed with me: books taken apart so a machine could learn from them, with nothing left to say which page taught it what. I wanted to try the opposite: let an AI read a book, keep the book whole, and hand back something a person can hold and check row by row.

From 2018 until Covid in 2020 I taught children to knit, so when I looked for a way to keep a book I reached for yarn. The poster carries three photographs from those classes, with the children's faces covered. The covered copies in `site/poster/img/` are the only ones in this repository.

## The question

Explanations of language models are mostly made for one answer on a short input. A model's reading of a whole novel is thousands of small judgements, and a summary, a score or a picture of that reading gives a person nothing they can check.

Rebind asks two things:

1. Can a model's reading of a whole book be shown so that a person can trace everything they see, by rules they could apply by hand, back to the sentences it came from?
2. How steady is that reading when the question is reworded, when every name is swapped, and when a different model reads?

What three books showed:

1. **Yes, by construction.** Every yarn, ridge and eyelet is a count of sentence labels or a checked fact, by seven written rules, and the tests confirm each row is exactly what the rules make of the labels. What cannot be traced is why the model gave a sentence its label.
2. **Only partly steady.** Asked in other words, a sentence keeps its warm, cold or neither label 58 to 68 times in 100, depending on the book. With every name swapped it keeps it 85 to 89 times in 100. A second model gives the same label 65 to 72 times in 100. The scarf shows this instead of hiding it: the rows left undyed run from about a sixth of Pride and Prejudice to over a third of Alice.

It is made for people who read and knit and do not program, and for anyone learning what an explanation of a model can and cannot promise.

## Where it sits

The course topics it draws on are explainable AI, interpretable machine learning, AI evaluation and human-AI interaction. Full references are at the end.

- **Interpretable by design, not explained afterwards.** Rudin (2019) argues for models a person can follow over explanations fitted to a black box afterwards. Rebind cannot make the language model interpretable, so it keeps the model's part as small as it can: one label on one sentence, which a person can judge in seconds. Everything after that is counting.
- **Faithfulness.** Jacovi and Goldberg (2020) separate an explanation that sounds right from one that reflects what actually produced the output. A row's explanation here is faithful to the pipeline because it is the pipeline: the sum on screen is the sum that chose the yarn. It claims nothing about what happens inside the model. Models' own accounts of their reasoning can be unfaithful (Turpin et al., 2023), so Rebind never asks the model why.
- **Pointing at evidence.** Work on rationales has a model show the part of the input its answer rests on (Lei et al., 2016; DeYoung et al., 2020). Rebind has the model cite sentence numbers for who is present, and code refuses any citation that does not hold.
- **Wording.** Sclar et al. (2024) show that changes in a prompt's format with no bearing on meaning move results a great deal, and recommend reporting a spread over plausible prompts instead of one. Rebind reads each book in two wordings and knits the disagreement in as undyed rows.
- **Memory of the book.** Chang et al. (2023) test which books a model has memorised by hiding a name and asking for it, and find that the more a book appears on the web the more of it is memorised. All three books here are everywhere on the web. So the model is never told the title, and one check swaps every name and counts what changes.
- **Emotional arcs.** Reagan et al. (2016) trace feeling through Project Gutenberg fiction with word lists. The scarf's run of cold and warm is that kind of arc, with one difference: each point opens into its sentences and their labels.
- **Data you can hold.** Jansen et al. (2015) define a data physicalization as an object whose shape or material carries the data. Here yarn, texture and holes carry it, and knitting sets the limits on how much can be said.
- **Changing the input and watching the answer.** LIME (Ribeiro et al., 2016) explains one prediction by removing words and seeing what changes. `rebind probe` does the simplest version of that on one passage: each word is left out once and the model asked again. It turned out to measure how firmly a label holds, not why the model gave it (see the checks below), and it says so.
- **How it is evaluated.** The agreement figures use Cohen's kappa (Cohen, 1960). In the terms of Doshi-Velez and Kim (2017) every check here is functionally grounded, meaning no people took part. The two kinds that need people have not been done.
- **Knowing where data came from.** In the spirit of datasheets for datasets (Gebru et al., 2021), each source text is pinned by its hash, every exclusion is logged with its reason, and every prompt and answer is kept.

## What it does

1. A local model (`qwen3:30b` through Ollama, on a laptop) reads the book a passage at a time, without being told which book it is. It labels every sentence warm, cold or neither, and tense or calm, and says who is in the passage, citing the sentence that shows it.
2. Code keeps a claim only if the sentence it cites exists and says so, then counts the labels by seven written rules (K1–K7, section 9 below). Nothing else decides a stitch: there is no score a person could not redo by hand.
3. The count is a knitting pattern: one passage is one pair of rows, with a yarn, a texture and eyelets. On the site every row opens into its instructions, the sum that chose its yarn, how many labels would have to change to change it, and each sentence with its label.

The explanation is the artefact itself, not something added afterwards: the scarf is a count of labels a reader can check, and the site shows the count.

## Design decisions

- **Local, open-weight model.** Nothing leaves the laptop, and every prompt and answer is kept in `out/<book>/runs/<run>/`.
- **Labels a person can check in seconds**, not a 0–10 score. An earlier version used scores; they could not be explained.
- **Read twice.** The model answers the same question in two wordings. Both are counted, and a row is left undyed when the two alone would pick yarns two or more apart, so the scarf shows where the model is unsure.
- **Knitting sets the limits.** One yarn per row, a width a person can hold, a length a person can finish. The book is told at passage level because of that.
- **Each book in its own colours.** At first every scarf ran from blue to red and the three looked alike. Now each book names a palette in `books/<slug>.json`: evergreen to candle gold for A Christmas Carol, violet to marmalade for Alice, blue coat to red coat for Pride and Prejudice. The colours are a choice, not a count. Counting was tried: Pride and Prejudice names a colour about fifteen times in 120,000 words, too few to choose by. In every palette cold is the cool colour, warm the warm one and undyed is cream, and a test checks that no two yarns of a palette can be mistaken for each other with red-green colour blindness (the first blue-to-red palette failed that; green to red, the obvious choice for a Christmas book, fails it too). A visitor can dye any book in any palette from the "Colours" menu, which changes no label, rule or stitch.
- **One yarn, texture only.** Every scarf can also be knitted from a single ball of yarn, for a knitter who has one, or a reader who goes by touch. Nothing is decided again: the class a passage gets from the count (A to E) is knitted as how much of the row is purled, so a cold passage is rough under the hand and a warm one is smooth. Two knit stitches near one edge make a rope that is crossed on a tense passage, and a passage the two readings disagree on is two plain knitted rows, a flat ridge with no pattern in it. The holes for people and chapters stay where they are. It is 41 stitches wide instead of 37. Open it from "One yarn, texture only" on any scarf, or `knit/?book=<slug>&mode=texture`; the printable pattern has a one-yarn version too.
- **One book file, many styles.** `book.json` holds the reading with nothing about how to draw it. The scarf, the weave and the survey map all draw from it.

## Limitations

- **Why a sentence got its label is not explained.** The one attempt, leaving words out one at a time, shows how firmly a label holds and nothing more, and it has been run on a single passage.
- **No person has checked the labels.** The checks say how steady the model is, not whether it is right. `site/knit/check.html` lets anyone label a sample blind.
- **Wording moves the labels.** Asked in other words, the model changes about one feeling label in three. The pooled count absorbs a steady lean, but in roughly a third of rows a single changed label would change the yarn.
- **The cut points and the colours are choices.** The balance is cut into yarns at -0.5, -0.2, 0.2 and 0.5 by hand, and each book's palette was picked by hand.
- **Who is present is undercounted.** A passage that only says "he" or "she" leaves no eyelet, because code cannot check who is meant. Descriptions used as names ("the Ghost") are not told apart.
- **Not yet knitted.** Sizes and yardage come from a typical gauge. No one has test-knitted the pattern, and frequent yarn changes may make it awkward to work.
- **Memory of the text is not ruled out.** Swapping every name moves the labels less than rewording does, so the model is not leaning on the names, but it may still know these famous books.
- **No readers' test yet** against a baseline such as an image model's picture of the same book.

## Who could be misled or harmed

- **People who see or wear the scarf.** A knitted thing looks finished and certain. Off the screen, the undyed rows are the only doubt that survives; a thin margin does not show. The printed pattern names the passage and the count on every row, but a scarf given away loses that.
- **Readers of the books.** Warm and cold are one model's reading, not what the book means. No one has checked how it handles irony, which Austen depends on.
- **Anyone who takes "traceable" for "correct".** Every row has a source, and that says nothing about whether the label on the source is right. The steadiness figures are not accuracy and should not be quoted as accuracy.
- **Authors and publishers.** All three books are out of copyright, and the site publishes the full text of every passage. For a book in copyright that would be republishing it. The reading runs on the laptop, so a person's own copy would stay there, but there is no mode yet that publishes a pattern without the text.
- **People whose own writing is labelled.** The same sentence labelling pointed at letters, essays or messages would be a profile of a person's feelings, made with labels this unsteady. It has only been built and tested on published fiction.
- **Knitters.** The pattern has not been knitted, so yarn and hours could be spent on something that does not work as written.
- **Readers of other languages.** One open-weight model read three English classics. Nothing here says how it reads anything else.

## What comes next

1. **People label a sample.** `site/knit/check.html` is ready. This is the only way to learn whether the labels are right and not just steady.
2. **A readers' test.** Given a scarf and its pattern, can a person find where something happens in the book, and do they do better than with an image model's picture of the same book?
3. **Knit one.** Swatch for the real gauge, then test-knit A Christmas Carol, the shortest that shows an arc.
4. **A closed-book mode** that publishes the pattern and the offsets without the text, so a book in copyright can be read from the owner's copy.
5. **Who "he" is.** Find a way to settle pronouns that code can check, and tell the four ghosts apart.
6. **Harder books.** The second model on the rest of Pride and Prejudice; then a book too new or too obscure for the model to know, and one not in English.
7. **Moving the cut points.** Show how each scarf changes as the four cuts move, so a reader can see how much of the picture is the choice of cuts.
8. **Other things to wear.** The reading is one file with nothing in it about drawing, so a second pattern costs no new reading.

## Run the reading pipeline

Needs Python 3.11+, [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com). The only Python packages are `openai` and `pydantic` (plus `pytest` for the tests); `uv sync` installs them. The three book texts are in `data/raw/`, each pinned by SHA-256 in `books/<slug>.json`.

Models, both open weights, run on an M1 Pro with 32 GB of memory:

```bash
ollama pull qwen3:30b-a3b-instruct-2507-q4_K_M      # the reader, 18 GB
ollama pull olmo-3.1:32b-instruct                   # only for the second-model check, 19 GB
OLLAMA_CONTEXT_LENGTH=8192 ollama serve             # in its own terminal
```

```bash
uv sync
uv run pytest -q                                       # 58 tests, no model needed
scripts/pipeline.sh a-christmas-carol                  # every step for one book, about 1½ hours; or step by step:
uv run rebind segment                                  # passages with source offsets
uv run rebind read --chapters 1-3 --model ollama:qwen3:30b-a3b-instruct-2507-q4_K_M   # cited facts, checked against the text
uv run rebind summary out/pride-and-prejudice/runs/<run>
uv run rebind resolve out/pride-and-prejudice/runs/<run>  # merge names into characters
uv run rebind locate out/pride-and-prejudice/runs/<run>   # where each passage takes place
uv run rebind tokenize out/pride-and-prejudice/runs/<run> # book.json: one record every style draws from (no model)
uv run rebind label out/pride-and-prejudice/runs/<run> --reading a   # then --reading b, then --reading a --swapped
uv run rebind tokenize out/pride-and-prejudice/runs/<run>           # again, to take the labels into book.json
uv run rebind knit                                        # pattern.json: the scarf pattern, from book.json (no model)
uv run rebind label out/pride-and-prejudice/runs/<run> --reading a --model ollama:olmo-3.1:32b-instruct --tag olmo   # a second model's labels
uv run rebind check out/pride-and-prejudice/runs/<run>    # checks.json: stability, memory, other model, hand
uv run rebind probe out/a-christmas-carol/runs/<run> c05.p12   # leave each word of one passage out in turn, about 15 minutes
uv run rebind compose out/pride-and-prejudice/runs/<run>  # layout for the survey-map style
python3 scripts/serve.py                                  # then open http://localhost:8737 (front page; scarves under /knit/, the map under /map/)
uv run rebind trace out/pride-and-prejudice/runs/<run> <fact-id>
```

Another book: add `books/<slug>.json` and its text under `data/raw/`, then `scripts/pipeline.sh <slug>` runs every step in order and the scarf opens at `/knit/?book=<slug>`. By default the first read asks only who is in each passage (`rebind read --only characters`), which is all the scarf needs, and the places step is skipped; `FULL=1 scripts/pipeline.sh <slug>` reads everything, as the map and the weave need, and takes about twice as long. A Christmas Carol (`a-christmas-carol`, 138 passages) is the practice book; its full run took about 2½ hours on an M1 Pro, 1¾ of them the first read. Its scarf runs cold in Stave I, warm in Staves II and III, cold again in Stave IV and warm in Stave V, with 37 of its 138 passages undyed because the two readings are two or more yarns apart (the second wording reads warmer: 65 passages come out one or two yarns warmer, 7 colder). Its checks: asked in different words, a sentence keeps its feeling label 67 times in 100 (kappa 0.48) and its pace label 83 in 100 (kappa 0.66); with every name swapped, 89 in 100 (kappa 0.80) and 93 in 100 (kappa 0.86), so as with Pride and Prejudice the names move the labels less than the wording does. A second model (OLMo 3.1, 32B), asked the first reading's question on all 138 passages, gives a sentence the same feeling label as Qwen 72 times in 100 (kappa 0.54) and the same pace label 71 in 100 (kappa 0.43); a passage gets the same yarn 57 times in 100, the same or a neighbouring yarn 84 in 100 and the same texture 63 in 100. (An evenly spread sample of 35 passages, taken first, had given 73 and 69.) The practice book changed two rules. The ghosts and Scrooge's nephew are never named, so at first they had no column; now a description counts as a person when the book itself uses it as a name at least three times, either written with a capital ("the Ghost") or as a named person's relation ("Scrooge's nephew"). "the Ghost" and "the Spirit" stay two columns, and neither says which of the four ghosts is meant. And no passage of this book has a setting, because the place list is built from places the book names with a capital and it names almost none.

A third book, Alice's Adventures in Wonderland (`alice-in-wonderland`, 131 passages), was run with the default who-only pipeline and no code changes, as a test on a book the rules were not written against. Its first read took 37 minutes. The cast came out as the ten columns a reader would expect (Alice, the Queen, the King, the White Rabbit, the Hatter, the March Hare, the Gryphon, the Mock Turtle, the Dormouse, the Mouse), with one wrong merge that the run itself flagged: "Footman" folded into the White Rabbit on the model's "knowledge of the novel". It is the least steady of the three: asked in other words a sentence keeps its feeling label 58 times in 100 (kappa 0.39) and its pace label 84 in 100 (kappa 0.68); with names swapped, 85 in 100 (kappa 0.76) and 90 in 100 (kappa 0.79). 47 of its 131 passages are undyed and in 74 a single changed label would change the yarn, so its scarf is mostly grey and undyed and shows no arc. A second model (OLMo 3.1, 32B), asked the first reading's question on all 131 passages, gives a sentence the same feeling label as Qwen 68 times in 100 (kappa 0.51) and the same pace label 70 in 100 (kappa 0.42); a passage gets the same yarn 42 times in 100, the same or a neighbouring yarn 78 in 100 and the same texture 57 in 100.

Other models: `--model openai-compat:<model>@<url>` for any OpenAI-compatible server (LM Studio or llama.cpp, for example), with the key in `REBIND_API_KEY`.

## How traceability works

1. **Source.** The book is the Project Gutenberg file, pinned by SHA-256 in `books/<slug>.json`. Every offset in every output points into that exact file.
2. **Passages.** Whole paragraphs grouped into ~350-word passages. Illustration captions and the printer's colophon are excluded, and each exclusion is logged with its reason in `excluded.jsonl`.
3. **Facts.** A reader model sees each passage with its sentences numbered and returns characters, interactions, places, objects, events and tone in four focused calls. Every item cites sentence numbers rather than quoting, so it cannot invent a quotation (asked for free quotes, OLMo 3 7B fabricated about 45% of them). Code, not a model, decides what is accepted:
   - *Found:* the cited sentences must exist in that passage. Each resolves to exact file offsets.
   - *Supports:* for characters, the cited sentences must contain the exact words the passage uses for them (`called_here`), as whole words; for places and objects, they must name the thing. A sentence about Elizabeth Bennet is not evidence for Mrs. Bennet.
   - *Not a pronoun:* a character "called" only "her", "you" or "the others" is refused. Those words are in nearly every sentence, so finding one proves nothing about who is meant. Descriptions such as "her sister" are still checked as words; the entity pass treats them as references, not names.
   - *Repair:* items that fail get one round in which the model is told why and may cite again or withdraw. Both attempts are kept.
   - The checker cannot catch a misreading of a correctly cited sentence (a 7B model said Darcy's "She is tolerable" was about Jane). Only a person can catch that, and no one has checked yet (see Limitations).
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
6. **The book file.** `rebind tokenize` gathers the whole reading into one `site/data/<book>/book.json` with nothing in it about how to draw: places, people, chapters, 314 passages (place, tension, warmth, people, meetings, objects, events, each with fact ids and spans) and 5,836 sentences (offsets, word count, whether it is speech, who and where it names, how many facts cite it). It calls no model and takes about two seconds. Model judgements and code-counted fields are labelled as such in the file's `fields`. A drawing style is a renderer over this file, so a new style costs no reading. The weave (`site/weave/`) and the lightbox study (`site/lightbox/`) draw from it; the survey map still uses its own `layout.json`.
7. **The weave.** `site/weave/` draws the book as cloth, the brief's own idea, from `book.json` alone. Every sentence is one pass of the weft (5,836 passes), cut into lengths at chapter ends. Every verified person is a band of warp threads the whole length of the book, lifted over the weft only on sentences that name them. The weft's colour is the passage's tone (bluer colder, redder warmer, darker more tense; speech glossier than narration). The edge threads are dyed by place and each place has its own ground weave. A gold thread joins people on the sentences the reader cited for a meeting. The seven rules (W1–W7) are in `site/weave/app.js` and shown on the page under "How it was woven". Nothing else is drawn: no scenery, no invented shapes. Clicking a stitch shows its sentence, whose thread it is and whether that sentence names them, why the pass has its colour, where it is set, and every fact that cites the sentence. Open `http://localhost:8737/weave/` after `python3 scripts/serve.py`.
8. **Sentence labels.** `rebind label` asks for nothing a person could not check in a few seconds: for every sentence, is it warm, cold or neither, and is it tense or calm. One call per passage; the model is not told which book it is reading, and the schema has one slot per sentence so every sentence is labelled exactly once. It is run three ways, each kept under `labels/` in the run: `a`, the first reading; `b`, the same question in different words with the choices in the opposite order; and `a --swapped`, reading `a` with every character and place name replaced by a neutral one. First reading of Pride and Prejudice: 2,625 cold, 2,040 warm, 1,171 neither; 2,663 tense, 3,173 calm.
9. **The scarf.** `rebind knit` turns `book.json` into a knitting pattern, `pattern.json`, for a scarf a person can actually knit: cast on 37, 628 rows, about 8 by 90 inches in worsted yarn (sizes and yardage are estimates from a typical gauge, not a measured swatch). Knitting sets the terms, so the book is told at passage level, one pair of rows per passage (K1). Nothing rests on a score. A row's yarn is counted from its sentence labels over both readings together: warm labels minus cold ones, divided by the number of labels, cut into five yarns at -0.5, -0.2, 0.2 and 0.5 (K2). The row back is knitted, leaving a ridge, when at least half the labels are tense (K3). The ten most-mentioned people each own a column (K4; a description such as "the Ghost" counts when the book uses it as a name, see above) and get an eyelet on passages where a verified fact puts them there (K5). An eyelet in the edge marks each chapter (K6). The two readings are also counted apart, and where on their own they would pick yarns two or more apart the row is knitted undyed (K7): 54 of 314 passages. The readings pick the same yarn for 139 passages and neighbouring yarns for 121; in those 121 the row takes the yarn of both together, which always lies between or on the two. An earlier, stricter rule left every disagreement undyed (175 of 314 passages); it was dropped after A Christmas Carol showed the disagreement is mostly a steady lean (the second wording reads warmer) that hid half the book. The cut points are design choices, set to round numbers after looking at how the first reading spreads; they are not learned. The same rows are also written for one yarn (`texture` and each row's `tx` in `pattern.json`): the class as purl stitches, tension as a crossed rope, an unsure passage as a plain ridge; tests check that each one-yarn row keeps 41 stitches, has its holes exactly where the coloured row has them, and is purled as much as its class says. The yarns' names and colours come from the book's palette (`PALETTES` in `src/rebind/knit.py`, copied to `site/data/palettes.json` for the site's "Colours" menu). `site/knit/` shows the pattern knitted on screen stitch by stitch; clicking a row gives its written instructions, each reading's tally, the tally of both together and the sum that picked the yarn, how many labels would have to change to change it, the cited sentences behind each eyelet, and every sentence of the passage with its label. `site/knit/pattern.html` is the printable pattern: materials, the rules, a chart and written instructions, with every row naming its passage and its count. Tests check that every row keeps 37 stitches, that an eyelet exists if and only if the run has the fact for it, and that every yarn and ridge is exactly what the rules make of the labels.
10. **Checks.** `rebind check` counts how far the labels can be trusted and writes `checks.json`, which the site shows under "How sure is it". Stability: asked in different words, a sentence keeps its feeling label 68 times in 100 (Cohen's kappa 0.50) and its pace label 85 in 100 (kappa 0.70); a passage gets the same yarn 44 times in 100 and the same or a neighbouring yarn 83 in 100. Memory: with every name swapped, a sentence keeps its feeling label 85 times in 100 (kappa 0.76) and its pace label 91 in 100 (kappa 0.81), and a passage keeps its yarn 67 times in 100. That is less movement than rewording the question causes, so there is no sign that the reader leans on recognising the names; it cannot rule out that the reader knows the text itself, and it also shows that a change with no bearing on meaning still moves about one feeling label in seven. Other model: OLMo 3.1 (32B), asked the first reading's question on an evenly spread 81 of the 314 passages (it takes about a minute a passage on this Mac), gives a sentence the same feeling label as Qwen 65 times in 100 (kappa 0.46) and the same pace label 76 in 100 (kappa 0.51); a passage gets the same yarn 36 times in 100 and the same or a neighbouring yarn 80 in 100. Two models agreeing would not make either right, and here they agree only moderately. Hand: not done. No one has labelled a sample by hand, so the checks above say how steady the labels are, not whether they are right. The tool is there for anyone who wants to: `site/knit/check.html` gives a person 150 random sentences to label without seeing the reader's answers; save its file as `data/handcheck.json` and `rebind check` reports agreement and kappa against both readings. Word by word: `rebind probe` takes one passage, leaves each word out once and asks the first reading's question again. On the poster's example, the last passage of A Christmas Carol (8 sentences, 213 words), six of the eight labels never changed. "Scrooge was better than his word." went from warm to cold when "Scrooge", "better" or "word" was left out, and the one cold sentence went to neither for 5 of its 81 words: "he", "little", "them", "such" and "these". Asked twice with nothing left out the model gave the same answer, and leaving a word out of one sentence changed another sentence's label only 3 times in 1,491, so the test is clean. But the words that flip the cold sentence are not the ones a reader would point to, so this shows how fragile a label is and not what it rests on. It costs one call per word, a quarter of an hour for this passage, so it has been run on this one passage only; the results are in the run's `probes/` folder and in `site/data/a-christmas-carol/probes.json`, and the row's panel on the site shows them.
11. **The map.** `rebind compose` lays the facts out as a survey map, by the rules written into `layout.json` (L1–L10) and shown on the site under "How it was drawn". Chapters run left to right; each place is a band; ground height is the reader's tension score, so one contour is one point of tension; the paper's tint is warmth; the most-mentioned people walk paths through the places they are named in; interactions are knots; letters and carriages are symbols; roads mark scene changes. The viewer (`site/`, three.js) draws only what `layout.json` says. Clicking any mark shows its rule, its fact ids and the cited sentences; clicking bare ground breaks its height into each passage's share, using the same formula that built it.
12. **Audit trail.** `calls.jsonl` stores every model call verbatim. `run.json` records the model, prompt hash, schema and decoding parameters.

**macOS note.** If `uv run rebind` says `No module named 'rebind'`, macOS has marked the virtualenv as hidden and Python skips hidden `.pth` files. Fix with `chflags -R nohidden .venv`.

## References

- *Bartz v. Anthropic PBC*, No. 3:24-cv-05417 (N.D. Cal.). Order on fair use, June 23, 2025; class settlement given final approval July 20, 2026.
- Chang, K. K., Cramer, M., Soni, S., and Bamman, D. (2023). Speak, Memory: An Archaeology of Books Known to ChatGPT/GPT-4. *EMNLP 2023*, 7312–7327.
- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37–46.
- DeYoung, J., Jain, S., Rajani, N. F., Lehman, E., Xiong, C., Socher, R., and Wallace, B. C. (2020). ERASER: A Benchmark to Evaluate Rationalized NLP Models. *ACL 2020*.
- Doshi-Velez, F., and Kim, B. (2017). Towards A Rigorous Science of Interpretable Machine Learning. arXiv:1702.08608.
- Gebru, T., Morgenstern, J., Vecchione, B., Wortman Vaughan, J., Wallach, H., Daumé III, H., and Crawford, K. (2021). Datasheets for Datasets. *Communications of the ACM*, 64(12), 86–92.
- Jacovi, A., and Goldberg, Y. (2020). Towards Faithfully Interpretable NLP Systems: How Should We Define and Evaluate Faithfulness? *ACL 2020*.
- Jansen, Y., Dragicevic, P., Isenberg, P., Alexander, J., Karnik, A., Kildal, J., Subramanian, S., and Hornbæk, K. (2015). Opportunities and Challenges for Data Physicalization. *CHI 2015*, 3227–3236.
- Lei, T., Barzilay, R., and Jaakkola, T. (2016). Rationalizing Neural Predictions. *EMNLP 2016*.
- Reagan, A. J., Mitchell, L., Kiley, D., Danforth, C. M., and Dodds, P. S. (2016). The emotional arcs of stories are dominated by six basic shapes. *EPJ Data Science*, 5, 31.
- Ribeiro, M. T., Singh, S., and Guestrin, C. (2016). "Why Should I Trust You?": Explaining the Predictions of Any Classifier. *KDD 2016*.
- Rudin, C. (2019). Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead. *Nature Machine Intelligence*, 1, 206–215.
- Sclar, M., Choi, Y., Tsvetkov, Y., and Suhr, A. (2024). Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design. *ICLR 2024*.
- Turpin, M., Michael, J., Perez, E., and Bowman, S. R. (2023). Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting. *NeurIPS 2023*.
