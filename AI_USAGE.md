# AI usage

## Tools

- **ChatGPT and Claude (web chat):** consulted before starting, to choose the programming
  language and the tech stack for the requirements.
- **Claude Code (in VS Code):** planning, writing code and tests, code review, and documentation.

## How it was used

- **Planning first:** the architecture and a milestone plan were agreed before any code was
  written; the app was then built one milestone at a time, one commit per feature.
- **Project rules:** `CLAUDE.md` records the architecture, conventions and commands, so the
  assistant followed the same rules in every session.
- **Review agent:** a separate read-only reviewer (`.claude/agents/senior-reviewer.md`) checks
  changes against `CLAUDE.md` and the requirements. It was tested first on planted defects and
  found all of them, plus two real bugs.

## Checking and correcting the output

- Every file was explained, read and reviewed before it was committed.
- Every change was tested: 120+ automated tests, linting, and running the app with demo data.
- Review findings were judged one by one rather than applied automatically. Accepted findings
  fixed real bugs, e.g. non-atomic database migrations and settings that could overwrite edits
  made outside the app.
- The output was corrected when needed, for example:
  - **Removed what wasn't required:** a command-line interface, and extra helper functions.
  - **Rejected an out-of-scope fix:** support for mixed Hebrew/English text.
  - **Simplified the design:** a hard-to-follow Settings screen was redesigned into two simple
    dialogs.
  - **Fixed the workflow:** a commit that included unrelated files was redone.
