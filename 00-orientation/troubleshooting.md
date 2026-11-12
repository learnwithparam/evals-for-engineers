# When something goes wrong

Every message a script prints on failure is in this table. Find the first line of what you see.

## Setup and the world

| What you see | What it means | Fix |
|---|---|---|
| `bun: command not found` | Bun is not installed. | Install it from bun.sh, then open a new terminal. |
| `uv: command not found` | uv is not installed. | Install it from docs.astral.sh/uv, then open a new terminal. |
| `No interpreter found for Python >=3.12` | uv cannot find a new enough Python. | Run `uv python install 3.13`, then `uv sync` again. |
| `There is no step called "..."` | The step name is misspelled. | Copy a name from the list it prints. |
| `There is no part called "..."` | The part name is misspelled. | Copy a name from the list it prints, such as `find-the-failures`. |
| `ERROR the check for ... could not load` | The check itself is broken, not your work. | Open an issue with the full output. |
| `There is no step called ... Try: uv run review mark-the-traces` | `uv run review` needs a step that has traces to review. | Use `mark-the-traces` or `note-the-failures`. |
| `Address already in use` | Another review app is running on that port. | Stop it with Ctrl+C, or add `--port 8766`. |
| `There is no lease ...` | `uv run fernhill demo --lease` was given an id that does not exist. | Use an id from L001 to L130. |
| `Use: uv run world [status|reset|tour|lease <id>|generate]` | `uv run world` was given a word it does not know. | Use one of the words it lists. |
| `FileNotFoundError: ... world/data/...` | The world's data files are missing or moved. | Run `git checkout -- world/data`, then `uv run world reset`. |
| `sqlite3.OperationalError: no such table` | The system of record is from an older version of the repo. | Run `uv run world reset`. |

## Models and keys

| What you see | What it means | Fix |
|---|---|---|
| `No recorded reply for this prompt` | Replay only knows the prompts the finished system sends, and you sent a new one. | Set `LLM_PROVIDER` and one key in `.env` to run it live, or keep the finished system's prompt. |
| `LLM_PROVIDER=... needs ..._API_KEY in .env` | You chose a provider but its key is empty. | Copy `.env.example` to `.env` and fill in that one key. |
| `LLM_PROVIDER=... is not known` | The provider is misspelled. | Use `replay`, `anthropic`, `openrouter`, `openai` or `ollama`. |
| `LLM_PROVIDER=ollama needs OLLAMA_MODEL in .env` | Ollama runs a model you choose. | Set `OLLAMA_MODEL` in `.env` to a model you have pulled. |
| `role(s) failed` from `uv run models` | A live call failed: a wrong key, no credit, or no network. | Read the line above it; check the key and your account, or go back to `LLM_PROVIDER=replay`. |
| `AuthenticationError` | The provider rejected the key. | Make a new key and paste it into `.env` with no spaces or quotes. |

## Check messages

Each `FAIL` line names the rule and the check it belongs to. The fix is the same `Try next:` sentence the check prints.

| What you see | What it means | Fix |
|---|---|---|
| `FAIL  rates.json has n, top_mode and modes` (count-the-failures) | Your work does not meet this rule yet. | Keep the shape of the starter rates.json and fill it in, or write it from count.py. |
| `FAIL  n is the number of reviewed traces in labels.csv` (count-the-failures) | Your work does not meet this rule yet. | Count the rows of labels.csv, not the failed ones. |
| `FAIL  every mode has a count and a rate that match labels.csv` (count-the-failures) | Your work does not meet this rule yet. | Compute the numbers from labels.csv with code: count = the 1s in the column, rate = count / n. |
| `FAIL  top_mode has the highest count` (count-the-failures) | Your work does not meet this rule yet. | Set top_mode to the mode with the most 1s; if two tie, either is right. |
| `FAIL  every mode has a decision: fix the prompt, code check, judge or monitor` (count-the-failures) | Your work does not meet this rule yet. | Pick one of the four decisions for each mode, spelled as shown. |
| `FAIL  rent failures, which have one right answer, go to a code check` (count-the-failures) | Your work does not meet this rule yet. | A rent value has one right answer in the lease; compare it in code, do not pay a judge to read it. |
| `FAIL  marks.csv exists with the columns trace_id and mark` (mark-the-traces) | Your work does not meet this rule yet. | Start the review app with uv run review mark-the-traces, or keep the header line trace_id,mark. |
| `FAIL  every trace in sample.jsonl has one mark, and no other trace has one` (mark-the-traces) | Your work does not meet this rule yet. | Go through all 40 traces in the review app; each trace gets exactly one row. |
| `FAIL  every mark is pass or fail, with no defer left` (mark-the-traces) | Your work does not meet this rule yet. | Come back to the traces you deferred and decide pass or fail on each. |
| `FAIL  every trace with a planted fault is marked fail` (mark-the-traces) | Your work does not meet this rule yet. | Compare rent, rent steps and renewal notice days with the lease text, amendments included. |
| `FAIL  your marks agree with Dana's on at least 32 of the 40 traces` (mark-the-traces) | Your work does not meet this rule yet. | A trace fails when any field differs from the signed lease; check every field, not only rent. |
| `FAIL  report.txt exists in this folder` (meet-fernhill) | Your work does not meet this rule yet. | From the repo root run uv run fernhill report --out 00-orientation/01-meet-fernhill/problem/report.txt. |
| `FAIL  it is the report for the live release` (meet-fernhill) | Your work does not meet this rule yet. | Write the file with uv run fernhill report, not by hand, so the first line is the report title. |
| `FAIL  it has all five report lines` (meet-fernhill) | Your work does not meet this rule yet. | Run the whole report; if a line is missing, read the error above it and see troubleshooting.md. |
| `FAIL  the gate blocks the cheaper model` (meet-fernhill) | Your work does not meet this rule yet. | Run uv run world reset, then write the report again on the default replay provider. |
| `FAIL  its world line matches the world in this repo` (meet-fernhill) | Your work does not meet this rule yet. | The report came from another copy of the world; run uv run world reset and write the report again. |
| `FAIL  failure_modes.yaml lists 4 to 8 modes` (name-the-failure-modes) | Your work does not meet this rule yet. | Group your notes: merge modes that share a cause in the data, split one that hides two behaviours. |
| `FAIL  every mode has a name in lower-case-with-dashes, a definition and at least one example` (name-the-failure-modes) | Your work does not meet this rule yet. | Copy the block shape from the comment at the top of failure_modes.yaml. |
| `FAIL  no mode has a generic name like hallucination, formatting or other` (name-the-failure-modes) | Your work does not meet this rule yet. | Name what happened to which field, for example amended-rent-missed. |
| `FAIL  every definition is one sentence of 25 words or fewer` (name-the-failure-modes) | Your work does not meet this rule yet. | Write each definition so a colleague could apply it to a new trace in one read. |
| `FAIL  every example is a trace you marked fail and wrote a note on` (name-the-failure-modes) | Your work does not meet this rule yet. | Use trace ids from notes.csv as examples. |
| `FAIL  labels.csv has a column per mode and a row per reviewed trace, with 0 or 1 in every cell` (name-the-failure-modes) | Your work does not meet this rule yet. | Give every trace in marks.csv one row, and put 0 or 1 under every mode. |
| `FAIL  every failed trace has at least one mode, and every passed trace has none` (name-the-failure-modes) | Your work does not meet this rule yet. | A failed trace with no mode means a mode is missing; add one or widen a definition. |
| `FAIL  the examples of each mode carry a 1 in that mode's column` (name-the-failure-modes) | Your work does not meet this rule yet. | Label the examples you named in failure_modes.yaml with 1 in labels.csv. |
| `FAIL  one mode covers every amendment failure in the sample` (name-the-failure-modes) | Your work does not meet this rule yet. | The traces where rent misses Amendment No. 1 are one behaviour; give them one mode. |
| `FAIL  notes.csv exists with the columns trace_id and note` (note-the-failures) | Your work does not meet this rule yet. | Keep the header line trace_id,note and add one row per failed trace. |
| `FAIL  every trace marked fail has a note` (note-the-failures) | Your work does not meet this rule yet. | Open uv run review note-the-failures; it shows only the failed traces and saves each note. |
| `FAIL  every note has at least 5 words` (note-the-failures) | Your work does not meet this rule yet. | Say which field is wrong, what the abstract says and what the lease says. |
| `FAIL  no note names a fix or a cause` (note-the-failures) | Your work does not meet this rule yet. | Describe the behaviour, do not diagnose: drop words like should, prompt and fix. |
| `FAIL  each note on a planted fault names the field that went wrong` (note-the-failures) | Your work does not meet this rule yet. | Name the field in the note: rent, the rent step, or the renewal notice days. |
| `FAIL  sample.py exists` (sample-the-traces) | Your work does not meet this rule yet. | Keep sample.py in this problem folder and edit it there. |
| `FAIL  sample.py --seed 7 runs and writes 40 traces` (sample-the-traces) | Your work does not meet this rule yet. | Run uv run python sample.py --seed 7 and read the error; sample() must return a list of 40 traces. |
| `FAIL  every trace id is real and none repeats` (sample-the-traces) | Your work does not meet this rule yet. | Write whole trace lines from world/data/traces/abstractor.jsonl and never pick the same trace twice. |
| `FAIL  at least 8 traces of amended leases` (sample-the-traces) | Your work does not meet this rule yet. | Pick traces where amendments is above 0 first, then fill the rest. |
| `FAIL  at least 3 traces of commercial leases` (sample-the-traces) | Your work does not meet this rule yet. | Add a stratum for lease_type commercial; a random draw often misses the 10 shop leases. |
| `FAIL  the same seed gives the same sample` (sample-the-traces) | Your work does not meet this rule yet. | Make one random.Random(seed) and draw every pick from it, then sort the result by trace_id. |
| `FAIL  a different seed gives a different sample` (sample-the-traces) | Your work does not meet this rule yet. | Draw with the seed you are given; a fixed list of ids is not a sample. |
