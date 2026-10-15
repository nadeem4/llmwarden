"""Ask for a Pydantic shape and get a validated object back, on any backend.

Needs: pip install "llmwarden[anthropic]" and ANTHROPIC_API_KEY in the environment.

Where the provider supports schemas natively, llmwarden asks for one. Where it does
not, the schema goes into the prompt. Either way llmwarden validates the reply
itself, and a reply that fails validation is retried like any other failure.
"""

from pydantic import BaseModel

import llmwarden as lw


class Ranking(BaseModel):
    order: list[int]
    reason: str


model = lw.model("anthropic/claude-sonnet-5", retry=lw.Retry(attempts=3))

reply = model.complete(
    system="Rank the options from best to worst by how well they fit the goal.",
    user="Goal: a quiet weekend. Options: 1 music festival, 2 cabin by a lake, 3 city tour.",
    schema=Ranking,
)

ranking: Ranking = reply.parsed
print(ranking.order, ranking.reason)
print(f"raw text: {reply.text}")
