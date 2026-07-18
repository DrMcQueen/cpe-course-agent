# ingest.py
# Node 1 of the pipeline: INGEST.
# Reads the source PDF and returns its text as a single string.
# This is the "document preparation" stage. Everything downstream depends on
# the quality of what comes out of here, so this script deliberately prints
# what it extracted for human inspection before any of it reaches a model.

from pypdf import PdfReader

# The frozen source document. Public domain (US government work), so it is
# safe to send to the Gemini free tier, whose inputs may be used for training.
SOURCE_PATH = "sources/NIST.CSWP.29.pdf"


def extract_text(path: str) -> str:
    """Read every page of a PDF and return the concatenated text.

    pypdf extracts page by page. We join with newlines so page boundaries
    do not glue the last word of one page to the first word of the next,
    which is a common and hard-to-spot source of garbled input.
    """
    reader = PdfReader(path)
    pages = [page.extract_text() for page in reader.pages]
    return "\n".join(pages)


def chunk_text(text: str, chunk_size: int = 4000, overlap: int = 200) -> list[str]:
    """Split text into overlapping fixed-size windows.

    Size-based chunking, chosen for generality: it works on any document
    regardless of formatting, unlike structure-based splitting which would
    be tuned to one PDF's headings and break on the next source.

    The tradeoff it accepts: a fixed window can cut through the middle of a
    concept. Overlap is the mitigation. By repeating the last `overlap`
    characters at the start of each next chunk, a sentence split across a
    boundary survives whole in at least one chunk. The cost is a little
    duplicated text; the benefit is no severed ideas at the seams.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        # Advance by chunk_size minus overlap so each window starts slightly
        # before the previous one ended. This is what creates the overlap.
        start += chunk_size - overlap
    return chunks

# This block runs only when ingest.py is executed directly (python ingest.py),
# not when the graph imports extract_text and chunk_text as components later.
# That dual role is why the functions live above and the test harness lives here.
if __name__ == "__main__":
    text = extract_text(SOURCE_PATH)

    # Inspection output. These counts are how we verify extraction and chunking
    # worked before any of this text reaches a model. Numbers first, eyes second.
    print(f"Total characters extracted: {len(text)}")
    print(f"Total pages: {len(PdfReader(SOURCE_PATH).pages)}")

    chunks = chunk_text(text)
    print(f"Total chunks: {len(chunks)}")

    # First chunk should be exactly chunk_size (4000). The last is whatever
    # remainder is left over, so it is normally shorter. If the first chunk is
    # not 4000, the windowing logic is wrong.
    print(f"First chunk length: {len(chunks[0])}")
    print(f"Last chunk length: {len(chunks[-1])}")

    # The overlap proof. The start of chunk 2 should be text you can also find
    # at the END of chunk 1. Printing it lets us confirm overlap by eye rather
    # than trusting the math. If these do not match, the step size is wrong.
    print("\n----- START OF CHUNK 2 (shows overlap with chunk 1) -----\n")
    print(chunks[1][:250])