# graph.py
# The pipeline orchestration. Defines the shared state that flows through
# every node, then wires the nodes into a LangGraph state machine.
# Ingestion logic lives in ingest.py and is imported, keeping document
# preparation separate from orchestration.


# ============================================================================
# IMPORTS & SETUP
# ============================================================================
import time
from typing import TypedDict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from ingest import extract_text, chunk_text
from validator import validate
from langgraph.graph import StateGraph, START, END

# Loads the API key from .env into the environment before any model call.
load_dotenv()

SOURCE_PATH = "sources/NIST.CSWP.29.pdf"


# The shared state. Every node receives this, reads the fields it needs, and
# returns updates to it. TypedDict gives us named, type-checked fields so a
# typo like state["objecives"] is caught by the editor instead of failing
# silently at runtime. This is the "form" that travels down the assembly line.
class CourseState(TypedDict):
    source_text: str        # filled by INGEST: the full extracted document
    chunks: list[str]       # filled by INGEST: the document split into windows
    objectives: str         # filled by OBJECTIVES: extracted learning objectives
    outline: str            # filled by OUTLINE: the course structure
    content: str            # filled by CONTENT: the written instructional material
    assessment: str         # filled by ASSESSMENT: the quiz questions

    # --- Loop control, added for the validation cycle ---
    failures: list[str]     # filled by VALIDATE: rule failures from the last run,
                            # empty list means the output passed. This is what the
                            # conditional edge reads to decide pass vs regenerate.
    attempts: int           # incremented each time the pipeline runs. The loop
                            # escalates to a human when this hits the retry cap,
                            # distinguishing systematic failure from transient.

# One shared model instance for every node. Flash Lite, chosen for the free
# tier's 500 requests/day allowance (the stronger Flash models cap at 20/day,
# too few to iterate a multi-node pipeline). temperature=0.3 keeps output
# focused and repeatable, which matters when the goal is consistent, testable
# structure rather than creative variety.
llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.3)


def load_prompt(name: str) -> str:
    """Read a prompt file from the prompts/ folder.

    Prompts live in their own files, not inline in code, so they can be read,
    versioned, and diffed independently. A refined prompt shows up as a clean
    git diff of one file, which is the evidence of prompt iteration.
    """
    with open(f"prompts/{name}.md", encoding="utf-8") as f:
        return f.read()


def objectives_node(state: CourseState) -> dict:
    """OBJECTIVES: extract learning objectives from the source document.

    Sends the model the substantive early chunks (skipping deep appendices)
    plus the objectives prompt, and returns the result as a state update.
    Returns only the field it owns; LangGraph merges it into shared state.
    """
    system_prompt = load_prompt("objectives")

    # Chunks 2 through 8: past the title page and table of contents, into the
    # framework's core functions and categories. A focused slice, not the whole
    # 32 pages, to stay cheap and keep the model on the substance.
    source_excerpt = "\n".join(state["chunks"][2:9])

    # A brief pause before the call. The free tier limits requests per minute;
    # spacing calls prevents 429 rate-limit errors when nodes run back to back.
    time.sleep(4)

    response = llm.invoke(
        f"{system_prompt}\n\n--- SOURCE MATERIAL ---\n\n{source_excerpt}"
    )

    # .text, not .content: LangChain 1.x returns content as a list of blocks,
    # and .text is the accessor that flattens it to a plain string.
    return {"objectives": response.text}

def outline_node(state: CourseState) -> dict:
    """OUTLINE: design the course structure from the learning objectives.

    Unlike OBJECTIVES, this node reads a previous node's output
    (state["objectives"]), not the raw document. The course structure should
    follow from the objectives, so the outline is grounded in them rather than
    re-derived from source text. This is the pipeline building on itself.
    """
    system_prompt = load_prompt("outline")

    time.sleep(4)

    response = llm.invoke(
        f"{system_prompt}\n\n--- LEARNING OBJECTIVES ---\n\n{state['objectives']}"
    )

    return {"outline": response.text}

def content_node(state: CourseState) -> dict:
    """CONTENT: write instructional text for each module, one call per module.

    Design decision (looping): earlier this generated all modules in a single
    call. Switched to one call per module so each module gets focused, richer
    content (200-250 words) and so a weak result in one module does not drag
    down the others. This mirrors how a production pipeline isolates module
    generation. Tradeoff: more API calls per run and a slower pass.

    Design decision (length): raised from ~150 to 200-250 words per module so
    there is enough substance for assessment items to visibly align to what the
    module actually taught. Alignment is the thing the proof of concept must
    show, and it is invisible if the content is thin.
    """
    system_prompt = load_prompt("content")

    # The outline is one text block containing all modules. We split it into
    # individual modules so each can be sent to the model on its own. Modules
    # are separated by blank lines in the outline's output format, so a blank
    # line is the split point. We filter out any empty fragments left by the
    # split so we do not send the model an empty module.
    module_blocks = [
        block.strip()
        for block in state["outline"].split("\n\n")
        if block.strip()
    ]

    # Generate content module by module, collecting each result. Using a list
    # and joining at the end (rather than string concatenation in the loop) is
    # the standard Python approach: clearer and avoids repeated recopying.
    module_contents = []
    for i, module in enumerate(module_blocks, start=1):
        time.sleep(4)  # rate-limit spacing, one pause per call now
        response = llm.invoke(
            f"{system_prompt}\n\n--- MODULE ---\n\n{module}"
        )
        # Re-attach a clean heading so the assembled content is readable and so
        # downstream nodes and export can tell modules apart.
        module_contents.append(f"## Module {i}\n\n{response.text}")

    # Join all module contents into one block for the state. Downstream nodes
    # (ASSESSMENT, and later the validator) read this combined content.
    return {"content": "\n\n".join(module_contents)}

def assessment_node(state: CourseState) -> dict:
    """ASSESSMENT: write GIFT-format quiz questions aligned to the objectives.

    Reads BOTH objectives and content. This dual input is the alignment
    mechanism: questions are written to test the objectives (what the learner
    should be able to do) using material from the content (what was taught).
    Assessing objectives rather than arbitrary facts is a core instructional
    design principle, and it makes the output checkable: each question should
    trace to an objective.

    Output is Moodle GIFT format so questions import directly into a live LMS
    question bank with no manual reformatting. This makes the assessment the
    most concretely validatable node: GIFT is either syntactically valid or it
    is not, and question count either matches the objective count or it does not.
    """
    system_prompt = load_prompt("assessment")

    time.sleep(4)

    response = llm.invoke(
        f"{system_prompt}\n\n"
        f"--- LEARNING OBJECTIVES ---\n\n{state['objectives']}\n\n"
        f"--- INSTRUCTIONAL CONTENT ---\n\n{state['content']}"
    )

    return {"assessment": response.text}

def validate_node(state: CourseState) -> dict:
    """VALIDATE: run the rule-based validator and record the result in state.

    This node does not judge anything itself. It calls the validator (built and
    tested separately in validator.py) and writes two things into state:
    the list of failures (empty means passed) and an incremented attempt count.

    The conditional edge downstream reads these two fields to decide whether to
    finish, regenerate, or escalate. Keeping the decision OUT of this node and
    IN the edge is deliberate: the node's job is to produce the verdict, the
    edge's job is to act on it. Separating "assess" from "route on the
    assessment" keeps each piece simple and independently understandable.
    """
    failures = validate(
        state["objectives"],
        state["outline"],
        state["assessment"],
    )

    # attempts may not be set on the first pass; default to 0 then add 1.
    # This counter is what bounds the loop and triggers human escalation.
    current_attempts = state.get("attempts", 0) + 1

    # Log to the console so a human watching the run sees the verdict live.
    # This is the auditable trail: every validation pass prints its outcome.
    if failures:
        print(f"\n[VALIDATE] Attempt {current_attempts}: FAILED with {len(failures)} issue(s):")
        for f in failures:
            print(f"    - {f}")
    else:
        print(f"\n[VALIDATE] Attempt {current_attempts}: PASSED all checks.")

    return {"failures": failures, "attempts": current_attempts}

# ============================================================================
# ROUTING / CONDITIONAL EDGE LOGIC
# Reads validation result from state and returns a direction: pass, escalate
# (retry cap hit, hand to human), or regenerate (loop back). Decision only.
# ============================================================================
MAX_ATTEMPTS = 3


def route_after_validation(state: CourseState) -> str:
    """Decide what happens after validation. Returns the name of the next step.

    This is the conditional edge's decision function. It does not act; it only
    chooses a direction by returning a string that the graph maps to a node
    (or to END). Three outcomes:

    - "pass": no failures. Finish.
    - "escalate": failures remain but the retry cap is hit. This is systematic
      failure, retrying will not help, so finish and leave the failures in state
      for a human to diagnose. This is the human-in-the-loop escalation.
    - "regenerate": failures exist and attempts remain. Loop back and rerun.
    """
    if not state["failures"]:
        return "pass"
    if state["attempts"] >= MAX_ATTEMPTS:
        print(
            f"\n[ROUTER] Hit {MAX_ATTEMPTS}-attempt cap with failures remaining. "
            f"Escalating to human review."
        )
        return "escalate"
    print(f"\n[ROUTER] Validation failed, regenerating (attempt {state['attempts']} of {MAX_ATTEMPTS}).")
    return "regenerate"

# ============================================================================
# GRAPH ASSEMBLY
# Wires nodes and edges into a compiled state machine. The conditional edge
# out of validate is what makes this a graph with a loop, not a linear chain.
# ============================================================================
def build_graph():
    """Wire the nodes and edges into a compiled LangGraph state machine.

    Linear spine: objectives -> outline -> content -> assessment -> validate.
    Then a conditional edge out of validate that either finishes, loops back to
    objectives (regenerate), or finishes with failures recorded (escalate).
    That loop back is what makes this a graph rather than a chain.
    """
    graph = StateGraph(CourseState)

    # Register each node under a name.
    graph.add_node("objectives", objectives_node)
    graph.add_node("outline", outline_node)
    graph.add_node("content", content_node)
    graph.add_node("assessment", assessment_node)
    graph.add_node("validate", validate_node)

    # The linear spine: each node flows to the next, unconditionally.
    graph.add_edge(START, "objectives")
    graph.add_edge("objectives", "outline")
    graph.add_edge("outline", "content")
    graph.add_edge("content", "assessment")
    graph.add_edge("assessment", "validate")

    # The conditional edge: after validate, route_after_validation decides.
    # The dict maps each string the router can return to a destination.
    # "regenerate" points back to "objectives", creating the loop.
    # "pass" and "escalate" both go to END, but for different reasons that
    # the printed logs and the failures field make auditable.
    graph.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "pass": END,
            "escalate": END,
            "regenerate": "objectives",
        },
    )

    return graph.compile()

# ============================================================================
# ENTRY POINT / TEST HARNESS
# Runs the full pipeline end to end from a single graph.invoke() call.
# Ingestion runs once up front (the source is fixed); LangGraph then
# orchestrates objectives -> outline -> content -> assessment -> validate,
# including the regeneration loop, from one call.
# ============================================================================
if __name__ == "__main__":
    # Build the extracted, chunked document once. Ingestion is not part of the
    # loop (the source does not change), so it runs before the graph.
    text = extract_text(SOURCE_PATH)
    chunks = chunk_text(text)

    # Initial state. The generation fields start empty; the loop fields start
    # at their base values. LangGraph fills the rest as nodes run.
    initial_state: CourseState = {
        "source_text": text,
        "chunks": chunks,
        "objectives": "",
        "outline": "",
        "content": "",
        "assessment": "",
        "failures": [],
        "attempts": 0,
    }

    # Build the graph and run it. This single invoke replaces the four manual
    # state.update calls from before: LangGraph now orchestrates the whole
    # pipeline, including the validation loop, from one call.
    app = build_graph()
    final_state = app.invoke(initial_state)

    print("\n========== FINAL RESULT ==========")
    print(f"Attempts: {final_state['attempts']}")
    print(f"Remaining failures: {final_state['failures']}")
    print("\n----- OBJECTIVES -----\n")
    print(final_state["objectives"])
    print("\n----- ASSESSMENT (GIFT) -----\n")
    print(final_state["assessment"])
