# Customer Portal

Customer Portal is a backend system that lets customers register, authenticate, manage their profile, and contact support. It exposes APIs and follows API-first development practices.

## Status

Spec-driven, artifact-driven delivery: product vision, stories, and formal specifications are in place for all 16 planned stories; US-001 (Register User) is implemented, the rest are pending implementation.

## Repository layout

- [`AGENTS.md`](AGENTS.md) — engineering rules and conventions for the codebase (architecture, layering, testing, quality gates).
- [`docs/product/`](docs/product) — product vision, epic map, business glossary/rules, personas, non-functional requirements.
- [`docs/stories/`](docs/stories) — user stories with acceptance criteria.
- [`docs/specifications/`](docs/specifications) — formal specs derived from the stories.
- [`docs/reviews/specifications/`](docs/reviews/specifications) — spec review reports.
- [`docs/designs/`](docs/designs), [`docs/decisions/`](docs/decisions), [`docs/plans/`](docs/plans), [`docs/impact-analysis/`](docs/impact-analysis), [`docs/verification/`](docs/verification) — downstream artifact-driven-development stages (API/DB design, open decisions, implementation plans, impact analysis, verification), populated per story as it progresses.
- [`docs/workflow/`](docs/workflow) — which story is currently active and at what stage.
- [`.claude/skills/`](.claude/skills) — Claude Code skills used to author and review specs, designs, plans, and tests for this project.
