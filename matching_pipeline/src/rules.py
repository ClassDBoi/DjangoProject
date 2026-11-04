"""Rule-based filter for terms that are funding/administrative language or organization names.

The patterns are written from the categories the generator and judge instructions already exclude
(funding mechanisms, administration, eligibility, organizations), not from specific reviewed terms.
A match flags a term as not useful for expertise matching. It never adds terms.
"""
from __future__ import annotations

import re

# NIH/NSF-style activity codes (R01, K99, U01, P30, F31, T32, R61/R33 ...) and small-business programs.
# A fixed list, so gene/cell-line names such as p53 or U87 are not caught.
_CODES = ("R00 R01 R03 R13 R15 R21 R24 R25 R33 R34 R35 R37 R41 R42 R43 R44 R56 R61 "
          "K01 K02 K05 K07 K08 K12 K18 K22 K23 K24 K25 K26 K43 K76 K99 "
          "U01 U10 U19 U24 U2C U54 UG3 UH3 UM1 P01 P20 P30 P50 F30 F31 F32 T32 T35 DP1 DP2 DP5 S10")
_ACTIVITY_CODE = re.compile(r"\b(?:" + "|".join(_CODES.split()) + r")\b|\b(?:SBIR|STTR)\b", re.I)

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("funding mechanism code", _ACTIVITY_CODE),
    ("funding or award language", re.compile(
        r"\b(?:grants?|funding|funded|awards?|awardees?|budgets?|cost[- ]?(?:sharing|matching)|"
        r"indirect costs?|stipends?|salary|appropriations?|solicitations?|announcements?|"
        r"cooperative agreements?|subawards?|renewals?|resubmissions?)\b", re.I)),
    ("administrative requirement", re.compile(
        r"\b(?:milestones?|timelines?|deliverables?|progress reports?|applicants?|grant applications?|"
        r"proposals?|submissions?|deadlines?|letters? of intent|review criteria|peer review process|"
        r"data (?:sharing|management) plans?|phase (?:i|ii|iii|1|2|3)\b(?! (?:clinical )?trials?))\b",
        re.I)),
    ("eligibility language", re.compile(
        r"\b(?:eligib\w*|recipients?|early[- ]career|new investigators?|career development awards?|"
        r"principal investigators?|institutional (?:eligibility|support|commitment))\b", re.I)),
    ("organization or program name", re.compile(
        r"\b(?:consortium|consortia|institute|institutes|agency|agencies|department of|office of|"
        r"university|universities|centers? for|centres? for|"
        r"program|programs|programme|initiative)\b|\b(?:NIH|NSF|NASA|DOE|DOD|USDA|CDC|FDA|EPA|NIST|NOAA|DARPA|"
        r"NIDDK|NCI|NIMH|NIGMS|NIBIB|NCCIH|NHLBI|NIAID|USAID|BLM)\b", re.I)),
    ("website or resource", re.compile(r"\b(?:websites?|web pages?|portals?|webinars?|listservs?)\b", re.I)),
]


def flag_reason(term: str) -> str | None:
    """Return why a term looks like funding/administrative language or an organization, else None."""
    text = str(term or "")
    for reason, pattern in _PATTERNS:
        if pattern.search(text):
            return reason
    return None


# Career-stage and award-type language. Not science, but useful later for the eligibility layer
# (e.g. "postdoctoral" or "early-stage investigator" awards), so matching sets it aside instead of
# dropping it silently. Used on opportunity topics only.
_CAREER = re.compile(
    r"\b(?:post-?doctoral|postdocs?|tenure[- ]track|faculty positions?|career (?:development|transition)|"
    r"mentored (?:research|career)|mentorship|mentoring|research training|trainees?|training programs?|"
    r"independen(?:t|ce) (?:research|investigator|faculty|career)|transition to independence|"
    r"early[- ]stage investigators?|new investigators?|junior (?:faculty|investigators?)|"
    r"mid-?career|physician[- ]scientists?|dissertation|graduate students?|medical students?|"
    r"scholars?(?: program)?|fellowships?|interns?(?:hips?)?|lead investigator|principal investigator)\b", re.I)


def career_stage_reason(term: str) -> str | None:
    """Return 'career stage or training' when a topic describes who can apply rather than the science."""
    return "career stage or training" if _CAREER.search(str(term or "")) else None
