# graph.py
# The pipeline orchestration. Defines the shared state that flows through
# every node, then wires the nodes into a LangGraph state machine.
# Ingestion logic lives in ingest.py and is imported, keeping document
# preparation separate from orchestration.

import time
from typing import TypedDict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from ingest import extract_text, chunk_text

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

# Standalone test: run just the ingestion + objectives path and print the
# result, before the full graph is wired. Verifies this node in isolation.
if __name__ == "__main__":
    text = extract_text(SOURCE_PATH)
    chunks = chunk_text(text)
    state: CourseState = {
        "source_text": text,
        "chunks": chunks,
        "objectives": "",
        "outline": "",
        "content": "",
        "assessment": "",
    }
    result = objectives_node(state)
    print("----- EXTRACTED OBJECTIVES -----\n")
    print(result["objectives"])