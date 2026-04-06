---
name: general-general-ignore-file-checker
description: Audits .gitignore, .geminiignore, and .copilotignore files for consistency, finds tracked files that should be ignored, and identifies untracked files that are missing from ignore lists. Use when the user asks to "check ignores", "clean up the repository", or when troubleshooting why certain files (like env or pycache) are visible.
---

# Ignore File Checker

## Overview
This skill provides a systematic way to audit repository ignore files (`.gitignore`, `.geminiignore`, and `.copilotignore`). It helps maintain a clean workspace by identifying common configuration errors, such as non-recursive patterns, and flagging files that are accidentally being tracked by Git despite matching ignore rules.

## Quick Start
To perform a comprehensive audit of the project's ignore settings:

1. **Run the Audit Script**: Execute the bundled Python script to scan the root and all submodules.
   ```bash
   python .github/skills/general-ignore-file-checker/scripts/check_ignores.py
   ```

2. **Analyze the Report**:
   - **Tracked but Ignored**: These files are currently in the Git index but match an ignore pattern. They should usually be removed from Git using `git rm --cached <file>`.
   - **Untracked but Not Ignored**: These are new files that haven't been added to any ignore list. Determine if they should be ignored (e.g., local logs, temporary artifacts) or tracked.
   - **Non-Recursive Patterns**: The script flags patterns like `env/` that might miss directories in subfolders. Recommend updating them to `**/env/`.

3. **Apply Fixes**: Based on the report, update the `.gitignore`, `.geminiignore`, or `.copilotignore` files as needed.

## Ignore File Reference

| File | Purpose |
|------|---------|
| `.gitignore` | Prevents files from being tracked by Git |
| `.geminiignore` | Prevents Gemini CLI from reading specific files (same gitignore syntax) |
| `.copilotignore` | Prevents GitHub Copilot from reading specific files (same gitignore syntax). Community convention — documented in [GitHub Community discussions](https://github.com/orgs/community/discussions/188006). Useful for secrets, proprietary algorithms, or any file you don't want Copilot to use as context. |

## Common Fixes

### Removing Tracked Files
If a file is reported as "Tracked but Ignored":
```bash
git rm --cached path/to/file
```

### Updating Non-Recursive Patterns
Ensure common patterns are recursive to cover the entire project tree:
- Change `env/` to `**/env/`
- Change `__pycache__/` to `**/__pycache__/`
- Change `.pytest_cache/` to `**/.pytest_cache/`

## Resources

### scripts/
- **check_ignores.py**: The primary audit tool. It performs the Git checks and pattern analysis recursively across the project and its submodules.

