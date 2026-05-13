# ESP-Firmware-Over-The-Air Team Conventions

## Development Tools
- **Python Manager**: `uv`
- **Formatter (Python)**: `black`
- **Formatter (C/Arduino)**: `clang-format`
- **Git Hooks**: `pre-commit`

## Workflows
- Always use `uv run <command>` to ensure the correct environment.
- Commits must follow Conventional Commits.
- Use `pre-commit` to automate formatting and linting.

## Style Guide
- Python: Black (line length 100).
- C/Arduino: Google Style (indent 4).
- Use concise English for comments.
- Avoid numbered lists in comments.
