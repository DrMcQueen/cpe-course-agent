# test_call.py
# Purpose: verify the Gemini API key works and the LangChain adapter is wired
# correctly. Deliberately minimal. This is a connectivity check, not a feature.

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Reads .env into the process environment so the key never appears in source.
# This is what makes the repo safe to publish: .env is gitignored, and the
# code below has no credential in it. See .env.example for the required keys.
load_dotenv()

# Model choice is a constraint decision, not a preference.
# The Gemini free tier caps the stronger Flash models at 20 requests/day.
# This pipeline makes ~7 LLM calls per source document, which allows roughly
# three runs/day: not enough to iterate on prompts. Flash Lite allows 500/day
# (~70 runs). Weaker prose, but this system is judged on architecture and
# evaluation, not style, and a weaker model gives the validator real failures
# to catch.
llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")

# .invoke() is LangChain's provider-agnostic call. Swapping to Anthropic or
# Azure OpenAI means changing the constructor above; this line does not move.
response = llm.invoke(
    "In one sentence, what is a CPE credit in professional certification?"
)

print(response.text)