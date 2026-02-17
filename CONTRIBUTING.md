# Contributing to context-memory

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

1. Clone the repository:

```bash
git clone https://github.com/ErebusEnigma/context-memory.git
cd context-memory
```

2. Ensure you have Python >= 3.8 with SQLite FTS5 support (included in the standard library).

3. Install development tools:

```bash
pip install ruff pytest
pip install flask flask-cors   # optional, for dashboard development
```

## Verify Schema

```bash
python skills/context-memory/scripts/db_init.py --verify
```

## Code Style

- Line length: 120 characters max
- Linter: [ruff](https://docs.astral.sh/ruff/) with `E`, `F`, `W`, `I` rules
- Target: Python 3.8 compatibility

Run the linter:

```bash
ruff check .
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## Running the Dashboard

```bash
python skills/context-memory/scripts/dashboard.py
```

Opens at [http://127.0.0.1:5111](http://127.0.0.1:5111). The frontend is vanilla JS in `skills/context-memory/scripts/static/` — no build step required.

## Project Structure Notes

- `.claude-plugin/plugin.json` is **not** part of the Anthropic skill spec. It exists for potential future plugin registry use. The canonical metadata lives in `skills/context-memory/SKILL.md` frontmatter.
- The skill spec is defined by Anthropic's [skill guide](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf): `SKILL.md`, `scripts/`, `references/`, `assets/`.

## Making Changes

1. Fork the repository and create a feature branch from `main`.
2. Make your changes and add tests if applicable.
3. Run the test suite and linter to ensure everything passes.
4. Commit with a clear, descriptive message.
5. Open a pull request against `main`.

## Pull Request Process

- Keep PRs focused on a single change.
- Update `CHANGELOG.md` under the `[Unreleased]` section.
- Ensure all CI checks pass.
- A maintainer will review and merge your PR.

## Reporting Bugs

Use the [bug report template](https://github.com/ErebusEnigma/context-memory/issues/new?template=bug_report.md) to file issues.

## Requesting Features

Use the [feature request template](https://github.com/ErebusEnigma/context-memory/issues/new?template=feature_request.md) to suggest ideas.
