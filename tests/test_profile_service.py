"""Tests for ProfileService (deterministic; no LLM).

The compound profile questions (contact_info, location_and_age, family)
were split — there are now 13 fields. Tests reference QUESTION_FIELD_ORDER
directly instead of hard-coding field names, so future re-orderings won't
silently rot the suite.
"""

from __future__ import annotations

from constants.app_constants import QUESTION_FIELD_ORDER
from services.profile_service import ProfileService


# 13 sample Q&A pairs, one per slot in QUESTION_FIELD_ORDER:
#  name / mobile / age / location / documents / languages /
#  marital_status / dependents / experience_years / experience /
#  education / salary / availability
# (email was removed from profile-building — collected via WhatsApp/SMS instead.)
_SAMPLE_ANSWERS = [
    "Kamlesh Kumar",                   # name
    "9876543210",                      # mobile
    "35",                              # age
    "Gorakhpur",                       # location
    "Yes, Aadhaar and Driving Licence",  # documents
    "Hindi, English",                  # languages
    "Yes, married",                    # marital_status
    "Two children, mother",            # dependents
    "4 years",                         # experience_years
    "Hotel Taj for 3 years",           # experience
    "12th pass",                       # education
    "15000 expected, 12000 last",      # salary
    "Next week, will relocate",        # availability
]


def test_builds_profile_with_all_answers(settings):
    service = ProfileService(settings)
    qa_pairs = [
        (f"q{i+1}", answer) for i, answer in enumerate(_SAMPLE_ANSWERS)
    ]
    profile = service.build_profile(
        candidate_name="Kamlesh",
        role="housekeeping",
        language="hi",
        qa_pairs=qa_pairs,
    )

    assert profile.name == "Kamlesh"
    assert profile.applied_role == "housekeeping"
    assert profile.language == "hi"
    # Length must match the canonical field order — drives the whole pipeline.
    assert len(profile.answers) == len(QUESTION_FIELD_ORDER)
    assert list(profile.answers.keys()) == list(QUESTION_FIELD_ORDER)
    # First answer maps to the first field.
    first_field = QUESTION_FIELD_ORDER[0]
    assert profile.answers[first_field].answer == _SAMPLE_ANSWERS[0]
    assert service.count_populated_fields(profile) == len(QUESTION_FIELD_ORDER)


def test_empty_answers_become_none(settings):
    service = ProfileService(settings)
    qa_pairs = (
        [("q1", "real answer")]
        + [(f"q{i}", "") for i in range(2, len(QUESTION_FIELD_ORDER) + 1)]
    )
    profile = service.build_profile(
        candidate_name="A", role="housekeeping", language="en", qa_pairs=qa_pairs,
    )
    first_field = QUESTION_FIELD_ORDER[0]
    assert profile.answers[first_field].answer == "real answer"
    populated = service.count_populated_fields(profile)
    assert populated == 1


def test_ignores_extra_qa_pairs(settings):
    service = ProfileService(settings)
    # Pass more pairs than fields — only the first N should map.
    n = len(QUESTION_FIELD_ORDER)
    qa_pairs = [(f"q{i}", f"a{i}") for i in range(n + 7)]
    profile = service.build_profile(
        candidate_name="A", role="housekeeping", language="en", qa_pairs=qa_pairs,
    )
    assert len(profile.answers) == n
