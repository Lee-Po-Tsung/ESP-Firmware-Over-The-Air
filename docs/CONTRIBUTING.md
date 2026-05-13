# Contributing Guidelines

## Code Style

- **Python**: We use [Black](https://github.com/psf/black) for formatting.
- **C/C++/Arduino**: We use [Clang-Format](https://clang.llvm.org/docs/ClangFormat.html) with a customized Google style.

## Commit Message Convention

Please follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

Example: `feat: add firmware version check`

## Development Setup

1. **Install `uv`**: We use `uv` for Python package management.
2. **Setup Pre-commit**:

   ```bash
   uv run pre-commit install
   uv run pre-commit install --hook-type commit-msg
   ```

   This will automatically format your code and check your commit messages before each commit.

3. **Format manually**:

   ```bash
   uv run black .

   # For C/Arduino files
   clang-format -i esp32/main/*.ino esp32/main/*.h
   ```
