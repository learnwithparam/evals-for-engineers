# Picks candidates

For the page pass. Each part lists 8 to 10 candidates that look like they pass the bar in STANDARD-v2.md section 5. The page pass cuts each list to 4 to 6 picks (at least 2 videos), checks every link is live, and deletes this file. Years are the year of first publication as I know it. No link was opened in this run, so the page pass must confirm each one and the video kind.

Kind key: V is a video or talk, R is a read.

## 01 Find the failures

1. R. Hamel Husain, "Your AI Product Needs Evals", 2024. A practitioner who runs evals for client products; evergreen method of reading traces first.
2. R. Hamel Husain and Shreya Shankar, "Frequently Asked Questions About AI Evals", 2025. The people who teach the error analysis method; a plain Q and A.
3. R. Hamel Husain, "A Field Guide to Rapidly Improving AI Products", 2025. Drawn from many production teams; covers looking at data before building tools.
4. V. Hamel Husain and Shreya Shankar, lightning lessons on error analysis from their AI Evals course, 2025. The method's authors; confirm the free recording is public.
5. R. Shreya Shankar and others, "Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences", 2024. The original paper behind labelling first, then criteria.
6. R. Anthropic, "Demystifying evals for AI agents", 2025. The lab that runs it in production; names reading transcripts as a core habit.
7. V. Anthropic, "Building effective agents" talk at AI Engineer, 2025. First-party talk; shows why you study runs. Confirm the exact title.
8. R. Eugene Yan, "Task-Specific LLM Evals that Do & Don't Work", 2024. Staff engineer who ships these systems; covers choosing the check per failure.
9. R. Barney Glaser and Anselm Strauss, "The Discovery of Grounded Theory", 1967 (book, the origin of open coding). Only if the page pass wants the root idea; it is a book, so check access.

## 02 Check with code

1. R. Hamel Husain, "Your AI Product Needs Evals", 2024. Covers unit-test style assertions before any judge.
2. R. Shreya Shankar and others, "SPADE: Synthesizing Data Quality Assertions for Large Language Model Pipelines", 2024. Research paper on code checks from prompts and failures.
3. R. Anthropic, "Demystifying evals for AI agents", 2025. Explains code graders first, model graders only where code cannot reach.
4. R. Anthropic documentation, "Define success criteria and build evaluations", ongoing. Official docs; code-graded evals are the cheapest.
5. R. UK AI Security Institute, Inspect AI documentation on scorers, 2024. The maintainers; evergreen for match and pattern scorers.
6. R. Hamel Husain, "Using LLM-as-a-Judge: A Complete Guide", 2024 (the section on synthetic data and starting without users). For the synthetic cases step.
7. R. Wang and others, "Self-Instruct: Aligning Language Models with Self-Generated Instructions", 2022. The original paper on model-made data; shows why a person reviews it.
8. R. Hamel Husain, "Generating synthetic data for evals" in the AI Evals FAQ, 2025. The method's author; dimensions first, then tuples, then questions.
9. V. JJ Allaire (Inspect AI author), talk on Inspect for evals, 2024. Confirm the host and that the video is public.

## 03 Judge what code cannot

1. R. Hamel Husain, "Creating a LLM-as-a-Judge That Drives Business Results", 2024. Practitioner guide; pass or fail, critiques, then align.
2. R. Hamel Husain, "Using LLM-as-a-Judge: A Complete Guide", 2024. Detailed method with a runnable flow.
3. R. Shreya Shankar and others, "Who Validates the Validators?", 2024. Shows criteria drift and why you label first.
4. R. Zheng and others, "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", 2023. The original paper naming position, verbosity and self-preference bias.
5. R. Eugene Yan, "Evaluating the Effectiveness of LLM-Evaluators (aka LLM-as-Judge)", 2024. A survey by a practitioner; compares biases and fixes.
6. R. Anthropic, "Demystifying evals for AI agents", 2025. Model graders must be calibrated against human graders.
7. V. Hamel Husain and Shreya Shankar, LLM-as-judge lesson from their AI Evals course, 2025. The authors; confirm the free recording.
8. R. Jacob Cohen, "A Coefficient of Agreement for Nominal Scales", 1960. The original paper for kappa, used in the label step.
9. R. W. J. Rogan and B. Gladen, "Estimating Prevalence from the Results of a Screening Test", 1978. The correction used in the pass-rate step; a paper, so only if the page can explain it simply.
10. R. Evan Miller, "Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations", 2024. Published through Anthropic; covers intervals for small test sets.

## 04 Gate the change

1. R. Anthropic, "Demystifying evals for AI agents", 2025. Defines trials, pass@k and pass^k; the lab that runs it.
2. R. Yao and others, "tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains", 2024. The paper that introduced pass^k.
3. R. Hamel Husain, "Your AI Product Needs Evals", 2024. Evals as part of the release loop.
4. R. GitHub Docs, "Understanding GitHub Actions", ongoing. Official docs for the CI step.
5. R. Evan Miller, "Adding Error Bars to Evals", 2024. Why a small gate needs an interval.
6. R. UK AI Security Institute, Inspect AI documentation on running evals and logs, 2024. Official.
7. R. Mark Chen and others, "Evaluating Large Language Models Trained on Code", 2021. The paper that defined pass@k.
8. R. Martin Fowler, "Continuous Integration", 2006 (updated). A founder of the practice; the idea of a build that fails fast. Check that the version is evergreen.
9. R. Google, "Software Engineering at Google", chapter on testing at scale, 2020. Free online; flaky tests and why they block trust.

## 05 Watch production

1. R. Hamel Husain, "A Field Guide to Rapidly Improving AI Products", 2025. Reading production traces and building from them.
2. R. Shreya Shankar, "Data Flywheels for LLM Applications", 2024. By a researcher who studies these loops.
3. R. Anthropic, "Demystifying evals for AI agents", 2025. Covers capability and regression evals and how evals age.
4. R. Anthropic, "Building effective agents", 2024. Short and first-party; keep the loop simple.
5. R. Google, "Site Reliability Engineering", chapter "Monitoring Distributed Systems", 2016. Free online; alert on symptoms, not causes.
6. R. Langfuse documentation on production monitoring and datasets from traces, ongoing. Maintainers of the tool; check it stays tool-neutral.
7. R. Evan Miller, "Adding Error Bars to Evals", 2024. Intervals on a sampled rate.
8. R. Rogan and Gladen, "Estimating Prevalence from the Results of a Screening Test", 1978. The correction for a judge that is not perfect.
9. V. Hamel Husain and Shreya Shankar, production monitoring lesson from their AI Evals course, 2025. Confirm the free recording.

## 06 Evaluate retrieval and the agent

1. R. Anthropic, "Introducing Contextual Retrieval", 2024. First-party measurement of retrieval failure with recall at k.
2. R. Anthropic, "Demystifying evals for AI agents", 2025. Grade the end state; trials; pass^k.
3. R. Yao and others, "tau-bench", 2024. The method for multi-turn, tool-using agents with a user simulator and pass^k.
4. R. Thakur and others, "BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models", 2021. Source of recall and nDCG practice.
5. R. Liu and others, "Lost in the Middle: How Language Models Use Long Contexts", 2023. Why where the right clause sits matters.
6. R. Jimenez and others, "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?", 2023. Grades by running tests on the end state.
7. R. Zheng and others, "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", 2023. Multi-turn judging in the MT-Bench half.
8. V. Barry Zhang and Erik Schluntz (Anthropic), "Building Effective Agents" talk, 2025. First-party talk; confirm the title.
9. R. Hamel Husain, "Evals for RAG" material in the AI Evals FAQ, 2025. Practitioner view that retrieval is measured apart from the answer.
10. R. Hamel Husain and Shreya Shankar, transition failure matrix in their agent lesson, 2025. The source of the first-failure map; confirm where it is public.

## 07 Score the answers with Inspect AI

1. R. UK AI Security Institute, Inspect AI documentation, 2024. The maintainers; tasks, solvers and scorers.
2. V. JJ Allaire, talk on Inspect, 2024. The author; confirm the host and that the video is public.
3. R. UK AI Security Institute, "inspect_evals" repository README, 2024. Official examples that mirror the port-the-gate shape.
4. R. Anthropic, "Demystifying evals for AI agents", 2025. Where a framework fits and where it does not.
5. R. Hamel Husain, "Your AI Product Needs Evals", 2024. Own your data and tools; do not outsource the looking.
6. R. Hamel Husain and Shreya Shankar, "Frequently Asked Questions About AI Evals", 2025. Covers choosing a framework late.
7. R. Anthropic documentation, "Define success criteria and build evaluations", ongoing. Official.
8. V. Hamel Husain and Shreya Shankar, capstone and own-data lesson from their AI Evals course, 2025. Matches the do-it-on-yours step; confirm the free recording.
9. R. Eugene Yan, "Task-Specific LLM Evals that Do & Don't Work", 2024. Practitioner; ties each check to a real system.
