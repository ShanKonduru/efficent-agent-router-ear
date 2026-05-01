# EAR Release Playbook

This document standardizes how EAR releases are prepared, validated, and published.

## Scope

This playbook covers:

- Versioning and tag discipline
- Preflight validation before release publish
- Release execution and rollback safety
- Troubleshooting common PyPI/TestPyPI failures

## Release Model

- Source of truth for version: `pyproject.toml` -> `[project].version`
- Allowed release tag formats: `X.Y.Z` and `vX.Y.Z`
- Production publish target: PyPI project `efficient-agent-router-ear`
- Test publish target: TestPyPI project `efficient-agent-router-ear`

## Prerequisites

Before cutting a release, confirm all of the following:

1. GitHub repository name matches trusted publisher config exactly.
2. `publish-pypi.yml` has `id-token: write` and `environment: pypi`.
3. `publish-testpypi.yml` has `id-token: write` and OIDC publish step enabled.
4. PyPI trusted publisher is configured for:
   - owner: `ShanKonduru`
   - repository: `efficient-agent-router-ear`
   - workflow: `publish-pypi.yml`
   - environment: `pypi` (or `Any`)
5. TestPyPI trusted publisher is configured for:
   - owner: `ShanKonduru`
   - repository: `efficient-agent-router-ear`
   - workflow: `publish-testpypi.yml`
   - environment: `testpypi` (or `Any`)

## Release Checklist

### Phase 1 - Prepare

1. Update `pyproject.toml` version.
2. Ensure working tree is clean:
   - `git status --short`
3. Run tests and strict coverage gate:
   - `python -m pytest tests/ --cov=ear --cov-branch --cov-report=term-missing --cov-fail-under=100 -v`
4. Validate dependency/security checks:
   - pip-audit workflow is green
   - trivy workflow is green

### Phase 2 - Preflight

1. Run `Release Preflight` workflow manually (workflow_dispatch) or rely on tag-triggered run.
2. Confirm all preflight checks pass:
   - tag format check
   - version-tag alignment
   - workflow OIDC/environment sanity
   - repository naming assumptions

### Phase 3 - Publish

1. Commit version bump:
   - `git add pyproject.toml`
   - `git commit -m "chore(release): bump version to X.Y.Z"`
2. Push branch:
   - `git push origin master`
3. Create and push release tag:
   - `git tag -a X.Y.Z -m "Release X.Y.Z"`
   - `git push origin X.Y.Z`
4. Verify GitHub actions:
   - `Publish - TestPyPI (Check-in)`
   - `Publish - PyPI (Production Release)`

### Phase 4 - Validate

1. Verify package on TestPyPI:
   - `https://test.pypi.org/project/efficient-agent-router-ear/`
2. Verify package on PyPI:
   - `https://pypi.org/project/efficient-agent-router-ear/`
3. Verify install path:
   - `pip install efficient-agent-router-ear==X.Y.Z`
4. Verify release page has artifacts attached.

## Troubleshooting Guide

### Error: invalid-publisher

Symptom:

- OIDC exchange fails with `invalid-publisher`.

Checks:

1. Repository name typo mismatch between GitHub and trusted publisher.
2. Workflow filename mismatch.
3. Environment mismatch (`pypi` vs `Any` vs other).
4. Running from unexpected ref.

Fix:

- Update trusted publisher configuration to exact claim values shown in logs.

### Error: no corresponding publisher

Symptom:

- Token valid but publisher not found.

Fix:

1. Confirm project pending/active publisher exists on PyPI/TestPyPI.
2. Ensure repo/workflow/environment match exactly.
3. Re-run workflow after config update.

### Error: publish appears green but package missing

Symptom:

- Workflow succeeds but package not visible on index.

Root causes:

1. Publish step skipped due to condition.
2. Dry run enabled.
3. Wrong index targeted.

Fix:

1. Verify publish step says `executed` and not `skipped`.
2. Check `dry_run` input for manual run.
3. Confirm `repository-url` for TestPyPI workflow.

### Error: version mismatch

Symptom:

- Tag check fails in verify job.

Fix:

1. Ensure `pyproject.toml` version equals tag normalized value.
2. For `vX.Y.Z` tags, normalized value is `X.Y.Z`.

## Release Governance

- Never bypass test/coverage gate for production release.
- Never publish from dirty working tree.
- Keep release tags immutable once pushed.
- Keep trusted publishing preferred over long-lived API tokens.

## Recommended Versioning Cadence

- Patch (`X.Y.Z+1`) for CI/workflow/hotfix updates.
- Minor (`X.Y+1.0`) for new user-facing behavior.
- Major (`X+1.0.0`) for breaking changes.

## Operational Notes

- If repository is renamed, update:
  - local `origin` URL
  - trusted publisher repository setting on both PyPI and TestPyPI
- Keep this document updated whenever publish pipeline logic changes.
