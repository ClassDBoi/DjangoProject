"""Build reviewed researcher expertise profiles from paper keywords.

Run:
    python manage.py build_researcher_expertise --dry-run --sample 5
    python manage.py build_researcher_expertise

This command only READS MySQL and writes a local JSON review artifact.
It does not change ResearcherExpertise or any other database table.
"""

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from researchdata.models import Researcher
from researchdata.management.commands.preview_researcher_expertise import (
    canonical_keyword,
    collect_researchers,
    compact_join,
)


def load_decisions(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("decisions")
    if not isinstance(rows, list):
        raise ValueError("Decision file must contain a top-level 'decisions' list.")
    if data.get("total_candidate_pairs") != len(rows):
        raise ValueError("Decision-file count does not match the decisions list.")

    by_researcher = defaultdict(list)
    seen = set()
    for item in rows:
        pair_id = str(item.get("pair_id") or "").strip()
        researcher_id = str(item.get("researcher_id") or "").strip()
        decision = item.get("decision")
        if not pair_id or not researcher_id:
            raise ValueError("Each decision needs pair_id and researcher_id.")
        if pair_id in seen:
            raise ValueError(f"Duplicate pair_id in decisions file: {pair_id}")
        seen.add(pair_id)
        if decision not in {"same_topic", "related_distinct", "unrelated"}:
            raise ValueError(f"Invalid decision for {pair_id}: {decision}")
        if decision == "same_topic" and not str(item.get("effective_preferred_label") or "").strip():
            raise ValueError(f"same_topic pair {pair_id} has no effective preferred label")
        by_researcher[researcher_id].append(item)

    policy = data.get("duplicate_paper_policy", {})
    if not policy.get("treat_as_distinct_until_client_confirmation"):
        raise ValueError("Duplicate-paper policy differs from the approved review policy.")
    return data, by_researcher


def merge_reviewed_terms(person, decisions):
    """Apply only approved same_topic relationships for one researcher.

    Evidence is deduplicated by paper ID. If two merged aliases appear in the
    same paper, that paper contributes once and the highest keyword score from
    that cluster is used for that paper.
    """
    terms = person["terms"]
    parent = {term: term for term in terms}

    def find(term):
        if term not in parent:
            raise ValueError(f"Reviewed term not found in live MySQL for {person['id']}: {term}")
        if parent[term] != term:
            parent[term] = find(parent[term])
        return parent[term]

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        # deterministic component root
        if ra > rb:
            ra, rb = rb, ra
        parent[rb] = ra

    # Validate all reviewed phrases first so stale decision files fail loudly.
    for item in decisions:
        a = canonical_keyword(item["term_a"])
        b = canonical_keyword(item["term_b"])
        if a not in terms or b not in terms:
            raise ValueError(
                f"{person['id']} {item['pair_id']}: reviewed keyword not found in live MySQL"
            )
        if item["decision"] == "same_topic":
            union(a, b)

    members = defaultdict(list)
    for term in terms:
        members[find(term)].append(term)

    # Map same-topic review rows to their final connected component.
    same_by_root = defaultdict(list)
    for item in decisions:
        if item["decision"] == "same_topic":
            root = find(canonical_keyword(item["term_a"]))
            same_by_root[root].append(item)

    grouped = []
    for root, aliases in members.items():
        aliases = sorted(aliases)
        merge_items = same_by_root.get(root, [])

        if merge_items:
            labels = {str(x["effective_preferred_label"]).strip() for x in merge_items}
            if len(labels) != 1:
                raise ValueError(
                    f"{person['id']}: inconsistent effective labels for merged group {aliases}: {labels}"
                )
            topic_label = next(iter(labels))
        else:
            # No semantic merge: retain the most common original display spelling.
            spelling_counts = Counter()
            for alias in aliases:
                spelling_counts.update(person["labels"][alias])
            topic_label = sorted(
                spelling_counts.items(),
                key=lambda x: (-x[1], len(x[0]), x[0].casefold()),
            )[0][0]

        evidence_by_paper = defaultdict(
            lambda: {"paper_id": None, "paper_title": "", "source_keywords": []}
        )
        for alias in aliases:
            for paper_id, paper in terms[alias].items():
                entry = evidence_by_paper[paper_id]
                entry["paper_id"] = paper_id
                entry["paper_title"] = paper["paper_title"]
                # Keep the representative original spelling for this exact alias.
                raw_label = sorted(
                    person["labels"][alias].items(),
                    key=lambda x: (-x[1], len(x[0]), x[0].casefold()),
                )[0][0]
                entry["source_keywords"].append({
                    "keyword": raw_label,
                    "keyword_score": paper["keyword_score"],
                })

        evidence = sorted(evidence_by_paper.values(), key=lambda x: int(x["paper_id"]))
        for entry in evidence:
            entry["source_keywords"].sort(key=lambda x: x["keyword"].casefold())

        per_paper_scores = [
            max(k["keyword_score"] for k in entry["source_keywords"])
            for entry in evidence
        ]
        mean_source_score = sum(per_paper_scores) / len(per_paper_scores)

        overrides = [
            {
                "pair_id": item["pair_id"],
                "suggested_label": item.get("suggested_label"),
                "final_decision": item["decision"],
                "review_note": item.get("review_note"),
            }
            for item in merge_items
            if item.get("decision_source") == "explicit_review"
            and item.get("suggested_label") != item.get("decision")
        ]

        grouped.append({
            "topic": topic_label,
            "canonical_topic": canonical_keyword(topic_label),
            "paper_support": len(evidence),
            "mean_source_keyword_score": round(mean_source_score, 4),
            "source_aliases": aliases,
            "applied_same_topic_pair_ids": sorted(x["pair_id"] for x in merge_items),
            "manual_override_notes": overrides,
            "evidence": evidence,
        })

    return grouped


def build_profiles(people, decisions_by_researcher, top=6, secondary=3, min_support=2):
    known_ids = {p["id"] for p in people}
    unknown_ids = set(decisions_by_researcher) - known_ids
    if unknown_ids:
        raise ValueError(f"Decision file contains researchers not present in MySQL: {sorted(unknown_ids)}")

    grouped_by_researcher = {
        person["id"]: merge_reviewed_terms(
            person, decisions_by_researcher.get(person["id"], [])
        )
        for person in people
    }

    # Researcher-level document frequency after reviewed semantic consolidation.
    researcher_df = Counter(
        topic["canonical_topic"]
        for topics in grouped_by_researcher.values()
        for topic in topics
    )
    n_researchers = len(people)
    profiles = []

    for person in people:
        topics = grouped_by_researcher[person["id"]]
        for topic in topics:
            df = researcher_df[topic["canonical_topic"]]
            idf = math.log((n_researchers + 1) / (df + 1))
            topic["researcher_document_frequency"] = df
            topic["ranking_score"] = round(
                topic["mean_source_keyword_score"]
                * (1 + math.log2(topic["paper_support"]))
                * (1 + 0.15 * idf),
                4,
            )

        topics.sort(
            key=lambda t: (-t["ranking_score"], -t["paper_support"], t["canonical_topic"])
        )
        recurring = [t for t in topics if t["paper_support"] >= min_support]
        single = [t for t in topics if t["paper_support"] < min_support]

        if recurring:
            description = (
                "Publications repeatedly address "
                + compact_join([t["topic"] for t in recurring[:5]])
                + "."
            )
            profile_strength = "recurring_evidence"
        elif topics:
            description = (
                "Available publications mention "
                + compact_join([t["topic"] for t in topics[:5]])
                + "; none meets the repeated-paper threshold."
            )
            profile_strength = "limited_recurring_evidence"
        else:
            description = "No paper keywords are available to infer research expertise."
            profile_strength = "no_keyword_evidence"

        profiles.append({
            "researcher_id": person["id"],
            "researcher_name": person["name"],
            "paper_count": person["paper_count"],
            "profile_strength": profile_strength,
            "expertise_description_draft": description,
            "recurring_topics": recurring[:top],
            "single_paper_topics_for_review": single[:secondary],
            "all_ranked_topics": topics,
        })

    return profiles


class Command(BaseCommand):
    help = "Build reviewed researcher expertise from paper keywords; reads MySQL and writes local JSON only."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--sample", type=int, default=5)
        parser.add_argument("--top", type=int, default=6)
        parser.add_argument("--secondary", type=int, default=3)
        parser.add_argument("--min-support", type=int, default=2)
        parser.add_argument(
            "--decisions",
            default="data/expertise/approved_keyword_decisions.json",
        )
        parser.add_argument(
            "--output",
            default="data/expertise/researcher_expertise_reviewed.json",
        )

    def handle(self, *args, **options):
        if options["sample"] < 0 or options["secondary"] < 0:
            raise CommandError("--sample and --secondary must be >= 0")
        if options["top"] < 1 or options["min_support"] < 1:
            raise CommandError("--top and --min-support must be >= 1")

        try:
            decision_file, decisions_by_researcher = load_decisions(options["decisions"])
            people = collect_researchers(
                Researcher.objects.prefetch_related("papers__keywords").order_by("auid")
            )
            profiles = build_profiles(
                people,
                decisions_by_researcher,
                top=options["top"],
                secondary=options["secondary"],
                min_support=options["min_support"],
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise CommandError(str(exc)) from exc

        merged_groups = sum(
            1
            for p in profiles
            for t in p["all_ranked_topics"]
            if t["applied_same_topic_pair_ids"]
        )
        explicit_overrides = sum(
            1
            for p in profiles
            for t in p["all_ranked_topics"]
            for _ in t["manual_override_notes"]
        )

        self.stdout.write(f"Built {len(profiles)} reviewed researcher profiles from live MySQL.")
        self.stdout.write(
            f"Applied {decision_file['decision_counts'].get('same_topic', 0)} approved same-topic pair decisions "
            f"across {merged_groups} merged topic groups."
        )
        self.stdout.write(
            f"Kept {decision_file['decision_counts'].get('related_distinct', 0)} related-but-distinct pairs separate."
        )
        self.stdout.write(
            f"Retained {explicit_overrides} reviewer-overridden merge decisions as audit notes."
        )
        self.stdout.write(
            "Paper IDs 66459 and 66460 are counted as separate records until the client confirms otherwise."
        )

        for profile in profiles[: options["sample"]]:
            self.stdout.write(f"\n{profile['researcher_name']} ({profile['paper_count']} papers)")
            self.stdout.write("  " + profile["expertise_description_draft"])
            for topic in profile["recurring_topics"]:
                merge_marker = " [reviewed merge]" if topic["applied_same_topic_pair_ids"] else ""
                self.stdout.write(
                    f"  {topic['topic']} — {topic['paper_support']} papers; "
                    f"rank {topic['ranking_score']:.3f}{merge_marker}"
                )

        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS("Dry run passed; shared MySQL unchanged; no output JSON written.")
            )
            return

        payload = {
            "method": "reviewed keyword recurrence + approved semantic consolidation + per-paper max score + modest researcher IDF",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "researcher_count": len(profiles),
            "min_paper_support": options["min_support"],
            "decision_summary": {
                "total_candidate_pairs": decision_file["total_candidate_pairs"],
                "explicit_review_count": decision_file["explicit_review_count"],
                "accepted_recommendation_count": decision_file["accepted_recommendation_count"],
                "decision_counts": decision_file["decision_counts"],
            },
            "duplicate_paper_policy": decision_file["duplicate_paper_policy"],
            "review_required": True,
            "notes": [
                "All 89 semantic-review candidate pairs have an effective classification.",
                "same_topic pairs are consolidated; related_distinct and unrelated pairs stay separate.",
                "A merged topic counts each supporting paper once, even if multiple aliases occur in that paper.",
                "Ranking scores order topics only; they are not confidence probabilities.",
                "The output remains a review artifact and does not modify shared MySQL.",
            ],
            "researchers": profiles,
        }

        out = Path(options["output"])
        out.parent.mkdir(parents=True, exist_ok=True)
        temp = out.with_suffix(out.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temp.replace(out)
        self.stdout.write(
            self.style.SUCCESS(
                f"Saved {len(profiles)} reviewed expertise profiles to {out}. Shared MySQL unchanged."
            )
        )
