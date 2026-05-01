# Copilot Prompts Guide

A collection of 9 reusable Copilot prompts for common developer workflows. All prompts are stored in your VS Code roaming profile and available across all projects.

**Location:** `~/.config/Code/User/prompts/` (or equivalent on your OS)

---

## ⚡ Quick Start: Setup

Before using the prompts, ensure all dependencies are installed:

```
/setup-dev-environment
```

This installs:
- Python dev tools (pytest, bandit, pylint, black, mypy, pip-audit)
- Optional system tools (trivy for filesystem scanning)

**One-liner:**
```bash
pip install -e ".[dev]"
```

---

## 0. `/setup-dev-environment` — One-Time Dev Setup

### What It Does
Installs all Python development tools and optional system utilities needed by the other prompts:
- pytest, pytest-cov (testing)
- bandit (security scanning)
- pip-audit (dependency audits)
- pylint (linting)
- black (code formatting)
- mypy (type checking)
- trivy (optional, for filesystem scanning)

### How to Use
```
/setup-dev-environment
```

### When to Run
- ✅ First time setting up the project
- ✅ After cloning a fresh repo
- ✅ When new developers join the team

### Example
```
/setup-dev-environment
```
→ Installs everything. All other prompts will now work without errors.

---

## 1. `/release` — Full Automated Release Workflow

### What It Does
Automates the entire release process in one command:
- ✅ Detects your project type (Python, Node.js, Rust, etc.)
- ✅ Bumps version in the appropriate config file
- ✅ Creates a commit with the version bump
- ✅ Creates an annotated git tag
- ✅ Pushes commits and tags to remote

### How to Use
```
/release 0.11.0 "Add new feature"
/release patch "Bug fixes"
/release minor "New features"
/release major "Breaking changes"
```

### Supported Project Types
- **Python**: `pyproject.toml`, `setup.py`
- **Node.js**: `package.json`
- **Rust**: `Cargo.toml`
- **Any Git project**: Manual version bumping support

### Example
```
/release 1.0.0 "Release v1.0.0 - Production Ready"
```
→ Copilot will automatically bump version, commit, tag, and push everything.

---

## 2. `/run-tests` — Execute Tests with Coverage

### What It Does
Runs your test suite with optional coverage analysis and generates an HTML report showing:
- Test results and pass/fail status
- Line-by-line coverage percentages
- Uncovered code sections
- Coverage trends

### How to Use
```
/run-tests                              # All tests with coverage
/run-tests test_models.py               # Specific test file
/run-tests test_router                  # Tests matching pattern
```

### Key Features
- `-v` flag for verbose output
- `-x` to stop on first failure
- `-k "test_name"` to filter by function names
- HTML report in `coverage_reports/html/index.html`

### Example
```
/run-tests test_router_engine.py
```
→ Runs only router engine tests and generates coverage report.

---

## 3. `/run-security-audit` — Security Scanning

### What It Does
Scans for vulnerabilities across three dimensions:
- **Dependency vulnerabilities** (pip-audit)
- **Code security issues** - SAST analysis (bandit)
- **Filesystem/container threats** (trivy)

### How to Use
```
/run-security-audit                    # All three scans
/run-security-audit pip-audit          # Dependencies only
/run-security-audit bandit             # Code security only
/run-security-audit trivy              # Filesystem scan only
```

### Output
- JSON and HTML reports in `security_reports/`
- Severity ratings (critical, high, medium, low)
- Auto-fix suggestions for dependencies

### Example
```
/run-security-audit all
```
→ Runs pip-audit, bandit, and trivy. Shows vulnerabilities and remediation steps.

---

## 4. `/generate-release-notes` — Create Changelogs

### What It Does
Automatically generates release notes from git commit history:
- Extracts commits since last tag
- Organizes by type (features, fixes, chores, docs)
- Supports multiple output formats
- Can compare between specific tags

### How to Use
```
/generate-release-notes                 # Since last tag
/generate-release-notes v1.0.0          # Since specific tag
```

### Output Formats
- **Markdown** (human-readable, for GitHub releases)
- **JSON** (for automation and tooling)

### Example
```
/generate-release-notes
```
→ Creates `RELEASE_NOTES.md` with all commits formatted as:
```markdown
### Features
- Add LiteLLM support (abc123)

### Fixes
- Fix routing timeout issue (def456)

### Chores
- Update dependencies (ghi789)
```

---

## 5. `/quick-code-review` — Self-Review Changes Before Commit

### What It Does
Scans uncommitted changes for common issues:
- ✅ Type hints and docstrings coverage
- ✅ Security issues (bandit scan)
- ✅ Code style violations (PEP8)
- ✅ Test coverage gaps
- ✅ Potential bugs and anti-patterns

### How to Use
```
/quick-code-review                      # Review all unstaged changes
/quick-code-review staged               # Review staged changes only
```

### Checks Performed
1. Type checking (mypy)
2. Code formatting (black)
3. Security scanning (bandit)
4. Linting (pylint)

### Example
```
/quick-code-review
```
→ Before committing, Copilot checks your changes and catches issues early (saves CI time!)

---

## 6. `/show-coverage-report` — Test Coverage Analysis

### What It Does
Opens and summarizes test coverage:
- Shows overall coverage percentage
- Identifies missing coverage gaps
- Opens interactive HTML dashboard
- Calculates coverage delta vs. previous commit

### How to Use
```
/show-coverage-report                   # Open HTML report
```

### Output
- Terminal summary with line numbers of uncovered code
- HTML dashboard in `coverage_reports/html/index.html`
- Coverage by module/function

### Example
```
/show-coverage-report
```
→ Shows coverage percentage and opens browser to see exactly which lines aren't tested.

---

## 7. `/view-git-log` — Commit History Search

### What It Does
Search and visualize git commit history with filtering:
- View recent commits
- Filter by author
- Search commit messages
- Show file change history
- Team standup summaries

### How to Use
```
/view-git-log                           # Last 20 commits
/view-git-log my-name                   # Commits by author
/view-git-log "fix: bug"                # Search message
/view-git-log src/router.py             # Changes to file
```

### Output Formats
- Pretty graph visualization
- With timestamps
- Full diff details
- Statistics (insertions/deletions)

### Example
```
/view-git-log
```
→ Shows recent commits in graph format with authors and timestamps.

```
/view-git-log "my-name"
```
→ Shows all your commits since yesterday (great for standup!)

---

## 8. `/create-feature-branch` — Git Flow Branch Creation

### What It Does
Creates and checks out a new branch following Git Flow conventions:
- Enforces naming conventions (feature/, fix/, hotfix/, etc.)
- Prevents typos in branch names
- Documents branch purpose

### How to Use
```
/create-feature-branch add-litellm-support
/create-feature-branch fix-timeout-issue feature
/create-feature-branch urgent-hotfix hotfix
```

### Branch Types
- **feature/** — New features
- **fix/** — Bug fixes
- **hotfix/** — Urgent production fixes
- **docs/** — Documentation updates
- **chore/** — Maintenance and refactoring

### Naming Conventions
✅ **Good:**
- `feature/add-litellm-support`
- `fix/routing-engine-timeout`
- `docs/update-readme`
- `chore/upgrade-dependencies`

❌ **Avoid:**
- `feature/wip` (too vague)
- `feature/JIRA-123-very-long-description-here` (too long)

### Example
```
/create-feature-branch add-new-routing-rule
```
→ Creates and switches to `feature/add-new-routing-rule` branch.

---

## Quick Reference Table

| Prompt | Use Case | Time Saved |
|--------|----------|-----------|
| `/setup-dev-environment` | Install all dev tools (run once) | 10 min setup |
| `/release` | Bump version, tag, push | 5 min/week |
| `/run-tests` | Verify quality before commit | 2 min/day |
| `/run-security-audit` | Find vulnerabilities early | 3 min/week |
| `/generate-release-notes` | Document releases | 10 min/release |
| `/quick-code-review` | Catch issues before CI | 5 min/commit |
| `/show-coverage-report` | Identify gaps | 2 min/day |
| `/view-git-log` | Track progress | 1 min/day |
| `/create-feature-branch` | Consistent naming | 1 min/feature |

---

## Tips & Tricks

### 1. Combine Prompts for Full Workflow
```
/create-feature-branch add-feature
# ... make changes ...
/quick-code-review
/run-tests
/generate-release-notes
/release 0.11.0 "Add feature"
```

### 2. Pre-commit Hook Alternative
Use `/quick-code-review` before every commit to catch issues without needing git hooks.

### 3. Daily Standup
```
/view-git-log "Your Name"
```
Shows everything you've done since yesterday!

### 4. Release Checklist
```
/run-security-audit
/run-tests
/show-coverage-report
/release 1.0.0 "Production Release"
```

### 5. Coverage Goals
Most projects aim for:
- 80%+ overall coverage
- 100% for critical paths (routing, security)
- Alert if coverage drops

---

## Accessing Prompts

### In VS Code
1. Open Copilot Chat (Ctrl+Shift+I or Cmd+Shift+I)
2. Type `/` to see available prompts
3. Select the prompt you need
4. Provide parameters
5. Copilot executes automatically

### Available Across
- All your projects
- All your workspaces
- All your machines (syncs with VS Code settings)

---

## Troubleshooting

**Prompt not showing up?**
- Reload VS Code (Ctrl+Shift+P → Developer: Reload Window)
- Check prompts folder: `~/.config/Code/User/prompts/`

**Command fails in Copilot Chat?**
- Run manually in terminal for detailed error messages
- Check that you're in the right directory
- Verify dependencies are installed

**Need project-specific prompts?**
- Create `.github/prompts/` in your repo
- Add `*.prompt.md` files there
- Copilot auto-discovers them

---

## Creating Your Own Prompts

Want to extend these? Create a new file in `~/.config/Code/User/prompts/my-custom.prompt.md`:

```yaml
---
name: My Custom Workflow
description: Description of what it does
parameters:
  - id: param1
    type: string
    description: Parameter description
    required: true
---

# My Custom Workflow

Instructions here...
```

Reload VS Code and use `/my-custom`!

