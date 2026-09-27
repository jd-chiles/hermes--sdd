"""Deterministic intake, adaptive workflow selection, and repository artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import Ledger, ProjectPaths, SDDError, slugify


@dataclass(frozen=True)
class Plan:
    mode: str
    slug: str
    objective: str
    criteria: list[dict[str, Any]]
    tasks: list[dict[str, Any]]


def classify(request: str, explicit_mode: str | None = None) -> str:
    if explicit_mode and explicit_mode in {"bugfix", "feature", "product"}:
        return explicit_mode
    lower = request.lower()
    if any(word in lower for word in ("new product", "from scratch", "launch", "platform", "application")):
        return "product"
    if any(word in lower for word in ("bug", "fix", "broken", "regression", "error", "crash")) and len(request) < 500:
        return "bugfix"
    return "feature"


def _criteria(request: str) -> list[dict[str, Any]]:
    explicit: list[str] = []
    for line in request.splitlines():
        match = re.match(r"\s*(?:[-*]\s*)?(?:acceptance|ac)\s*[:\-]\s*(.+)", line, flags=re.I)
        if match:
            explicit.append(match.group(1).strip())
    statements = explicit or [f"The requested change is implemented in the local repository: {request.strip()}", "The relevant automated verification passes."]
    return [{"id": f"AC-{index:03d}", "text": statement, "required": True} for index, statement in enumerate(statements, start=1)]


def build_plan(request: str, explicit_mode: str | None = None) -> Plan:
    request = request.strip()
    if not request:
        raise SDDError("a non-empty development request is required")
    mode = classify(request, explicit_mode)
    slug = slugify(request.splitlines()[0])
    if mode == "bugfix":
        task_templates = [
            ("T-001", "Implement the scoped regression fix", "engineer", "implementation", None),
            ("T-002", "Independently review the regression fix", "reviewer", "review", "T-001"),
            ("T-003", "Run acceptance checks and submit evidence", "qa", "acceptance", "T-002"),
        ]
    elif mode == "feature":
        task_templates = [
            ("T-001", "Clarify requirements and acceptance criteria", "coordinator", "requirements", None),
            ("T-002", "Inspect the repository and define compatible interfaces", "architect", "architecture", "T-001"),
            ("T-003", "Implement the feature with regression tests", "engineer", "implementation", "T-002"),
            ("T-004", "Independently review correctness and security", "reviewer", "review", "T-003"),
            ("T-005", "Run acceptance and browser checks where applicable", "qa", "acceptance", "T-004"),
        ]
    else:
        task_templates = [
            ("T-001", "Establish audience, scope, and product acceptance", "coordinator", "requirements", None),
            ("T-002", "Define UX direction and user journeys", "architect", "ux", "T-001"),
            ("T-003", "Define architecture and compatibility boundaries", "architect", "architecture", "T-001"),
            ("T-004", "Create the first incremental product slice", "engineer", "implementation", "T-002"),
            ("T-005", "Independently review the product slice", "reviewer", "review", "T-004"),
            ("T-006", "Run acceptance and browser scenarios", "qa", "acceptance", "T-005"),
            ("T-007", "Prepare requested documentation and launch materials", "writer", "documentation", "T-006"),
        ]
    return Plan(
        mode=mode,
        slug=slug,
        objective=request,
        criteria=_criteria(request),
        tasks=[{"stable_key": key, "title": title, "role": role, "kind": kind, "parent_key": parent} for key, title, role, kind, parent in task_templates],
    )


def write_spec(paths: ProjectPaths, plan: Plan, ledger: Ledger) -> Path:
    feature_dir = paths.features / plan.slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    spec_path = feature_dir / "spec.md"
    lines = [
        f"# {plan.slug}",
        "",
        f"- Mode: `{plan.mode}`",
        f"- Specification revision: `1`",
        "- Delivery boundary: verified local repository change; no automatic commit, PR, deployment, or publication.",
        "",
        "## Request",
        "",
        plan.objective,
        "",
        "## Acceptance criteria",
        "",
    ]
    lines.extend(f"- **{criterion['id']}** — {criterion['text']}" for criterion in plan.criteria)
    lines.extend(["", "## Stable task graph", ""])
    for task in plan.tasks:
        dependency = f"; depends on `{task['parent_key']}`" if task.get("parent_key") else ""
        lines.append(f"- **{task['stable_key']}** ({task['role']}) — {task['title']}{dependency}")
    lines.extend(["", "## Limits", "", "- Maximum concurrent workers: 3", "- Maximum repair cycles per task: 2", "- Maximum run duration: 60 minutes", ""])
    spec_path.write_text("\n".join(lines), encoding="utf-8")
    return spec_path


def read_current_plan(ledger: Ledger) -> dict[str, Any]:
    project = ledger.project()
    if not project:
        raise SDDError("project is not initialized")
    with ledger._connect() as db:  # read-only internal helper; all writes remain transactional
        row = db.execute("SELECT content_json FROM specs WHERE project_id = ? ORDER BY revision DESC LIMIT 1", (project["project_id"],)).fetchone()
    if not row:
        raise SDDError("project has no specification")
    import json

    return json.loads(row[0])
