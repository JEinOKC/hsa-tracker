# HSA Tracker — Claude Guidelines

## Branch discipline — non-negotiable

**Never commit directly to main.** This means every change — features, bug fixes, one-line dependency updates, build fixes, anything.

Before writing or editing any file:
1. Run `git branch --show-current`
2. If the answer is `main`, run `git checkout -b <type>/<description>` first
3. There is no exception for "it's a small fix"

## Test coverage requirement

**Any bug fix or new feature must include unit tests.** This is non-negotiable.

- When fixing a bug, add a test that would have caught it (regression test).
- When adding a feature, add tests covering the happy path and key error paths.
- Frontend tests live alongside the code in `__tests__/` directories (Vitest + React Testing Library).
- Backend tests live in `backend/tests/`.
- Do not leave test coverage to a follow-up; write tests in the same change.

## Running frontend tests

```bash
PATH="$HOME/.nvm/versions/node/v20.20.1/bin:$PATH" npx vitest run
```

Run a single file:
```bash
PATH="$HOME/.nvm/versions/node/v20.20.1/bin:$PATH" npx vitest run src/pages/__tests__/BankAccounts.test.tsx
```

## Project structure

- `frontend/` — Vite + React + TypeScript
- `backend/` — FastAPI (Python)
- `docker-compose.dev.yml` — local dev stack
