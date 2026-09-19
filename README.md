# OrderReady

**Chatathon 2026 — Track 01, Misneach.**

Turns a messy customer inquiry into a checked intake ticket, without inventing a single detail the customer didn't give.

---

## The founder and the bottleneck

**Founder:** Maya, sole operator of a one-person custom T-shirt printing shop. She prints, packs, invoices, and answers every inquiry herself.

**Bottleneck:** Orders arrive as Instagram DMs, texts, and emails — almost never with the details needed to quote. "We need about 40 shirts, mostly mediums, by the 15th" is a typical message. Maya's first reply is always the same set of questions, and the job stalls until the customer answers. A printer quoting without quantity, size split, and a firm date is guessing.

OrderReady is the hire that reads the message and tells her exactly what's missing.

---

## What it does

```
paste inquiry → extract only what's stated (with the words it came from)
              → surface every gap as a question
              → Maya corrects or confirms
              → totals and dates revalidated
              → export intake ticket
```

**Collected from the customer:** name, contact (email or phone), S/M/L quantities, deadline, and any total the customer stated.

**Configured by the shop, never extracted:** garment, print location, lead time. These are constants at the top of `order_logic.py`. They are explicitly configured values — the app does not infer them from an inquiry.

---

## The hard part

**The model is never trusted to be right — only to point at where it got something.**

Every extracted value must carry an exact substring from the inquiry as evidence. Code then checks that the substring actually appears in the source text and drops any value that fails. A confident hallucination can't survive the check, because it has nothing to cite.

That's why the app asks instead of guessing:

| Inquiry says | System does |
|---|---|
| "mostly mediums" | No size split. Asks for the breakdown. |
| "about 40 shirts" | No count. Asks for the exact number. |
| "by the 15th" | No deadline. Asks which month. |
| "September 28" | No year. Asks. **Never infers the year from today's date.** |

A model response is a proposal, not a verdict on completeness. Omitted values stay unresolved; they never quietly become defaults.

**Silently changing "five large" to "ten large" to make the arithmetic work is a failure, not a fix.** When the numbers disagree, both are preserved and shown, and a human decides.

Every rule that decides anything is deterministic Python in `order_logic.py`:

- All required fields must be present before export unlocks.
- Size counts must reconcile with any total the customer stated.
- Deadlines must parse to a real date outside the configured lead time.
- Every founder edit revalidates the whole ticket before completion is possible again.

---

## Run it

```bash
pip install streamlit
export ANTHROPIC_API_KEY=your-key
streamlit run app.py
```

Paste any case from `fixtures.py`, or your own text.

If the API times out, fails auth, or returns invalid JSON, the app shows **"Live AI unavailable — manual intake mode"** and keeps working: Maya types the fields and the same validation and export run. That mode is labelled as manual and is not live AI. No stored or replayed model response is ever presented as a live one.

---

## Demo

Both inquiries are synthetic.

**Normal case**

> "Thirty shirts. Ten small, ten medium, ten large. Needed 2026-10-28. — Priya, priya@example.com"

Extraction proposes each field beside the words it came from. Sizes sum to 30, matching the stated total; the deadline is a real date outside the lead time; nothing is missing. Export unlocks.

**Contradiction case**

> "Thirty shirts. Ten small, ten medium, five large. Needed September 28."

Three separate failures caught at once:
- Stated total is 30; sizes sum to 25. Both numbers are shown, export is blocked, and the app does not pick one.
- "September 28" has no year, so the deadline stays unresolved.
- No contact was given, so it's listed as missing.

Maya resolves them — confirms 25, supplies the year, adds her customer's email — and validation runs again before export becomes available.

---

## What's real and what's simulated

**Real:** the model call, the evidence gate, all validation, the ticket export, the acceptance cases.

**Simulated:** the customers, the inquiries, the shop. Every name, email, and order in this repo is fictional.

**Not claimed:** no integration with any shop-management system exists. A working local export does not establish a production workflow, and an intake ticket is not a quote, a confirmed order, or a promise the deadline can be met.

---

## Results

- **Passed 8/8 synthetic workflow cases**, across 3 consecutive live runs (`claude-sonnet-5`, no caching, no retries). Four must extract and export, two must ask rather than guess, two must block export. A case passes only when the app accepts, blocks, or asks as expected *without inventing a missing detail*.
- **16 unit tests on the evidence gate, all passing.**
- **Intake timing, measured today across four sample inquiries:** ~100 seconds filling the ticket by hand, ~20 seconds through OrderReady including answering the gap questions.

These are acceptance tests and a timed comparison on synthetic inquiries. They are not accuracy figures, and we don't extrapolate them to weekly or annual savings. We have no measured evidence of extraction accuracy in the wild, revenue impact, user validation, or market uniqueness.

---

## Limits

- Extraction quality depends on the model, and a message can be ambiguous even when it looks complete. Human review is required on every ticket by design.
- One garment, three sizes, one print location. Colour, pricing, artwork review, inventory, payments, messaging integrations, and production management are all out of scope — not deferred features we're claiming.
- The evidence gate stops fabricated values. It cannot tell whether a correctly quoted value is what the customer actually meant.
- Inquiry text is sent to the model provider for extraction. The app itself has no database and stores nothing between sessions. We make no verified claims about provider retention — use synthetic inquiries.

---

## Prior art

Form builders already solve part of this. Jotform ships a screen-printing request template aimed squarely at reducing missing details, and it works well for shops whose customers fill in forms.

OrderReady starts one step earlier. Maya's inquiries arrive as DMs and texts, and a solo shop can't require a form without losing the job. We work from the message she already received. We don't claim a form product couldn't build this.

---

## Files

| File | Owner | Contains |
|---|---|---|
| `model.py` | Dev | Extraction prompt, JSON parsing, evidence gate, failure handling |
| `fixtures.py` | Dev | Acceptance cases with expected outcomes |
| `order_logic.py` | Devansh | Shop constants, validation rules, ticket rendering. No model calls. |
| `app.py` | Devansh | Streamlit UI — paste box, field panel with evidence, gap questions, export |

The two halves are independent by design. `order_logic.py` imports nothing from `model.py` and makes no network calls, so it can be built and tested against a hand-written dict while the model adapter is still being wired up. Neither owner waits on the other.

## Team and contributions

Northeastern undergraduates.

| | |
|---|---|
| **Dev Luharuwalla** | Extraction and the evidence gate (`model.py`), acceptance fixtures and the timed intake comparison (`fixtures.py`), repository freeze and submission |
| **Devansh** | Validation rules and ticket rendering (`order_logic.py`), review interface and export flow (`app.py`) |

Both: interface freeze at the start, integration, demo rehearsal.