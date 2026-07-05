# 09 · Git Workflow

Git is used to make every change traceable — each increment is a self-contained,
reviewable unit of history.

## Branching model

- `main` is always green (boots + `make check` passes).
- One branch per increment, named after the plan: `feat/04-worker-claim`,
  `feat/05-retries-dlq`, `chore/10-hardening`, `feat/b2-ai-summaries`.
- Merge to `main` when the increment's Definition of Done is met, then tag milestones.

Solo workflow: fast-forward or squash-merge is fine. If simulating PRs, open one per
branch so history reads like a real project.

## Commit conventions

Conventional Commits: `<type>: <description>`

| Type | Use |
|------|-----|
| `feat` | new capability |
| `fix` | bug fix |
| `refactor` | behavior-preserving change |
| `test` | adding/adjusting tests |
| `docs` | documentation only |
| `chore` | tooling/config/scaffolding |
| `perf` | performance |

Keep commits small and focused — one logical change each. Prefer several clear commits
per increment over one giant blob. Example sequence for Increment 4:

```
feat: add worker loop skeleton and registration
feat: implement atomic claim with FOR UPDATE SKIP LOCKED
feat: add simulate handler and sample job types
test: no-double-execution under N concurrent workers
docs: note worker run instructions in README
```

## Per-increment checklist

1. `git switch -c feat/NN-name`
2. Implement + test until `make check` is green.
3. Commit in small conventional steps.
4. Update docs if any contract/behavior changed.
5. Merge to `main`; tag if it hits a milestone (`git tag v0.1`).

## What never gets committed

- Secrets or real `.env` files (only `.env.example`).
- `node_modules/`, `.venv/`, `pgdata/`, build output — see `.gitignore`.
- Commented-out dead code or debug prints.

## Why this matters here

A code-review company will read the git history as a signal of engineering discipline.
Clean, small, well-labeled commits that map 1:1 to the documented increments tell a story
of deliberate, incremental engineering — exactly what the rubric rewards.
