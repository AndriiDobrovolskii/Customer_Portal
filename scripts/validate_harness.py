"""Validate the delivery harness for internal consistency.

Checks that the canonical workflow files, the artifact registry, and the stage
skills all agree. Run it after touching anything under ``docs/workflow/`` or
``.claude/skills/``::

    python scripts/validate_harness.py

Exits non-zero and prints one line per problem. ``docs/workflow/history.jsonl``
is the single exclusion from the retired-identifier scan: history is
append-only and is never rewritten.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "docs" / "workflow"
SKILLS = ROOT / ".claude" / "skills"
COMMANDS = ROOT / ".claude" / "commands"

SCANNED_DIRS = (
    "docs",
    ".claude/skills",
    ".claude/commands",
    "app",
    "tests",
    "migrations",
    "scripts",
)
SCANNED_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".json"}

# These deliberately record the retired vocabulary so history stays traceable.
CANONICAL_EXCLUDE = {
    "docs/workflow/artifact-paths.yaml",
    "docs/workflow/artifact-schema.md",
    "docs/workflow/artifact-lifecycle.md",
    "docs/workflow/state-schema.md",
    "docs/workflow/stage-map.yaml",
    "docs/workflow/stages.md",
    "docs/catalog/stories.yaml",
    "docs/knowledge/project-state.md",
    "scripts/validate_harness.py",
}

# These teach the migration by quoting a retired id as a rejected example.
RETIRED_ID_DOC_ALLOWLIST = {
    ".claude/skills/story-orchestrator/references/start-flow.md",
    ".claude/commands/so/start.md",
}

SEQ_ID = re.compile(r"US-0\d\d")
DOC_PATH = re.compile(r"docs/[A-Za-z0-9_./-]+\.(?:md|yaml|yml|jsonl)")

# Retired path shapes, as they appear with a placeholder rather than a real
# story id - the DOC_PATH resolution check cannot see these because a
# placeholder path never resolves either way.
RETIRED_PATH_STEMS = (
    "-verification-report.md",
    "-reconciliation-report.md",
    "-traceability-matrix.md",
    "-pr-description.md",
    "docs/security/",
    "docs/reviews/specifications/US-0",
)


def load(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise SystemExit(f"{path} did not parse to a mapping")
    return data


def scanned_files() -> list[Path]:
    out: list[Path] = []
    for rel in SCANNED_DIRS:
        base = ROOT / rel
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            posix = p.relative_to(ROOT).as_posix()
            # Skill eval fixtures reference synthetic stories and paths on
            # purpose; they are inputs to a benchmark, not repository content.
            if (
                "__pycache__" in posix
                or "story-spec-writer-workspace" in posix
                or "/evals/" in posix
            ):
                continue
            out.append(p)
    return out


def _is_live_harness(posix: str) -> bool:
    """True for files that drive future runs, as opposed to delivered history."""
    return (
        posix.startswith(
            (".claude/", "docs/workflow/", "app/", "tests/", "migrations/", "scripts/")
        )
        or posix == "docs/catalog/stories.yaml"
    )


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def check_stage_map(errors: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    stage_map = load(WORKFLOW / "stage-map.yaml")
    registry = load(WORKFLOW / "artifact-paths.yaml")

    order: list[str] = stage_map["stage_order"]
    stages: dict[str, Any] = stage_map["stages"]
    keys = set(registry["artifacts"])

    for stage in order:
        if stage not in stages:
            errors.append(f"stage_order lists {stage} but stages has no definition")
    for name, st in stages.items():
        if name not in order:
            errors.append(f"stages defines {name}, absent from stage_order")
        for field in ("inputs", "outputs", "produces"):
            for key in st.get(field) or []:
                if key not in keys:
                    errors.append(f"{name}.{field}: {key} is not a registry key")
        for field in ("next", "on_approve", "on_reject"):
            target = st.get(field)
            if target and target not in order:
                errors.append(f"{name}.{field} -> {target} is not a stage")
        for key, target in (st.get("loop_back") or {}).items():
            if target not in order:
                errors.append(f"{name}.loop_back.{key} -> {target} is not a stage")

    # Every automated stage's skill must exist on disk.
    for name, st in stages.items():
        named = list(st.get("skills") or [])
        if st.get("skill"):
            named.append(st["skill"])
        for skill in named:
            if not (SKILLS / skill / "SKILL.md").is_file():
                errors.append(f"{name}: skill '{skill}' has no .claude/skills/{skill}/SKILL.md")

    # Exactly one owner per artifact type, and every owner is a real skill.
    for key, spec in registry["artifacts"].items():
        owner = spec.get("owner")
        if not owner:
            errors.append(f"artifact '{key}' has no owner")
        elif not (SKILLS / owner / "SKILL.md").is_file():
            errors.append(f"artifact '{key}' owner '{owner}' is not a skill")

    return stage_map, registry


def check_skill_contracts(stage_map: dict[str, Any], errors: list[str]) -> None:
    order = set(stage_map["stage_order"])
    stages: dict[str, Any] = stage_map["stages"]

    stage_of: dict[str, str] = {}
    for name, st in stages.items():
        if st.get("skill"):
            stage_of[st["skill"]] = name

    # Skills that own an artifact but are not any stage's `skill` (notably
    # story-orchestrator) would otherwise never be opened by this check.
    registry = load(WORKFLOW / "artifact-paths.yaml")
    unstaged_owners = {
        spec["owner"]
        for spec in registry["artifacts"].values()
        if spec.get("owner") and spec["owner"] not in stage_of
    }
    for owner in sorted(unstaged_owners):
        text = read(SKILLS / owner / "SKILL.md")
        for field, named in re.findall(
            r"\b(stage|next_stage|loop_back_stage|current_stage):\s*([A-Z_]+)", text
        ):
            if named in (stage_map.get("retired_identifiers") or {}):
                errors.append(f"{owner}: {field} uses retired identifier {named}")
            elif named not in order and named != "NULL":
                errors.append(f"{owner}: {field} names unknown stage {named}")

    for skill, stage in sorted(stage_of.items()):
        text = read(SKILLS / skill / "SKILL.md")
        if not text:
            continue  # already reported as missing
        if "Result Envelope" not in text:
            errors.append(f"{skill}: no Result Envelope section")
            continue
        if f"stage: {stage}" not in text:
            errors.append(f"{skill}: Result Envelope does not declare 'stage: {stage}'")
        # A retired identifier is only a defect in a stage POSITION. Skills are
        # expected to name the retired ids in prose - the Prohibited section
        # exists precisely to list them - so matching bare words would flag the
        # rule itself as a violation of the rule.
        retired = set(stage_map.get("retired_identifiers") or {})
        for field, named in re.findall(
            r"\b(stage|next_stage|loop_back_stage|current_stage|substep_stage):\s*([A-Z_]+)",
            text,
        ):
            if named in retired:
                errors.append(f"{skill}: {field} uses retired identifier {named}")
            elif named not in order and named != "NULL":
                errors.append(f"{skill}: {field} names unknown stage {named}")

        for key in re.findall(r"loop_back_stage:\s*([A-Z_]+)", text):
            if key not in order and key != "NULL":
                errors.append(f"{skill}: loop_back_stage names unknown stage {key}")


def check_no_retired(stage_map: dict[str, Any], errors: list[str]) -> None:
    retired_stages = set(stage_map.get("retired_identifiers") or {})
    history = "docs/workflow/history.jsonl"

    for path in scanned_files():
        posix = path.relative_to(ROOT).as_posix()
        if posix in CANONICAL_EXCLUDE or posix == history:
            continue
        text = read(path)
        if not text:
            continue
        if SEQ_ID.search(text) and posix not in RETIRED_ID_DOC_ALLOWLIST:
            errors.append(f"{posix}: retired sequential story id (US-0NN)")
        # The retired-path-shape check applies to files that DRIVE future runs -
        # skills, commands, workflow definitions, and source. A delivered
        # artifact under docs/ may legitimately narrate what a file was called
        # at the time it was written; rewriting that would falsify the record.
        if _is_live_harness(posix):
            for stem in RETIRED_PATH_STEMS:
                if stem in text:
                    errors.append(f"{posix}: retired artifact path shape '{stem}'")

        # A retired stage id anywhere in a skill or command - a prose sentence,
        # a table cell - not just in `current_stage:` position. Lines that are
        # *about* the retired ids (a Prohibited list, a retired_identifiers
        # note) are exempt, or the rule would flag itself.
        if posix.startswith(".claude/"):
            # "PR" is excluded: it is an ordinary English abbreviation as well
            # as a retired stage id, so a bare-word match is pure noise here.
            # It is still caught in stage position by check_skill_contracts.
            watched = sorted(retired_stages - {"PR"})
            lines = text.splitlines()
            for lineno, line in enumerate(lines, 1):
                # The exemption keyword often sits on the previous line, since
                # the id list wraps: "...retired stage\n identifiers (`DESIGN`,".
                window = (lines[lineno - 2] if lineno > 1 else "") + " " + line
                if any(
                    w in window.lower()
                    for w in ("retired", "do not use", "prohibited", "deprecated")
                ):
                    continue
                for stage in watched:
                    if re.search(rf"(?<![A-Z_]){stage}(?![A-Z_])", line):
                        errors.append(f"{posix}:{lineno}: retired stage identifier {stage}")
        if posix.startswith("docs/workflow/") or posix.startswith(".claude/"):
            for stage in retired_stages:
                if re.search(rf"current_stage:\s*{stage}\b", text):
                    errors.append(f"{posix}: current_stage uses retired identifier {stage}")


def check_paths_resolve(errors: list[str]) -> None:
    for path in scanned_files():
        posix = path.relative_to(ROOT).as_posix()
        if posix in CANONICAL_EXCLUDE:
            continue
        text = read(path)
        for ref in sorted(set(DOC_PATH.findall(text))):
            if "{" in ref or "*" in ref or "<" in ref:
                continue
            if not (ROOT / ref).exists():
                errors.append(f"{posix}: references missing {ref}")


def check_registry_resolves(registry: dict[str, Any], errors: list[str]) -> None:
    catalog = load(ROOT / "docs" / "catalog" / "stories.yaml")
    delivered = [s for s in catalog["stories"] if s["state"] in {"COMPLETED", "ARCHIVED"}]
    # Only story-level artifacts every delivered story must have.
    required = ["specification", "specification_review"]
    for story in delivered:
        if story["id"] in {"US-1.1", "US-1.2", "US-1.3"}:
            continue  # delivered before pipeline tracking; no pipeline artifacts
        for key in required:
            pattern: str = registry["artifacts"][key]["pattern"]
            resolved = pattern.format(story_id=story["id"], slug=story["slug"])
            if not (ROOT / resolved).exists():
                errors.append(f"{story['id']}: {key} missing at {resolved}")


def main() -> int:
    errors: list[str] = []
    stage_map, registry = check_stage_map(errors)
    check_skill_contracts(stage_map, errors)
    check_no_retired(stage_map, errors)
    check_paths_resolve(errors)
    check_registry_resolves(registry, errors)

    if errors:
        logger.error("harness validation FAILED - %d problem(s):", len(errors))
        for e in errors:
            logger.error("  - %s", e)
        return 1
    logger.info("harness validation OK")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
