# Contributing

Small, focused pull requests are welcome. Python 3.10 or newer.

## Fork and branch

- Fork [stefanopineda/gpu-stack-thermal-sim](https://github.com/stefanopineda/gpu-stack-thermal-sim) and clone your fork.
- Branch from `main`. One change per branch.
- A missing case or card is often an issue first: include the maker's spec page.

## Code

Match the code around your edit. The repo has no formatter, linter, or style config.

- Preset numbers need a `source`, or `approximate: true` plus an `assumption`. A bare number is rejected. See [docs/MODEL.md](docs/MODEL.md) (“How to extend”).
- If you change a request model or route, regenerate the checked-in schemas: `uv run gpusim schema`.

## Tests

CI (`.github/workflows/ci.yml`) installs the dev extra and runs pytest. Locally:

```bash
uv sync --extra dev
uv run pytest -q
```

[docs/MODEL.md](docs/MODEL.md) also documents `uv venv` then `uv pip install -e ".[dev]"`. CI uses Python 3.12.

## Pull requests

- Title: short, and say what the change does.
- Description: what changed and why. Link an issue with `Fixes #123` when there is one.
- Keep the diff to that one change. Update docs when behavior or usage changes.

Reviewers look for a green `uv run pytest -q` run, cited preset numbers, a description that matches the diff, and docs or schemas updated when those changed.

## License

This project is [MIT licensed](LICENSE). Contributions are under that license. There is no separate contributor license agreement.
