"""Section-aware filtering of funding announcements.

Announcements come from several agencies (NIH, NSF, DOE, DOI/BLM, DOJ/OJJDP, USAID) with different
layouts, so this does not rely on one template. It finds heading lines, labels each heading as
scientific ("keep"), administrative ("drop") or neutral (inherits the current state), and keeps only
text under scientific headings. Every decision is recorded so the team can check it.

Rules of thumb that the heading patterns encode:
- Strong headings start a top-level part: "Section II. Award Information", "III. Award Information",
  "Part 2", NIH "Funding Opportunity Purpose", OJJDP-style "B. Federal Award Information", "## ..." lines.
- Weak headings are short standalone lines such as "Background", "Program Objectives", "Eligibility".
- Attachments, appendices and annexes end the scientific text once some text has been kept
  (proposal templates in attachments repeat "Purpose/Objectives" headings as instructions).
- Tables of contents produce headings with no text between them, so they keep nothing.
"""
from __future__ import annotations

import re

KEEP, DROP, NEUTRAL, STOP = "keep", "drop", "neutral", "stop"

# Checked before the keep words: a heading that mentions any of these is administrative.
_DROP_WORDS = re.compile(
    r"award information|federal award|award administration|award notices?|award conditions|"
    r"eligib|application and submission|submission|how to apply|proposal preparation|"
    r"application review|review (?:and selection|information|criteria|process|procedures)|merit review|"
    r"selection process|evaluation criteria|reporting|agency contacts?|contact information|contacts?\b|"
    r"other information|budget|cost[- ]sharing|cost sharing|funding restrictions|estimated funding|"
    r"deadlines?|due dates?|key dates|closing date|dates and times|table of contents|^contents$|"
    r"definitions|term of agreement|certification|registration|intergovernmental|"
    r"terms and conditions|policy requirements|statutory authority|applicable regulations|"
    r"authority and regulations|^authority\b|updates and reminders|glossary|page limit|"
    r"performance measures|application checklist|fastlane|grants\.gov|^questions$|questions/|overview information",
    re.I)
_KEEP_WORDS = re.compile(
    r"purpose|goals?\b|background|introduction|overview|summary|synopsis|program description|"
    r"funding opportunity description|project description|objectives?|research|scientific|technical approach|"
    r"scope|areas? of (?:interest|emphasis|focus)|priorit|topics?|program-specific|supplementary information|"
    r"statement of work|themes?|specific aims|description",
    re.I)
_END_WORDS = re.compile(r"^(?:attachment|appendix|appendices|annex|exhibit)\b|appendices", re.I)

_ROMAN = r"(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)"
_STRONG = [
    re.compile(rf"^(?:section|part)\s+(?:{_ROMAN}|\d+)\b[.:\s–—-]*(.*)$", re.I),
    re.compile(rf"^{_ROMAN}\.\s+([A-Z].*)$"),
    re.compile(r"^(Funding Opportunity (?:Purpose|Goal\(s\)|Goals?|Description))\s*$", re.I),
]
_LETTERED = re.compile(r"^[A-H]\.\s+(.+)$")
_TOP_LETTERED = re.compile(
    r"^(program description|federal award information|award information|eligibility information|"
    r"application and submission information|application review information|"
    r"federal award administration information|award administration information|"
    r"federal awarding agency contact|agency contacts?|other information)", re.I)
_SMALL = {"and", "or", "of", "the", "for", "to", "in", "with", "on", "by", "a", "an", "as", "at", "from"}
_TRAILING_FUNCTION_WORD = re.compile(r"\b(?:and|or|of|the|for|to|in|with|on|by|a|an|as|at|from|that|is|are)$", re.I)


def _strip(line: str) -> str:
    return line.strip().strip(":").strip()


def _titleish(text: str) -> bool:
    """Headings are Title Case or UPPER CASE; wrapped sentences are mostly lowercase."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'/-]*", text) if w.lower() not in _SMALL]
    return not words or sum(w[0].isupper() for w in words) / len(words) >= 0.6


def _label(t: str) -> str:
    if _END_WORDS.search(t):
        return STOP
    if _DROP_WORDS.search(t):
        return DROP
    if _KEEP_WORDS.search(t):
        return KEEP
    return NEUTRAL


def classify_heading(line: str, after_break: bool = True) -> tuple[str, str] | None:
    """Return (strength, label) for a heading line, or None if the line is body text.
    strength is 'strong' (top-level part) or 'weak' (sub-heading); label is keep/drop/neutral/stop."""
    text = _strip(line)
    hashed = text.startswith("#")
    if hashed:                      # "## ..." marks a heading of unknown level in PDF conversions
        text = _strip(text.lstrip("#"))
    words = text.split()
    if not text or len(words) > 16 or len(text) > 140:
        return None
    for pat in _STRONG:
        m = pat.match(text)
        if m:
            inner = (m.group(1) if m.groups() else "") or text
            if len(words) <= 14 and _titleish(inner):
                return "strong", _label(inner)
            return None
    m = _LETTERED.match(text)
    if m and _TOP_LETTERED.match(m.group(1)):
        return "strong", _label(m.group(1))
    if _END_WORDS.search(text) and len(words) <= 6 and _titleish(text):
        return "strong", STOP
    # Weak headings: short title-like lines. Unless marked with "##", only after a blank line or a
    # finished sentence, so wrapped body lines are not mistaken for headings.
    limit = 12 if hashed else 8
    if ((hashed or after_break) and len(words) <= limit and not text.endswith((".", ",", ";"))
            and text[:1].isupper() and not _TRAILING_FUNCTION_WORD.search(text)):
        lab = _label(text)
        if lab != NEUTRAL:
            return "weak", lab
    return None


_JUNK = re.compile(r"^(?:[\d\s.,%$()/+\-–—:;#]+|https?://\S+|\S+@\S+|page \d+.*|\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}.*)$",
                   re.I)


def _is_junk(line: str) -> bool:
    t = line.strip()
    if not t or _JUNK.match(t) or "....." in t:       # dotted leaders = table-of-contents entries
        return True
    letters = sum(c.isalpha() for c in t)
    return letters < 0.4 * len(t)


def split_announcement(text: str, min_keep_words: int = 200) -> dict:
    """Return {"kept_text", "kept_words", "front_words", "sections": [...]}.

    State rules: a strong heading sets the state (keep/drop); a neutral strong heading keeps it.
    A weak heading can switch keep/drop only while the enclosing strong part is not administrative,
    so "Research Strategy" inside the application instructions does not re-enable keeping.
    An attachment/appendix heading ends the scientific text once enough has been kept; before that
    (for example inside a table of contents) it just resets to front matter.
    """
    lines = text.splitlines()
    state = strong_state = "front"
    kept_lines: list[str] = []
    front_lines: list[str] = []
    current = {"heading": "(front matter)", "line": 0, "strength": "", "label": "", "decision": "drop", "words": 0}
    sections = [current]
    stopped = False
    prev = ""
    stripped = [l.strip() for l in lines]
    next_text = [""] * len(stripped)
    upcoming = ""
    for k in range(len(stripped) - 1, -1, -1):
        next_text[k] = upcoming
        if stripped[k]:
            upcoming = stripped[k]
    for i, line in enumerate(stripped):
        prev_line = prev
        after_break = (not prev or prev.endswith((".", ":", ";", "!", "?")) or prev.startswith("---")
                       or _is_junk(prev) or bool(classify_heading(prev)))
        prev = line
        if not line:
            continue
        head = None if stopped else classify_heading(line)
        # A heading-like line inside a sentence is a cross-reference ("see Section IV. Application and
        # Submission Information for details"), common where HTML links became separate lines.
        heading_like_prev = bool(prev_line) and len(prev_line.split()) <= 16 and _titleish(prev_line)
        excused = line.startswith("#") or (head is not None and heading_like_prev and
                                           (head[0] == "strong" or len(line.split()) <= 4))
        if head and ((not after_break and not excused) or re.match(r"^[a-z.,;:)\]]", next_text[i])):
            head = None
        if head:
            strength, lab = head
            ignored = False
            if strength == "strong":
                if lab == STOP:
                    if sum(len(l.split()) for l in kept_lines) >= min_keep_words:
                        stopped, state, strong_state = True, DROP, DROP
                    else:
                        state = strong_state = "front"
                elif lab in (KEEP, DROP):
                    state = strong_state = lab
            elif strong_state == DROP:
                ignored = True
            else:
                state = lab
            current = {"heading": line[:120], "line": i, "strength": strength,
                       "label": lab + (" (ignored: inside an administrative part)" if ignored else ""),
                       "decision": "keep" if state == KEEP else "drop", "words": 0}
            sections.append(current)
            if state == KEEP:
                kept_lines.append(line)
            continue
        if _is_junk(line):
            continue
        current["words"] += len(line.split())
        if state == KEEP:
            kept_lines.append(line)
        elif state == "front":
            front_lines.append(line)
    kept_text = "\n".join(kept_lines)
    return {"kept_text": kept_text, "kept_words": len(kept_text.split()),
            "front_words": sum(len(l.split()) for l in front_lines),
            "sections": [s for s in sections if s["words"] or s["decision"] == "keep"]}
