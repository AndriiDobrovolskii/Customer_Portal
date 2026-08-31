# Gate Report — <StoryId>

**Date:** <date> · **Branch/commit:** <branch@sha>

## Part A — Mechanical

### 1. `pre-commit run --all-files`
**Result:** Pass / Fail
```
<paste real output>
```

### 2. `mypy app tests`
**Result:** Pass / Fail
```
<paste real output>
```

### 3. `lint-imports`
**Result:** Pass / Fail
```
<paste real output>
```
New `ignore_imports`/`exhaustive=false` since last commit: Yes / No

### 4. `pytest --cov=app --cov-report=term-missing --cov-fail-under=85`
**Result:** Pass / Fail / Not run here — CI is the authority
```
<paste real output>
```

### 5. Migration cycle (`upgrade → downgrade → upgrade`)
**Result:** Pass / Fail / Already captured by migration-manager (see its report)
```
<paste real output>
```

## Part B — Runtime rules (AGENTS.md §6.6)

### 6. ORM containment
**Result:** Pass / Fail — evidence: <file:line or grep output>

### 7. Eager loading
**Result:** Pass / Fail / N/A — evidence: <file:line or grep output>

### 8. Cache TTL
**Result:** Pass / Fail / N/A — no cache writes in this diff — evidence: <file:line or grep output>

### 9. Cross-module discipline
**Result:** Pass / Fail — evidence: <grep output>

### 10. Banned idioms (`Any`, `# type: ignore`, `cast(`, `os.getenv`/`os.environ`)
**Result:** Pass / Fail — evidence: <grep output>

### 11. Contract & security spot-check (§6.7)
**Result:** Pass / Fail — evidence: <file:line notes>

## Verdict

**PASS / FAIL / Local gate green, CI-only checks pending**

<if FAIL: the specific unmet items, no bypass suggested>
