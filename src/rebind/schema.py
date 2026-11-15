"""What a reader model is asked to return for one passage.

The schema is sent to the model as a JSON-schema constraint, so the field
descriptions double as instructions. The passage is shown with numbered
sentences, and every item cites sentence numbers rather than quoting. A
model therefore cannot invent a quotation; it can only point at the wrong
sentence, which the support check is there to catch.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

def Evidence(what: str = "this"):
    return Field(description=f"Numbers of the one to three sentences, e.g. [4], that show {what}.")


class Character(BaseModel):
    name: str = Field(description="Full canonical name, e.g. 'Elizabeth Bennet' rather than 'Lizzy'.")
    called_here: str = Field(description="The word(s) this passage uses for them, e.g. 'Lizzy' or 'his lady'.")
    evidence: list[int] = Evidence("them, using the words in `called_here`")


class Interaction(BaseModel):
    characters: list[str] = Field(description="Canonical names of the two or more characters involved.")
    kind: Literal["conversation", "meeting", "dance", "letter", "proposal", "quarrel", "visit", "other"]
    summary: str = Field(description="One sentence: what passes between them.")
    evidence: list[int] = Evidence()


class Place(BaseModel):
    name: str
    kind: Literal["house", "room", "estate", "town", "outdoors", "road", "other"]
    evidence: list[int] = Evidence()


class Thing(BaseModel):
    name: str = Field(description="A physical object that matters in the passage.")
    description: str = Field(description="How the passage describes it, or what it is used for.")
    evidence: list[int] = Evidence()


class Event(BaseModel):
    summary: str = Field(description="One sentence.")
    evidence: list[int] = Evidence()


class Tone(BaseModel):
    tension: int = Field(ge=0, le=10, description="0 calm, 10 crisis.")
    warmth: int = Field(ge=0, le=10, description="0 cold or hostile, 10 tender or joyful.")
    reason: str = Field(description="One sentence explaining both scores.")
    evidence: list[int] = Evidence()


class CharactersOut(BaseModel):
    characters: list[Character] = Field(min_length=1)


class InteractionsOut(BaseModel):
    interactions: list[Interaction]


class SettingOut(BaseModel):
    places: list[Place]
    objects: list[Thing]


class EventsOut(BaseModel):
    events: list[Event] = Field(min_length=1, max_length=5, description="What happens, in order.")
    tone: Tone


class Fix(BaseModel):
    n: int = Field(description="The number of the item being fixed.")
    evidence: list[int] = Field(description="Sentence numbers that show the item, or [] to withdraw it.")


class Repairs(BaseModel):
    fixes: list[Fix]


def inline_schema(model: type[BaseModel]) -> dict:
    """JSON schema with $refs resolved, which small-model grammars handle more reliably."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)
