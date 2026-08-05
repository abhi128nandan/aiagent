"""
Improvement Planner — prioritizes issues and creates fix plans.

Two responsibilities:
  1. IssuePrioritizer: Ranks issues by severity × blast_radius × frequency × confidence
  2. ImprovementPlanner: Uses LLM to generate structured fix plans for top-N issues

The planner calculates "blast radius" using the knowledge graph — how many
files would be affected if a fix changes the target file's API surface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


# ── Data Structures ───────────────────────────────────────────────────


@dataclass
class FixItem:
    """A planned code fix for a specific issue."""
    issue_index: int           # Index into the issues list
    file: str                  # Target file to modify
    description: str           # What needs to change
    blast_radius: int          # Number of files that depend on this one
    risk_level: str            # low, medium, high
    estimated_tokens: int = 0  # Estimated LLM tokens to generate the fix
    tests_needed: List[str] = field(default_factory=list)  # Files that should be tested


@dataclass
class ImprovementPlan:
    """A structured plan for fixing a batch of issues."""
    items: List[FixItem] = field(default_factory=list)
    total_issues: int = 0
    planned_issues: int = 0
    estimated_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_issues": self.total_issues,
            "planned_issues": self.planned_issues,
            "estimated_tokens": self.estimated_tokens,
            "items": [
                {
                    "issue_index": item.issue_index,
                    "file": item.file,
                    "description": item.description,
                    "blast_radius": item.blast_radius,
                    "risk_level": item.risk_level,
                }
                for item in self.items
            ],
        }


# ── Issue Prioritizer ─────────────────────────────────────────────────


class IssuePrioritizer:
    """
    Ranks issues by multi-factor priority scoring.

    Factors:
      - Severity (40%): critical=10, high=8, medium=5, low=2, info=1
      - Blast Radius (30%): how many files depend on the affected file
      - Frequency (20%): how many instances of the same pattern exist
      - Fix Confidence (10%): how likely the auto-fix is correct
    """

    SEVERITY_SCORES = {
        "critical": 10,
        "high": 8,
        "medium": 5,
        "low": 2,
        "info": 1,
    }

    def prioritize(
        self,
        issues: List[Any],
        kg: Any = None,
    ) -> List[Any]:
        """
        Score and sort issues by priority.

        Args:
            issues: List of Issue objects from the analysis engine.
            kg: Optional KnowledgeGraph for blast radius calculation.

        Returns:
            Same list, sorted by priority_score (highest first).
        """
        if not issues:
            return issues

        # Count frequency of each (category, file) pair
        freq_map: Dict[str, int] = {}
        for issue in issues:
            key = f"{issue.category.value}:{issue.file}"
            freq_map[key] = freq_map.get(key, 0) + 1

        scored: List[tuple] = []
        for i, issue in enumerate(issues):
            # Factor 1: Severity (40%)
            severity_score = self.SEVERITY_SCORES.get(issue.severity.value, 5)

            # Factor 2: Blast Radius (30%)
            blast = 0
            if kg and hasattr(kg, 'get_reverse_dependencies'):
                try:
                    dependents = kg.get_reverse_dependencies(issue.file)
                    blast = min(len(dependents), 10)
                except Exception:
                    pass
            blast_score = blast

            # Factor 3: Frequency (20%)
            freq_key = f"{issue.category.value}:{issue.file}"
            frequency = freq_map.get(freq_key, 1)
            freq_score = min(frequency, 10)

            # Factor 4: Fix Confidence (10%)
            confidence_score = issue.fix_confidence * 10

            priority = (
                severity_score * 0.4 +
                blast_score * 0.3 +
                freq_score * 0.2 +
                confidence_score * 0.1
            )

            scored.append((priority, i, issue))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[2] for item in scored]


# ── Improvement Planner ───────────────────────────────────────────────


class ImprovementPlanner:
    """
    Creates structured fix plans from prioritized issues.

    Uses the knowledge graph to assess blast radius and determine
    which related files need to be tested after a fix.
    """

    def create_plan(
        self,
        issues: List[Any],
        kg: Any = None,
        max_items: int = 10,
    ) -> ImprovementPlan:
        """
        Create an improvement plan for the top-N issues.

        Args:
            issues: Prioritized list of Issues.
            kg: KnowledgeGraph for blast radius and test planning.
            max_items: Maximum fixes to plan per cycle.

        Returns:
            ImprovementPlan with ordered FixItems.
        """
        plan = ImprovementPlan(
            total_issues=len(issues),
            planned_issues=min(len(issues), max_items),
        )

        # Deduplicate by file+category (only fix each issue once per file)
        seen: set = set()
        batch = []
        for issue in issues:
            dedup_key = f"{issue.file}:{issue.category.value}:{issue.line}"
            if dedup_key not in seen:
                seen.add(dedup_key)
                batch.append(issue)
            if len(batch) >= max_items:
                break

        for i, issue in enumerate(batch):
            # Calculate blast radius
            blast_radius = 0
            related_tests: List[str] = []
            if kg and hasattr(kg, 'get_reverse_dependencies'):
                try:
                    dependents = kg.get_reverse_dependencies(issue.file)
                    blast_radius = len(dependents)
                    # Find test files among dependents
                    related_tests = [
                        d for d in dependents
                        if "test" in d.lower() or "spec" in d.lower()
                    ]
                except Exception:
                    pass

            # Determine risk level
            if blast_radius > 5 or issue.severity.value == "critical":
                risk = "high"
            elif blast_radius > 2 or issue.severity.value == "high":
                risk = "medium"
            else:
                risk = "low"

            # Estimate tokens (rough: ~500 tokens per fix + context)
            est_tokens = 500 + (blast_radius * 200)

            fix_item = FixItem(
                issue_index=i,
                file=issue.file,
                description=f"[{issue.category.value}] {issue.message}",
                blast_radius=blast_radius,
                risk_level=risk,
                estimated_tokens=est_tokens,
                tests_needed=related_tests[:5],
            )
            plan.items.append(fix_item)
            plan.estimated_tokens += est_tokens

        logger.info(
            "improvement_plan_created",
            total_issues=plan.total_issues,
            planned=plan.planned_issues,
            estimated_tokens=plan.estimated_tokens,
        )

        return plan
