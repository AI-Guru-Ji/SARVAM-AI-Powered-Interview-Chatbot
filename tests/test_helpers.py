"""Tests for utils.helpers."""

from __future__ import annotations

from utils.helpers import (
    ascii_safe,
    coerce_str_list,
    extract_contact_from_transcripts,
    extract_phone_and_email,
    parse_json_lenient,
    strip_code_fences,
)


# ──────────────────────────────────────────────────────────────────────
# extract_phone_and_email
# ──────────────────────────────────────────────────────────────────────
class TestExtractPhoneAndEmail:
    def test_extracts_both(self):
        phone, email = extract_phone_and_email(
            "मेरा नाम विजय है, मोबाइल नंबर 9876543210 और ईमेल vijay@example.com है"
        )
        assert phone == "9876543210"
        assert email == "vijay@example.com"

    def test_handles_plus_91_prefix_and_spaces(self):
        phone, email = extract_phone_and_email("Phone +91 98765 43210")
        assert phone == "9876543210"
        assert email is None

    def test_handles_dashes(self):
        phone, _ = extract_phone_and_email("mera number 98765-43210")
        assert phone == "9876543210"

    def test_returns_none_when_missing(self):
        phone, email = extract_phone_and_email("no contact info here")
        assert phone is None
        assert email is None

    def test_empty_text(self):
        assert extract_phone_and_email("") == (None, None)
        assert extract_phone_and_email(None) == (None, None)  # type: ignore[arg-type]

    # ── Spoken email patterns (STT writes "at" / "dot" instead of @ / .) ─
    def test_spoken_email_at_and_dot(self):
        _, email = extract_phone_and_email(
            "my email is devesh at gmail dot com"
        )
        assert email == "devesh@gmail.com"

    def test_spoken_email_at_the_rate(self):
        # "at the rate" is a very common Indian English speech idiom for @.
        _, email = extract_phone_and_email(
            "ramesh at the rate yahoo dot co dot in"
        )
        assert email == "ramesh@yahoo.co.in"

    def test_spoken_email_with_devanagari_at_dot(self):
        # Real-world emails are almost always Latin-script. The point of
        # this test is that the function doesn't crash on mixed scripts
        # and that the "@" / "." reconstruction works for ASCII portions.
        _, email = extract_phone_and_email("vijay ऐट gmail डॉट com")
        # The "@gmail.com" portion must reconstruct cleanly.
        assert email is not None
        assert email.endswith("@gmail.com")

    # ── Digit-word phone patterns (STT writes spoken numbers as words) ──
    def test_phone_english_digit_words(self):
        phone, _ = extract_phone_and_email(
            "my number is nine eight seven six five four three two one zero"
        )
        assert phone == "9876543210"

    def test_phone_mixed_words_and_digits(self):
        # Partial digit-word transcription happens often.
        phone, _ = extract_phone_and_email(
            "my mobile is nine eight seven 6 5 4 3 2 1 0"
        )
        assert phone == "9876543210"

    def test_phone_hindi_digit_words(self):
        phone, _ = extract_phone_and_email(
            "मेरा नंबर नौ आठ सात छह पांच चार तीन दो एक शून्य है"
        )
        assert phone == "9876543210"

    def test_phone_with_plus_91_prefix_and_words(self):
        phone, _ = extract_phone_and_email(
            "plus 9 1 nine eight seven six five four three two one zero"
        )
        assert phone == "9876543210"

    # ── Combined real-world demo answer ─────────────────────────────────
    def test_real_world_q1_answer_devesh(self):
        # Mirrors the actual Q1 transcript that produced an empty header
        # in the user's last demo screenshot.
        phone, email = extract_phone_and_email(
            "my name is Devesh Singh, my mobile number is "
            "nine eight seven six five four three two one zero, "
            "and my email is devesh dot singh at gmail dot com"
        )
        assert phone == "9876543210"
        assert email == "devesh.singh@gmail.com"


# ──────────────────────────────────────────────────────────────────────
# extract_contact_from_transcripts — scans every answer, not just Q1
# ──────────────────────────────────────────────────────────────────────
class TestExtractContactFromTranscripts:
    def test_finds_phone_in_q1_email_in_q2(self):
        # Sometimes STT splits "mobile" into one answer and "email" into
        # the next (e.g. when the candidate paused mid-sentence).
        phone, email = extract_contact_from_transcripts([
            "Devesh Singh, mobile 9876543210",
            "my email is devesh at gmail dot com",
            None,
        ])
        assert phone == "9876543210"
        assert email == "devesh@gmail.com"

    def test_returns_none_when_no_contact_anywhere(self):
        assert extract_contact_from_transcripts(
            ["just some text", "no contact here", None]
        ) == (None, None)

    def test_skips_none_entries(self):
        # Should not crash on None / empty answers in the list.
        phone, email = extract_contact_from_transcripts([
            None, "", "  ", "phone 9876543210", None,
        ])
        assert phone == "9876543210"


# ──────────────────────────────────────────────────────────────────────
# JSON helpers
# ──────────────────────────────────────────────────────────────────────
class TestStripCodeFences:
    def test_removes_triple_backticks(self):
        text = "```json\n{\"a\": 1}\n```"
        assert strip_code_fences(text) == '{"a": 1}'

    def test_passthrough_when_no_fence(self):
        text = '{"a": 1}'
        assert strip_code_fences(text) == '{"a": 1}'


class TestParseJsonLenient:
    def test_parses_clean_json(self):
        assert parse_json_lenient('{"a": 1}') == {"a": 1}

    def test_strips_fences_first(self):
        assert parse_json_lenient('```\n{"a": 1}\n```') == {"a": 1}

    def test_handles_prose_around_json(self):
        text = 'Here is the JSON: {"a": 1, "b": 2}. Hope it helps!'
        assert parse_json_lenient(text) == {"a": 1, "b": 2}

    def test_returns_none_on_unparseable(self):
        assert parse_json_lenient("not json at all") is None


# ──────────────────────────────────────────────────────────────────────
# coerce_str_list — the "one bullet per character" bug fix
# ──────────────────────────────────────────────────────────────────────
class TestCoerceStrList:
    def test_passthrough_for_list(self):
        assert coerce_str_list(["a", "b"]) == ["a", "b"]

    def test_wraps_single_string_in_one_element_list(self):
        # Critical: prevents iterating a string char-by-char.
        assert coerce_str_list("one sentence") == ["one sentence"]

    def test_splits_string_with_newlines(self):
        text = "first\nsecond\nthird"
        assert coerce_str_list(text) == ["first", "second", "third"]

    def test_filters_empty_strings_from_list(self):
        assert coerce_str_list(["a", "", "b", "   "]) == ["a", "b"]

    def test_handles_none(self):
        assert coerce_str_list(None) == []


# ──────────────────────────────────────────────────────────────────────
# ascii_safe — PDF safety
# ──────────────────────────────────────────────────────────────────────
class TestAsciiSafe:
    def test_replaces_em_dash(self):
        assert "—" not in ascii_safe("hello — world")

    def test_replaces_curly_quotes(self):
        assert ascii_safe('“quoted”') == '"quoted"'

    def test_replaces_rupee_symbol(self):
        assert "₹" not in ascii_safe("₹500")

    def test_passes_through_ascii(self):
        assert ascii_safe("simple ascii text") == "simple ascii text"
