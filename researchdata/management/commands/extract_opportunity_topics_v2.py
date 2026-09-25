import html
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from django.core.management.base import BaseCommand, CommandError
from django.utils.html import strip_tags
from FlagEmbedding import BGEM3FlagModel

from researchdata.models import Opportunity


DEFAULT_OUTPUT = Path(
    "data/opportunity_topics/opportunity_topic_candidates_v2.json"
)

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.'/-]*")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+|\n+")
TITLE_SPLIT_RE = re.compile(r"\s*[:;]\s*|\s+[–—-]\s+")

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being",
    "by", "for", "from", "has", "have", "having", "in", "into",
    "is", "it", "its", "of", "on", "or", "that", "the", "their",
    "these", "this", "those", "to", "was", "were", "will", "with",
    "within", "without", "through", "using", "use", "used", "via",
    "may", "can", "could", "should", "would", "such", "than", "then",
    "also", "other", "including", "include", "includes", "which",
    "who", "whom", "whose", "where", "when", "while", "all", "any",
    "both", "each", "either", "more", "most", "some", "not", "no",
    "only", "our", "your", "they", "them", "we", "you",
}

ADMIN_WORDS = {
    "application", "applications", "applicant", "applicants",
    "award", "awards", "announcement", "announcements",
    "competition", "deadline", "deadlines", "eligible", "eligibility",
    "foa", "fund", "funding", "funds", "grant", "grants",
    "institution", "institutions", "mechanism", "mechanisms",
    "nofo", "opportunity", "opportunities", "program", "programs",
    "proposal", "proposals", "request", "requests", "submission",
    "submissions", "submit", "submitted", "recipient", "recipients",
    "information", "necessary", "type",
}

# Grant mechanism / trial-status vocabulary should not define the scientific
# subject area used for matching.
MECHANISM_WORDS = {
    "clinical", "trial", "optional", "required", "allowed",
    "independent", "parent", "limited",
    "r01", "r03", "r21", "r33", "r35", "r61",
    "u01", "p30", "k01", "k08", "k23", "k24", "k25", "k99",
    "r00",
}

ADMIN_PHRASE_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"\brequest for information\b",
        r"\bfunding opportunity\b",
        r"\bsubmit(?:ted)? application\b",
        r"\bapplications? (?:are|is|for|from)\b",
        r"\bclinical trial (?:optional|required|not allowed)\b",
        r"\bthis (?:nofo|foa)\b",
        r"\bthe (?:nofo|foa)\b",
        r"\bannouncement solicits applications\b",
        r"\btype 6 applications?\b",
        r"\bnotice of funding opportunity\b",
    ]
]

CODE_ONLY_TITLE_RE = re.compile(
    r"^(?:RFA|PA|PAR|PAS|NOT|NOFO)[-_A-Z0-9.]+$", re.I
)


def clean_text(value):
    if not value:
        return ""
    value = html.unescape(str(value))
    value = strip_tags(value)
    value = value.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def clean_phrase(value):
    value = re.sub(r"\s+", " ", value).strip()
    return value.strip(" \t\r\n.,;:()[]{}")


def norm_token(token):
    return token.lower().strip(" \t\r\n.,;:()[]{}'\"")


def canonicalize(value):
    return " ".join(
        t for t in (norm_token(x) for x in TOKEN_RE.findall(value)) if t
    )


def informative_tokens(value):
    tokens = [norm_token(t) for t in TOKEN_RE.findall(value)]
    return [
        t for t in tokens
        if t
        and t not in STOPWORDS
        and t not in ADMIN_WORDS
        and t not in MECHANISM_WORDS
    ]


def admin_fraction(value):
    tokens = [norm_token(t) for t in TOKEN_RE.findall(value)]
    content = [t for t in tokens if t and t not in STOPWORDS]
    if not content:
        return 1.0
    admin = sum(
        t in ADMIN_WORDS or t in MECHANISM_WORDS
        for t in content
    )
    return admin / len(content)


def has_admin_phrase(value):
    return any(pattern.search(value) for pattern in ADMIN_PHRASE_PATTERNS)


def usable_subject_phrase(value, allow_single=False):
    value = clean_phrase(value)
    if not value or has_admin_phrase(value):
        return False

    info = informative_tokens(value)
    if not info:
        return False

    words = TOKEN_RE.findall(value)
    if len(words) == 1 and not allow_single:
        return False

    if len(words) > 6:
        return False

    if admin_fraction(value) > 0.40:
        return False

    # A multiword phrase needs at least two informative content words.
    if len(words) > 1 and len(info) < 2:
        return False

    # Reject fragments consisting mostly of codes/numbers.
    alpha_info = [
        t for t in info if any(ch.isalpha() for ch in t)
    ]
    if not alpha_info:
        return False

    return True


def strip_mechanism_parentheticals(title):
    def repl(match):
        inner = match.group(1)
        lower = inner.lower()
        if (
            any(word in lower for word in MECHANISM_WORDS)
            or "clinical trial" in lower
        ):
            return " "
        return match.group(0)

    return re.sub(r"\(([^()]*)\)", repl, title)


def title_subject_segments(title):
    title = clean_text(title)
    if not title:
        return []

    if CODE_ONLY_TITLE_RE.match(title):
        return []

    title = strip_mechanism_parentheticals(title)

    # Remove common administrative title phrases without replacing the
    # remaining domain-bearing text.
    title = re.sub(
        r"\bRequest for Information\b", " ", title, flags=re.I
    )
    title = re.sub(
        r"\bFunding Opportunity Announcement\b", " ", title, flags=re.I
    )

    raw_segments = TITLE_SPLIT_RE.split(title)
    output = []

    for segment in raw_segments:
        segment = clean_phrase(segment)
        if not segment:
            continue

        # Also split long comma lists into coherent 2-6 word pieces later
        # through description n-grams, but retain the main title segment.
        if usable_subject_phrase(segment, allow_single=False):
            output.append(segment)

    return output


def description_candidates(description, min_n=2, max_n=5):
    counts = Counter()
    display = {}
    evidence = defaultdict(list)

    for sentence in SENTENCE_SPLIT_RE.split(description):
        sentence = clean_phrase(sentence)
        if not sentence:
            continue

        tokens = TOKEN_RE.findall(sentence)

        for n in range(min_n, max_n + 1):
            if len(tokens) < n:
                continue

            for i in range(len(tokens) - n + 1):
                phrase = clean_phrase(" ".join(tokens[i:i+n]))
                if not usable_subject_phrase(phrase):
                    continue

                canonical = canonicalize(phrase)
                if not canonical:
                    continue

                counts[canonical] += 1
                display.setdefault(canonical, phrase)

                if len(evidence[canonical]) < 3:
                    evidence[canonical].append(sentence)

    return counts, display, evidence


def normalize(values):
    values = np.asarray(values, dtype=np.float32)
    if len(values) == 0:
        return values
    lo = float(values.min())
    hi = float(values.max())
    if math.isclose(lo, hi):
        return np.ones_like(values)
    return (values - lo) / (hi - lo)


def normalize_vectors(matrix):
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms <= 0):
        raise ValueError("Zero-norm embedding encountered.")
    return matrix / norms


class Command(BaseCommand):
    help = (
        "Generate cleaner opportunity subject-area candidates using "
        "title subject segments, filtered description keyphrases, BGE-M3 "
        "semantic relevance, and MMR diversity. No database writes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=str(DEFAULT_OUTPUT),
        )
        parser.add_argument(
            "--candidate-limit",
            type=int,
            default=60,
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=8,
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=8,
        )
        parser.add_argument(
            "--threads",
            type=int,
            default=8,
        )
        parser.add_argument(
            "--max-length",
            type=int,
            default=1024,
        )
        parser.add_argument(
            "--sample",
            type=int,
            default=5,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def handle(self, *args, **options):
        opportunities = list(
            Opportunity.objects.all()
            .prefetch_related("topics", "domains")
            .order_by("opp_id")
        )
        if not opportunities:
            raise CommandError("No opportunities found.")

        prepared = []

        for opp in opportunities:
            title = clean_text(opp.title)
            description = clean_text(
                getattr(opp, "clean_description", "")
            ) or clean_text(opp.description)

            source_quality = (
                "insufficient"
                if len(description.split()) < 15
                else "limited"
                if len(description.split()) < 60
                else "usable"
            )

            segments = title_subject_segments(title)

            counts, displays, evidence = description_candidates(
                description
            )

            # Add title segments as high-value candidates.
            sources = defaultdict(set)
            for canonical in counts:
                sources[canonical].add("description")

            for segment in segments:
                canonical = canonicalize(segment)
                if canonical:
                    counts[canonical] += 2
                    displays.setdefault(canonical, segment)
                    sources[canonical].add("title")

            prepared.append(
                {
                    "opp": opp,
                    "title": title,
                    "description": description,
                    "source_quality": source_quality,
                    "counts": counts,
                    "displays": displays,
                    "evidence": evidence,
                    "sources": sources,
                }
            )

        # Cross-opportunity document frequency.
        df = Counter()
        for item in prepared:
            df.update(item["counts"].keys())

        n_docs = len(prepared)

        for item in prepared:
            lexical = []
            for canonical, tf in item["counts"].items():
                phrase = item["displays"][canonical]
                phrase_df = df[canonical]
                idf = math.log((n_docs + 1) / (phrase_df + 1)) + 1.0
                source_bonus = (
                    1.35 if "title" in item["sources"][canonical]
                    else 1.0
                )
                length = len(TOKEN_RE.findall(phrase))
                length_bonus = 1.0 + 0.08 * min(max(length - 2, 0), 3)

                score = (
                    math.log1p(tf)
                    * idf
                    * source_bonus
                    * length_bonus
                )

                lexical.append(
                    {
                        "canonical": canonical,
                        "phrase": phrase,
                        "term_frequency": int(tf),
                        "document_frequency": int(phrase_df),
                        "lexical_score": float(score),
                        "sources": sorted(
                            item["sources"][canonical]
                            or {"description"}
                        ),
                        "evidence_snippets": item["evidence"].get(
                            canonical, []
                        ),
                    }
                )

            lexical.sort(
                key=lambda x: (
                    -x["lexical_score"],
                    x["canonical"],
                )
            )
            item["lexical"] = lexical[:options["candidate_limit"]]

        self.stdout.write(
            f"Prepared {len(prepared)} opportunities from MySQL."
        )

        quality_counts = Counter(
            item["source_quality"] for item in prepared
        )
        self.stdout.write(
            "Source quality: "
            + ", ".join(
                f"{key}={value}"
                for key, value in sorted(quality_counts.items())
            )
        )

        if options["dry_run"]:
            for item in prepared[:options["sample"]]:
                opp = item["opp"]
                self.stdout.write(
                    f"\n{opp.opp_id} — {item['title']}"
                )
                self.stdout.write(
                    f"  source quality: {item['source_quality']}"
                )
                self.stdout.write(
                    f"  title subject segments: "
                    f"{title_subject_segments(item['title']) or 'none'}"
                )
                self.stdout.write("  filtered lexical candidates:")
                for row in item["lexical"][:10]:
                    self.stdout.write(
                        f"    {row['phrase']} "
                        f"[{','.join(row['sources'])}]"
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    "\nDry run passed: no model loaded, "
                    "no database changes, no output written."
                )
            )
            return

        torch.set_num_threads(options["threads"])
        self.stdout.write("\nLoading BGE-M3 on CPU (FP32)...")
        model = BGEM3FlagModel(
            "BAAI/bge-m3",
            use_fp16=False,
            devices=["cpu"],
        )

        anchors = []
        for item in prepared:
            # Give the title a clear lead while keeping the description
            # for semantic context.
            anchors.append(
                f"Opportunity subject: {item['title']}. "
                f"{item['description']}"
            )

        token_counts = [
            len(
                model.tokenizer(
                    text,
                    truncation=False,
                    add_special_tokens=True,
                )["input_ids"]
            )
            for text in anchors
        ]
        longest = max(token_counts)

        self.stdout.write(
            f"Longest opportunity anchor: {longest} tokens"
        )
        if longest > options["max_length"]:
            raise CommandError(
                f"Anchor exceeds --max-length: {longest}"
            )

        anchor_result = model.encode(
            anchors,
            batch_size=options["batch_size"],
            max_length=options["max_length"],
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        anchor_vectors = normalize_vectors(
            anchor_result["dense_vecs"]
        )

        all_canonicals = sorted(
            {
                row["canonical"]
                for item in prepared
                for row in item["lexical"]
            }
        )
        display_map = {}
        for item in prepared:
            for row in item["lexical"]:
                display_map.setdefault(
                    row["canonical"], row["phrase"]
                )

        phrase_texts = [
            display_map[c] for c in all_canonicals
        ]

        self.stdout.write(
            f"Encoding {len(phrase_texts)} unique subject candidates..."
        )

        phrase_result = model.encode(
            phrase_texts,
            batch_size=options["batch_size"],
            max_length=64,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        phrase_vectors = normalize_vectors(
            phrase_result["dense_vecs"]
        )
        phrase_index = {
            c: i for i, c in enumerate(all_canonicals)
        }

        records = {}

        for i, item in enumerate(prepared):
            opp = item["opp"]
            candidates = item["lexical"]

            # For extremely short code-only opportunities, do not fabricate
            # subject areas from boilerplate.
            if (
                item["source_quality"] == "insufficient"
                and not title_subject_segments(item["title"])
            ):
                selected = []
                review_flag = "insufficient_source_text"
            else:
                review_flag = None

                lexical_norm = normalize(
                    [c["lexical_score"] for c in candidates]
                )

                enriched = []
                for row, lex_norm in zip(
                    candidates, lexical_norm
                ):
                    idx = phrase_index[row["canonical"]]
                    semantic = float(
                        anchor_vectors[i] @ phrase_vectors[idx]
                    )

                    source_bonus = (
                        0.04 if "title" in row["sources"] else 0.0
                    )
                    relevance = (
                        0.82 * semantic
                        + 0.18 * float(lex_norm)
                        + source_bonus
                    )

                    enriched.append(
                        {
                            **row,
                            "semantic_similarity": round(
                                semantic, 6
                            ),
                            "lexical_score_normalized": round(
                                float(lex_norm), 6
                            ),
                            "relevance_score": round(
                                relevance, 6
                            ),
                            "_idx": idx,
                        }
                    )

                # MMR: preserve relevance while actively reducing near-
                # duplicate phrases from the same wording family.
                selected = []
                remaining = enriched[:]

                while remaining and len(selected) < options["top_k"]:
                    best = None
                    best_mmr = None

                    for row in remaining:
                        if not selected:
                            redundancy = 0.0
                        else:
                            v = phrase_vectors[row["_idx"]]
                            redundancy = max(
                                float(
                                    v
                                    @ phrase_vectors[s["_idx"]]
                                )
                                for s in selected
                            )

                        mmr = (
                            0.78 * row["relevance_score"]
                            - 0.22 * redundancy
                        )

                        if best is None or mmr > best_mmr:
                            best = row
                            best_mmr = mmr

                    best = dict(best)
                    best["mmr_score"] = round(
                        float(best_mmr), 6
                    )
                    selected.append(best)
                    remaining = [
                        r for r in remaining
                        if r["canonical"] != best["canonical"]
                    ]

            final = []
            for rank, row in enumerate(selected, start=1):
                row = dict(row)
                row.pop("_idx", None)
                row["rank"] = rank
                row["review_decision"] = None
                row["preferred_topic_label"] = None
                final.append(row)

            existing_topics = [
                {
                    "topic": t.topic,
                    "score": t.score,
                    "source": t.source,
                }
                for t in opp.topics.all().order_by(
                    "-score", "topic"
                )
            ]
            existing_domains = [
                {
                    "domain_name": d.domain_name,
                    "confidence_score": d.confidence_score,
                    "rationale": d.rationale,
                    "is_primary": d.is_primary,
                }
                for d in opp.domains.all().order_by(
                    "-is_primary",
                    "-confidence_score",
                    "domain_name",
                )
            ]

            records[str(opp.opp_id)] = {
                "opportunity_id": int(opp.opp_id),
                "title": item["title"],
                "description_word_count": len(
                    item["description"].split()
                ),
                "source_quality": item["source_quality"],
                "review_flag": review_flag,
                "title_subject_segments": title_subject_segments(
                    item["title"]
                ),
                "existing_topics_reference_only": existing_topics,
                "existing_domains_reference_only": existing_domains,
                "candidate_topics": final,
            }

        output = {
            "method": (
                "filtered subject keyphrases + title subject segments + "
                "BGE-M3 relevance + MMR diversity"
            ),
            "model": "BAAI/bge-m3",
            "candidate_only": True,
            "database_modified": False,
            "opportunity_count": len(records),
            "top_k": options["top_k"],
            "records": records,
        }

        output_path = Path(options["output"])
        output_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(
                output,
                f,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSaved refined candidates for "
                f"{len(records)} opportunities to {output_path}"
            )
        )

        self.stdout.write("\nSample refined candidates:")
        for item in prepared[:options["sample"]]:
            record = records[str(item["opp"].opp_id)]
            self.stdout.write(
                f"\n{record['opportunity_id']} — "
                f"{record['title']}"
            )
            self.stdout.write(
                f"  source quality: {record['source_quality']}"
            )
            if record["review_flag"]:
                self.stdout.write(
                    f"  review flag: {record['review_flag']}"
                )
            for topic in record["candidate_topics"]:
                self.stdout.write(
                    f"  {topic['rank']}. "
                    f"{topic['phrase']} "
                    f"(rel={topic['relevance_score']:.4f}, "
                    f"mmr={topic['mmr_score']:.4f})"
                )
