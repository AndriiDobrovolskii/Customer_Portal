# Runtime Rules — Grep Patterns

Mechanical helpers for Part B of the gate. These narrow the search; they don't replace reading the actual matched lines — a grep hit is a lead, not a verdict.

## ORM containment (router must never import a model or the repository)

```bash
grep -rnE '^\s*(from|import)\s+.*\.(models|repository)\b' app/modules/*/router.py
```
Expect zero output. Any hit is a Fail.

## Cross-module discipline (a service must depend on another module's *service*, never its router)

```bash
grep -rnE 'from app\.modules\.[a-z_]+\.router import' app/modules/*/service.py
```
Expect zero output. Compare against the module's own legitimate cross-module service imports:
```bash
grep -rnE 'from app\.modules\.[a-z_]+\.service import' app/modules/*/service.py
```

## Cache-write TTL presence

```bash
grep -rnE '\.(set|hset|setex|hset\w*)\(' app/modules/*/cache.py
```
For every match, confirm a TTL/`ex=`/`px=` argument (or a dedicated `setex`) accompanies it. No `cache.py` in the diff → report N/A, not a false pass.

## Banned idioms

```bash
grep -rnE '\btyping\.Any\b|:\s*Any\b|->\s*Any\b' app/ --include='*.py'
grep -rn '# type: ignore' app/ --include='*.py'
grep -rnE '\bcast\(' app/ --include='*.py'
grep -rnE '\bos\.(getenv|environ)\b' app/ --include='*.py' | grep -v 'app/core/config.py'
```
Every hit is a finding unless it's the one documented `migrations/env.py` exemption (which is excluded from `app/` anyway) already carved into `pyproject.toml`.

## Eager-loading spot check

No automatic grep substitutes for reading the query — check manually:
1. Find every `relationship(...)` in the touched `models.py` and confirm it declares `lazy="raise_on_sql"`.
2. For each, find the repository method that loads it and confirm the query includes the matching `joinedload()`/`selectinload()`/`contains_eager()` call.
3. Flag any repository method returning that model without the corresponding eager-load option in the same `select()` statement.

## Contract & security spot check (§6.7)

```bash
grep -rnE '@router\.(get|post|put|patch|delete)' app/modules/*/router.py
```
For every match, confirm the same decorator call includes both `response_model=` and `status_code=`.

```bash
grep -rnE 'model_config\s*=\s*ConfigDict\(' app/modules/*/schemas.py
```
For every inbound schema class (`*Create`/`*Update`/`*AdminUpdate`), confirm `extra="forbid"` appears in its `ConfigDict(...)` call.
