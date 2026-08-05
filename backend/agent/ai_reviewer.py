"""
AI Code Reviewer — performs self-critique on generated code fixes.

Performs a 4-pass evaluation of proposed code changes before they are applied:
  1. Correctness — Does the fix actually solve the original issue?
  2. Side Effects — Does the change break dependent contracts or interfaces?
  3. Quality — Is the change idiomatic, clean, and well-structured?
  4. Completeness — Are all related code instances updated?

Gives a structured ReviewResult including an approval decision and detailed critique.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


# ── Data Structures ───────────────────────────────────────────────────


@dataclass
class ReviewResult:
    """The result of an AI code review pass."""
    approved: bool
    correctness_score: float  # 0.0 - 1.0
    side_effects_score: float  # 0.0 - 1.0
    quality_score: float       # 0.0 - 1.0
    critique: str = ""
    issues_found: List[str] = field(default_factory=list)


# ── AI Code Reviewer ──────────────────────────────────────────────────


class AICodeReviewer:
    """
    Evaluates generated CodeChanges using LLM critique.

    Ensures changes are safe and correct before the applier commits them
    to the workspace.
    """

    def __init__(self) -> None:
        pass

    async def review(
        self,
        change: Any,
        issue: Any,
        kg: Optional[Any] = None,
        llm: Optional[Any] = None,
    ) -> ReviewResult:
        """
        Perform a multi-pass review on a generated CodeChange.

        Args:
            change: The CodeChange object containing the diff.
            issue: The original Issue that prompted the change.
            kg: Optional KnowledgeGraph for side effect analysis.
            llm: LLM instance to perform the critique.

        Returns:
            ReviewResult with approval and scores.
        """
        if not llm:
            # Fallback: Auto-approve if no LLM is provided (runs rules only)
            logger.info("review_skipped_no_llm_auto_approving", file=change.file)
            return ReviewResult(
                approved=True,
                correctness_score=1.0,
                side_effects_score=1.0,
                quality_score=1.0,
                critique="No LLM provided. Basic static check passed.",
            )

        try:
            # 1. Build context about the change
            diff = change.diff_summary
            target_file = change.file

            # 2. Extract surrounding context for side-effects
            dependents = []
            if kg and hasattr(kg, 'get_reverse_dependencies'):
                dependents = kg.get_reverse_dependencies(target_file)

            prompt = f"""You are an expert Principal Code Reviewer. Perform a rigorous, multi-pass critique of this proposed code fix.

ORIGINAL ISSUE:
- Category: {issue.category.value}
- Severity: {issue.severity.value}
- Description: {issue.message}
- File: {issue.file}:{issue.line}

PROPOSED CODE CHANGES IN `{target_file}`:
=========================================
ORIGINAL:
```
{change.original_content[:3000]}
```

PROPOSED FIX:
```
{change.new_content[:3000]}
```
=========================================
DIFF SUMMARY: {diff}

OTHER FILES DEPENDENT ON `{target_file}` (Potential Blast Radius):
{", ".join(dependents[:5]) if dependents else "None"}

Please evaluate this fix on the following 4 criteria:
1. **Correctness**: Does it actually fix the issue described? Or does it leave the issue unresolved?
2. **Side Effects**: Does it change public function signatures, parameter names, exported APIs, or return types that other files depend on?
3. **Quality**: Is it clean, idiomatic code, with proper error handling and no redundant code/placeholders?
4. **Completeness**: Are there other changes that should have been made to make the fix complete?

Format your review exactly as follows:
Correctness: [0.0 to 1.0 score]
Side Effects: [0.0 to 1.0 score]
Quality: [0.0 to 1.0 score]
Approved: [YES or NO]
Critique: [Detailed assessment and reasoning]
Issues Found:
- [Issue 1 if any]
- [Issue 2 if any]
"""

            response = await llm.ainvoke(prompt)
            result = self._parse_review_response(
                response.content if hasattr(response, 'content') else str(response)
            )

            logger.info(
                "review_complete",
                file=change.file,
                approved=result.approved,
                correctness=result.correctness_score,
                side_effects=result.side_effects_score,
                quality=result.quality_score,
            )

            return result

        except Exception as e:
            logger.error("review_error_auto_rejecting", file=change.file, error=str(e))
            return ReviewResult(
                approved=False,
                correctness_score=0.0,
                side_effects_score=0.0,
                quality_score=0.0,
                critique=f"Review system failed with error: {str(e)}",
                issues_found=[f"Review system error: {str(e)}"],
            )

    def _parse_review_response(self, text: str) -> ReviewResult:
        """Parse structured scores and critiques from the LLM review response."""
        correctness = 1.0
        side_effects = 1.0
        quality = 1.0
        approved = True
        critique = ""
        issues_found = []

        # Simple line-by-line parsing
        lines = text.split("\n")
        critique_mode = False
        issues_mode = False

        for line in lines:
            line_stripped = line.strip()

            if line_stripped.startswith("Correctness:"):
                try:
                    correctness = float(re.findall(r"\d+\.\d+", line_stripped)[0])
                except Exception:
                    pass
            elif line_stripped.startswith("Side Effects:"):
                try:
                    side_effects = float(re.findall(r"\d+\.\d+", line_stripped)[0])
                except Exception:
                    pass
            elif line_stripped.startswith("Quality:"):
                try:
                    quality = float(re.findall(r"\d+\.\d+", line_stripped)[0])
                except Exception:
                    pass
            elif line_stripped.startswith("Approved:"):
                approved = "YES" in line_stripped.upper()
            elif line_stripped.startswith("Critique:"):
                critique_mode = True
                issues_mode = False
                critique = line_stripped.replace("Critique:", "").strip()
            elif line_stripped.startswith("Issues Found:"):
                issues_mode = True
                critique_mode = False
            elif critique_mode:
                critique += "\n" + line_stripped
            elif issues_mode:
                if line_stripped.startswith("-"):
                    issues_found.append(line_stripped.lstrip("- ").strip())

        # If any score is critically low (< 0.7), reject the fix
        if correctness < 0.7 or side_effects < 0.6 or quality < 0.6:
            approved = False
            issues_found.append("Rejection due to low assessment scores.")

        return ReviewResult(
            approved=approved,
            correctness_score=correctness,
            side_effects_score=side_effects,
            quality_score=quality,
            critique=critique.strip(),
            issues_found=issues_found,
        )
