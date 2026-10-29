"""Unit tests for request validation rules (Phase 0 Q12): no database needed."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from idea_board.api.schemas import IdeaCreate


def test_content_is_trimmed() -> None:
    assert IdeaCreate.model_validate({"content": "  hello  "}).content == "hello"


@pytest.mark.parametrize("bad", ["", "   ", "\n\t "])
def test_empty_or_whitespace_is_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        IdeaCreate.model_validate({"content": bad})


def test_500_chars_accepted_501_rejected() -> None:
    assert len(IdeaCreate.model_validate({"content": "a" * 500}).content) == 500
    with pytest.raises(ValidationError):
        IdeaCreate.model_validate({"content": "a" * 501})


def test_length_counts_unicode_characters_not_bytes() -> None:
    # 500 emoji = 500 characters (2000 bytes in UTF-8) → accepted, same as PG char_length.
    assert len(IdeaCreate.model_validate({"content": "💡" * 500}).content) == 500


@pytest.mark.parametrize("bad", [123, None, ["x"], {"a": 1}, True])
def test_non_string_is_rejected_not_coerced(bad: object) -> None:
    with pytest.raises(ValidationError):
        IdeaCreate.model_validate({"content": bad})


def test_missing_content_is_rejected() -> None:
    with pytest.raises(ValidationError):
        IdeaCreate.model_validate({})


def test_extra_fields_are_ignored() -> None:
    assert IdeaCreate.model_validate({"content": "x", "author": "me"}).model_dump() == {
        "content": "x"
    }
