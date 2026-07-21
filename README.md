CPE Course Generator: A Multi-Agent Content Pipeline

A LangGraph multi-agent pipeline that turns a source document into a validated, CPE-compliant micro-course: learning objectives, a module outline, instructional content, and assessment items exported in Moodle GIFT format. It includes a self-correcting validation loop and full observability.

Built as a five-day proof of concept. The source document used here is the NIST Cybersecurity Framework (CSF) 2.0, a U.S. government work in the public domain.

What it does

Feed the pipeline a document and it produces a complete draft micro-course: learning objectives extracted from the source, a module outline that covers every objective, instructional content written for each module, and assessment questions aligned to the objectives and formatted for direct import into a learning management system. Before it finishes, the pipeline checks its own output against a rubric. If the output does not meet the rubric, it regenerates. If it fails repeatedly, it stops and flags the run for a human rather than shipping bad content or looping forever.

Why this design

The pipeline is a LangGraph state machine, not a linear chain. Five nodes generate content in sequence, each reading the previous node's output from a shared typed state. A sixth node validates, and a conditional edge after validation routes the run to one of three outcomes: finish, regenerate, or escalate to a human. That loop back is what makes this a graph rather than a chain, and it is the core of the project.

Validation is rule-based and deterministic. It checks objective count, module count, question count, and GIFT syntax validity, and every check returns a specific, auditable reason on failure rather than a bare pass or fail. This suits a certification context, where quality has to be defensible. Semantic checks that rules cannot do honestly, such as whether every objective maps to a module or whether distractors are plausible, are deliberately deferred to a planned LLM-as-judge rather than approximated with brittle keyword matching. Rules own structure; the judge owns meaning.

On validation failure the pipeline regenerates, with a retry cap of three attempts that distinguishes transient failure (model nondeterminism, which regeneration resolves) from systematic failure (a defect retries cannot fix). On hitting the cap it escalates to a human with the failure reasons preserved. Regeneration is whole-pipeline rather than node-level because the nodes are cascading-dependent: the outline is built from the objectives and the content from the outline, so a failure that surfaces downstream often has an upstream root cause.

Each agent's prompt lives in its own versioned file so prompts can be read, diffed, and refined independently, and each prompt constrains output to a testable shape so the validator has something concrete to check. The pipeline runs on Google Gemini but is provider-agnostic through LangChain: swapping to Anthropic Claude or Azure OpenAI is a one-line change. LangSmith tracing is enabled through environment variables with no changes to application code, capturing every run as a trace tree of inputs, outputs, latency, and token usage.

Tech stack

Python 3.13, LangGraph, LangChain, Google Gemini API, pypdf, and LangSmith.

Roadmap

Planned extensions in priority order: an LLM-as-judge for semantic validation to complete the hybrid design, HTML export of module content for direct LMS paste, live LMS integration via Moodle web services, RAG over the source corpus, and a multi-provider demonstration running the same pipeline on Anthropic Claude.

A full illustrated walkthrough with screenshots and demo videos is in progress.

You can view videos of the current build process on Dr. McQueen's Professional Instructional Design/AI Channel "EdTech with Dr. Jaime McQueen" https://www.youtube.com/playlist?list=PLAyjqYBYO48U

Built by Dr. Jaime McQueen, instructional designer and learning experience architect. This project pairs multi-agent AI engineering with instructional design discipline.