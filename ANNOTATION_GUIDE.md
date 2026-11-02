# LMP Annotation Guide (English + Hindi)

Adapted from the JUDGEBERT / FrJUDGE procedure (Beauchemin et al., EMNLP 2025, Sec. 3.2.3).

**Definition.** *Legal meaning* measures how well the simplified text conveys the legal details and
exceptions of the original and does not misrepresent the law.

Each annotator rates every pair independently and does not see which system produced the simplification.
Annotators work on their own native language (English pairs by English-proficient annotators,
Hindi pairs by native Hindi speakers). Spend at most ~5 minutes per pair. Do 15 practice pairs first,
discuss disagreements as a team, then annotate the real set (practice pairs are discarded).

## Step 1 - choose the bracket

| Score | Bracket | Meaning |
|---|---|---|
| 7-10 | Accurate | Legal details and exceptions are conveyed; the law is not misrepresented. |
| 2-6 | Seems imprecise | Some legal details/exceptions are lost or the law is slightly misrepresented. |
| 1 | Off-track | Clearly wrong; misrepresents the law. |

## Step 2 - deduct one point per legal error, starting from the top of the bracket

Start at 10 (Accurate) or 6 (Imprecise), subtract 1 for every error found, never below 1.

## Step 3 - record the error types (column `errors`, separated by `;`)

| Label | Use when |
|---|---|
| `omission` | an essential fact of the original is missing |
| `hallucination` | a fact is added that is not in the original |
| `contradiction` | the simplification says the opposite (e.g. negation lost) |
| `obligation_permission` | *shall/must* vs *may/can* changed (करना होगा vs कर सकता है) |
| `condition` | a condition (*if / in the event of* / यदि) dropped or changed |
| `exception` | an exception or proviso (*unless / provided that* / सिवाय / बशर्ते) dropped or changed |
| `scope` | *any/all/every/only*, *vehicle -> car*, *premises -> house* ... widened or narrowed |
| `number_date` | amount, time limit, percentage or date changed |
| `entity` | parties or roles changed/swapped (insurer <-> insured, landlord <-> tenant) |

Leave `errors` empty when there is no error. Use `notes` for anything unclear.

## Context sub-study (Experiment 3)

For ~60 pairs, rate twice: first sentence-only, later (after a gap) with the `context` column visible.
Record the second rating in `annotator_k_ctx` columns. Report whether context changes scores or agreement.

## Quality

Report Krippendorff's alpha (interval) - `lmp.data.load_annotated_csv` prints it. The paper's alpha
for LMP was only 0.10; a clear rubric plus an adjudication meeting for pairs whose ratings differ by
4+ points should give you a much better value.
