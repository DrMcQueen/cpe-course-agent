# test_validator.py
# Confidence check for the rule-based validator. Runs the validator against
# known-good output (should pass) and deliberately broken output (should fail
# with specific reasons). A validator only trusted after you have watched it
# correctly reject bad input, not just accept good input.

from validator import validate

# --- Known-GOOD output, matching the shape your pipeline actually produces ---

good_objectives = """1. Describe the components of the NIST CSF 2.0.
2. Explain the six CSF Core Functions.
3. Develop a Current and Target Organizational Profile.
4. Apply CSF Tiers to characterize governance rigor.
5. Utilize supplementary NIST resources.
6. Analyze how the CSF facilitates communication."""

good_outline = """Module 1: Foundations of the NIST CSF 2.0
This module introduces the core components.

Module 2: The Six Core Functions
This module explains the functions.

Module 3: Profiles and Tiers
This module covers assessment."""

good_assessment = """::Q1::What are the components? {
=The Core, Profiles, and Tiers
~The wrong one
~Another wrong one
~A third wrong one
}

::Q2::Which function governs? {
=GOVERN
~IDENTIFY
~PROTECT
~RESPOND
}

::Q3::What is a Profile for? {
=Assessing posture
~Something wrong
~Another wrong
~Third wrong
}

::Q4::What do Tiers describe? {
=Rigor of practices
~Wrong
~Wrong again
~Third wrong
}

::Q5::What are Informative References? {
=Links to external standards
~Wrong
~Wrong
~Wrong
}

::Q6::How does CSF aid communication? {
=Shared taxonomy across levels
~Wrong
~Wrong
~Wrong
}"""

print("----- TEST 1: known-good output (should PASS, no failures) -----")
failures = validate(good_objectives, good_outline, good_assessment)
if failures:
    print("UNEXPECTED FAILURES:")
    for f in failures:
        print("  -", f)
else:
    print("PASSED: no failures, as expected.")

# --- Deliberately BROKEN output: only 2 objectives, and a question missing
# its correct answer. The validator should catch BOTH. ---

bad_objectives = """1. Describe something.
2. Explain something else."""

bad_assessment = """::Q1::A question with no correct answer? {
~wrong one
~another wrong
~third wrong
}"""

print("\n----- TEST 2: broken output (should FAIL with specific reasons) -----")
failures = validate(bad_objectives, good_outline, bad_assessment)
if failures:
    print("CAUGHT THESE FAILURES (expected):")
    for f in failures:
        print("  -", f)
else:
    print("PROBLEM: validator passed broken output. The rules are not working.")