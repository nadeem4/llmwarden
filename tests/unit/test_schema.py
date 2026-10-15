import pytest
from pydantic import BaseModel

from llmwarden.schema import parse, prompt_for
from llmwarden.types import InvalidOutput


class Ranking(BaseModel):
    order: list[int]


def test_prompt_mentions_json_and_contains_schema_fields():
    p = prompt_for(Ranking)
    assert "JSON" in p and '"order"' in p and "array" in p


def test_parse_plain_json():
    assert parse('{"order": [2, 1]}', Ranking, provider="fake").order == [2, 1]


def test_parse_strips_code_fence():
    text = '```json\n{"order": [1]}\n```'
    assert parse(text, Ranking, provider="fake").order == [1]


def test_parse_failure_is_invalid_output_with_text():
    with pytest.raises(InvalidOutput) as info:
        parse('{"order": "nope"}', Ranking, provider="fake")
    assert info.value.text == '{"order": "nope"}' and info.value.provider == "fake"
