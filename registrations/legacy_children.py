import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedLegacyChildren:
    ages: tuple[int | None, ...]
    needs_manual_review: bool


_CHILD_COUNT_RE = re.compile(
    r"(?P<count>\d+)\s*(?:реб(?:[её]н(?:ок|ка|ку|ком|ке))?|дет(?:ей|и|ям|ьми)?)",
    re.IGNORECASE,
)
_WORD_CHILD_COUNT_RE = re.compile(
    r"\b(?P<count_word>один|одна|одно|двое|трое)\s+(?:реб[её]нок|дет(?:ей|и))",
    re.IGNORECASE,
)
_WORD_COUNTS = {"один": 1, "одна": 1, "одно": 1, "двое": 2, "трое": 3}
_AGE_EXPRESSION_RE = re.compile(
    r"(?P<ages>\d{1,2}(?:\s*(?:,|и)\s*\d{1,2})*)\s*(?:лет|год|года)\b",
    re.IGNORECASE,
)
_SAFE_TRAILING_AGES_RE = re.compile(
    r"^\s*[:,;\-]?\s*(?P<ages>\d{1,2}(?:\s*(?:,|и)\s*\d{1,2})*)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\d+")
_ONLY_NUMBER_RE = re.compile(r"^\s*(?P<count>[12])\s*$")
_TEAM_CHILDREN_RE = re.compile(r"дети\s+в\s+команде", re.IGNORECASE)


def parse_legacy_children_details(value: str) -> ParsedLegacyChildren:
    """Conservatively extract child rows from historical free text."""
    text = (value or "").strip()
    if not text:
        return ParsedLegacyChildren((), False)

    if _TEAM_CHILDREN_RE.search(text):
        return ParsedLegacyChildren((), True)

    count_match = _CHILD_COUNT_RE.search(text)
    word_count_match = _WORD_CHILD_COUNT_RE.search(text)
    only_number_match = _ONLY_NUMBER_RE.fullmatch(text)
    if count_match:
        explicit_count = int(count_match.group("count"))
        matched_count = count_match
    elif word_count_match:
        explicit_count = _WORD_COUNTS[word_count_match.group("count_word").lower()]
        matched_count = word_count_match
    elif only_number_match:
        explicit_count = int(only_number_match.group("count"))
        matched_count = only_number_match
    else:
        explicit_count = None
        matched_count = None

    ages: list[int] = []
    for age_match in _AGE_EXPRESSION_RE.finditer(text):
        ages.extend(
            number
            for number in (
                int(raw) for raw in _NUMBER_RE.findall(age_match.group("ages"))
            )
            if 0 <= number <= 17
        )

    if not ages and matched_count is not None and (count_match or word_count_match):
        trailing_match = _SAFE_TRAILING_AGES_RE.fullmatch(
            text[matched_count.end() :]
        )
        if trailing_match:
            ages = [
                number
                for number in (
                    int(raw)
                    for raw in _NUMBER_RE.findall(trailing_match.group("ages"))
                )
                if 0 <= number <= 17
            ]

    if explicit_count is None:
        return ParsedLegacyChildren(tuple(ages), not bool(ages))

    target_count = max(explicit_count, len(ages))
    mismatch = len(ages) != explicit_count
    padded: list[int | None] = list(ages)
    padded.extend([None] * (target_count - len(padded)))
    return ParsedLegacyChildren(tuple(padded), mismatch or any(age is None for age in padded))
