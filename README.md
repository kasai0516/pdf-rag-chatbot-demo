# pdf-rag-chatbot-demo

A small chatbot that answers questions **from your PDFs**, shows the page each answer came from, and is designed to **decline** when the documents don't cover the question — plus an evaluation script so you can check it instead of trusting it.

Runs offline with no API key. Optionally, Claude writes the answers from the retrieved passages.

```
$ python -m ragdemo ask "What is the refund period for annual plans?"
Annual plans can be refunded in full within 14 days of purchase. [northwind_terms.pdf p.1] ...

$ python -m ragdemo ask "Do you offer an on-premise installation?"
I couldn't find this in the documents.
```

## Quick start

```bash
pip install -r requirements.txt
python -m ragdemo eval                # run the 12-question test set
python -m ragdemo serve               # local web chat at http://127.0.0.1:8000
python -m ragdemo --docs path/to/your/pdfs ask "your question"
```

## Evaluation

`samples/questions.yaml` has 9 questions the documents answer (the right page must be retrieved) and 3 they don't (the bot must decline).

```
PASS  What is the refund period for annual plans?  ->  source found
...
PASS  Do you offer an on-premise installation?  ->  declined
PASS  Who is the CEO of Northwind?  ->  declined
PASS  Is there a discount for students?  ->  declined

12/12 passed
```

What this measures: that the passage with the answer is retrieved (top 3) and that unanswerable questions are declined. It does not grade the wording of the answer. For a real project, the question set comes from the client: the questions their team or customers actually ask, including ones the documents should *not* answer — and answer quality is reviewed on those.

## How it works

1. **Index**: wrapped PDF lines are rejoined into sentences; each page is split into short overlapping passages that remember their file and page.
2. **Retrieve**: BM25 keyword search finds the best passages (pure Python, no vector database needed for a demo).
3. **Decide**: if the best passage covers too little of the question, the bot declines instead of guessing. This is a simple keyword rule — good for a demo, not a guarantee.
4. **Answer**:
   - *extractive* (default): quotes the most relevant full sentences with their page, preferring sentences about the subject the question names (so "monthly plans" doesn't get the annual-plan rule first);
   - *Claude* (optional): Claude writes a short answer using only the retrieved passages, cites them, and replies `NOT_IN_DOCUMENTS` when they don't contain the answer.

### Using Claude

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...          # or log in with `ant auth login`
export RAGDEMO_USE_CLAUDE=1
python -m ragdemo ask "When is live chat support available?"
```

The model defaults to `claude-opus-5-5` (override with `RAGDEMO_MODEL`). Sources are listed as `[1] file p.N` under the answer. Note: the automated tests run the offline mode only; Claude mode is not exercised in CI and needs a recent `anthropic` SDK that supports the server-side `fallbacks` parameter.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Scope

This is a deliberately small, readable demo: text-based PDFs, one language, a local chat page. Production versions add embeddings or hybrid search, website embedding, document syncing, access control and hosting. All sample documents are fictional (`tools/make_samples.py`).

## Want this on your own documents?

I offer a fixed-price version on Upwork: you send your PDFs and real questions, and you get a working demo with an evaluation on those questions.
→ [GlobeZenith on Upwork](https://www.upwork.com/freelancers/~01df04fe198316bf24)

MIT License · built by [GlobeZenith OÜ](https://www.globezenith.net/en/)
