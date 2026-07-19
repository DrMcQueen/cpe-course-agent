# validator.py
# Rule-based validation for the pipeline's generated output.
# Every check here is deterministic and structural: counts and syntax, nothing
# semantic. Semantic checks (objective coverage, distractor plausibility) are
# handled separately by an LLM-judge, because forcing rules to do meaning-work
# badly would blur the design's core line: rules own structure, judge owns
# meaning.
#
# Each function returns a list of failure strings. An empty list means the
# output passed. Returning the reasons (not just True/False) is deliberate:
# the failure reason is what makes the system auditable and what the
# human-facing diagnosis ladder acts on when the loop escalates.

import re


def check_objectives(objectives: str) -> list[str]:
    """Structural checks on the OBJECTIVES output.

    Rule: 4 to 6 objectives, one per numbered line. This is exactly what the
    objectives prompt constrains, so the rule enforces the prompt's contract.
    """
    failures = []

    # Count lines that look like a numbered objective: start with a digit and
    # a period. This matches the prompt's required output format ("1. ...").
    numbered = [
        line for line in objectives.splitlines()
        if re.match(r"^\s*\d+\.", line)
    ]

    if len(numbered) < 4:
        failures.append(
            f"OBJECTIVES: found {len(numbered)}, need at least 4"
        )
    elif len(numbered) > 6:
        failures.append(
            f"OBJECTIVES: found {len(numbered)}, need at most 6"
        )

    return failures


def check_outline(outline: str) -> list[str]:
    """Structural checks on the OUTLINE output.

    Rule: 3 to 5 modules. Coverage (does every objective map to a module) is a
    semantic question and is intentionally NOT checked here. It belongs to the
    LLM-judge. This function only counts modules.
    """
    failures = []

    # Modules are lines beginning "Module N:", per the outline prompt's format.
    modules = [
        line for line in outline.splitlines()
        if re.match(r"^\s*Module\s+\d+\s*:", line)
    ]

    if len(modules) < 3:
        failures.append(f"OUTLINE: found {len(modules)} modules, need at least 3")
    elif len(modules) > 5:
        failures.append(f"OUTLINE: found {len(modules)} modules, need at most 5")

    return failures


def check_assessment(assessment: str, objective_count: int) -> list[str]:
    """Structural and GIFT-syntax checks on the ASSESSMENT output.

    This is the strongest, most auditable check in the rubric, and it protects
    the pipeline's most valuable artifact: GIFT that imports directly into a
    live Moodle question bank. Malformed GIFT breaks that promise, so syntax
    validity is checked precisely.

    Two rules:
    1. Question count equals objective count (one question per objective).
    2. Each question is valid GIFT: has a ::title::, exactly one =correct
       answer, and at least two ~distractors.
    """
    failures = []

    # A GIFT question block runs from "::" to the closing "}". Split on the
    # closing brace and keep blocks that actually contain a "::title::".
    blocks = [b for b in assessment.split("}") if "::" in b]

    # Rule 1: one question per objective.
    if len(blocks) != objective_count:
        failures.append(
            f"ASSESSMENT: found {len(blocks)} questions, "
            f"expected {objective_count} (one per objective)"
        )

    # Rule 2: GIFT syntax per question.
    for i, block in enumerate(blocks, start=1):
        # Exactly one correct answer, marked with "=" at the start of a line.
        correct = re.findall(r"^\s*=", block, re.MULTILINE)
        # Distractors, marked with "~".
        distractors = re.findall(r"^\s*~", block, re.MULTILINE)

        if len(correct) != 1:
            failures.append(
                f"ASSESSMENT Q{i}: found {len(correct)} correct answers "
                f"(=), need exactly 1"
            )
        if len(distractors) < 2:
            failures.append(
                f"ASSESSMENT Q{i}: found {len(distractors)} distractors "
                f"(~), need at least 2"
            )

    return failures


def validate(objectives: str, outline: str, assessment: str) -> list[str]:
    """Run all rule-based checks and collect every failure.

    Returns an empty list if everything passes. A non-empty list is the full
    set of reasons the output failed, which is what gets logged and what drives
    the regenerate-or-escalate decision in the graph loop.
    """
    objective_count = len([
        line for line in objectives.splitlines()
        if re.match(r"^\s*\d+\.", line)
    ])

    failures = []
    failures += check_objectives(objectives)
    failures += check_outline(outline)
    failures += check_assessment(assessment, objective_count)
    return failures