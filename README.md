# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-20870c35` (track: `academic-slides`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable pipeline and all supporting documents. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `academic-talk-organizer`
- Summary: Use when a research talk must be organized for a specific audience, goal and time budget, with one claim per slide, evidence strength and prepared Q&A.

## Contents

| File |
|------|
| `SKILL.md` |
| `docs/DECK_WORKFLOW.md` |
| `docs/ERROR_HANDLING.md` |
| `examples/demo-case/case.json` |
| `rules/rules_deck.md` |
| `schema/deck_ir.schema.json` |
| `scripts/artifacts.py` |
| `scripts/deckkit.py` |
| `scripts/pptxgen.py` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/sk_entry.py --input /input --work /app/work --out /app/output
```

A single deterministic pass reads `/input`, computes the deliverable and writes a
contract-complete `/app/output/result.json` plus the human-readable review files
described in `SKILL.md`. The same input always produces byte-identical output; no
network access is used, and fields the materials cannot support are reported
explicitly instead of being left empty.

## Notes

- Pure Python standard library; no network access required.
- Every claim is anchored to paragraph-level evidence; unknown items are reported
  in `uncertainty` instead of being fabricated.
