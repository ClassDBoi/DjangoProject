import React from "react";
import { Link } from "react-router-dom";

import DeadlineBadge from "./DeadlineBadge";
import ScoreReveal from "./ScoreReveal";
import { linkStyle, mutedStyle, sectionTitleStyle } from "./styles";
import { linkPhrase, matchStrength } from "../../config/matchStrength";

/**
 * Matches for the detail panels, with the evidence behind each one.
 *
 * Strength is shown in words ("Strong match", "closely matches") rather than as
 * numbers, which are easy to misread as percentages or probabilities. The semantic
 * similarity behind each label appears on hover, click or tap (ScoreReveal).
 * Thresholds: src/config/matchStrength.js.
 *
 * @param {"researcher" | "opportunity"} kind whose panel this is
 * @param {object} data response of /api/researchers/<auid>/matches/ or
 *   /api/opportunities/<id>/matches/
 * @param {boolean} loading
 *
 * Hidden entirely until a match run has been imported (data.run is null).
 */
function MatchList({ kind, data, loading }) {
    if (loading) {
        return <p style={mutedStyle}>Loading matches...</p>;
    }
    if (!data?.run) {
        return null;
    }

    const forResearcher = kind === "researcher";

    return (
        <section>
            <h3 style={sectionTitleStyle}>
                {forResearcher ? "Matching Funding Opportunities" : "Matching Researchers"}
            </h3>
            <p style={{ ...mutedStyle, fontSize: "13px", marginTop: 0 }}>
                {forResearcher
                    ? "Opportunities whose research topics are closest to keywords from this researcher's papers."
                    : "Researchers whose paper keywords are closest to this opportunity's research topics."}
                {" "}"Strong" and "possible" describe how closely the research topics overlap, not the
                chance of funding; eligibility and deadlines are not checked. Tap or hover over a label
                to see the underlying score.
            </p>

            {data.unmatched_reason && <p style={mutedStyle}>{data.unmatched_reason}</p>}

            {data.no_close_match && (
                <p style={mutedStyle}>
                    No close match {forResearcher ? "among the current funding opportunities" : "among the current researchers"}.
                </p>
            )}

            {data.matches.map((match) => {
                const strength = matchStrength(match.semantic_similarity);
                return (
                    <div
                        key={forResearcher ? match.opp_id : match.auid}
                        style={{ ...matchStyle, borderLeftColor: strengthColors[strength.key].accent }}
                    >
                        <div style={headerStyle}>
                            {forResearcher ? (
                                <Link to={`/opportunities?selected=${match.opp_id}`} style={{ ...linkStyle, fontSize: "15px" }}>
                                    {match.title}
                                </Link>
                            ) : (
                                <Link to={`/researchers?selected=${encodeURIComponent(match.auid)}`} style={{ ...linkStyle, fontSize: "15px" }}>
                                    {match.name}
                                </Link>
                            )}
                            {forResearcher && <DeadlineBadge dueDate={match.due_date} />}
                        </div>

                        <div style={metaRowStyle}>
                            <ScoreReveal
                                score={match.semantic_similarity}
                                style={{ ...badgeStyle, ...strengthColors[strength.key].badge }}
                            >
                                <span style={{ whiteSpace: "nowrap" }}>{strength.label}</span>
                            </ScoreReveal>
                            <span style={{ ...mutedStyle, fontSize: "13px" }}>
                                {forResearcher ? match.agency || "Agency not available" : match.department || "Department not available"}
                            </span>
                        </div>

                        <p style={{ margin: "0 0 4px", fontSize: "13px", fontWeight: 600 }}>Matched because:</p>
                        <ul style={evidenceListStyle}>
                            {match.evidence.map((link) => (
                                <li key={`${link.opportunity_topic}-${link.researcher_term}`} style={{ marginBottom: "6px" }}>
                                    <ScoreReveal score={link.semantic_similarity}>
                                        <span style={topicStyle}>{link.opportunity_topic}</span>
                                        {` ${linkPhrase(link.semantic_similarity)} `}
                                        <span style={topicStyle}>{link.researcher_term}</span>
                                    </ScoreReveal>
                                    {link.paper_id && (
                                        <>
                                            <br />
                                            <span style={mutedStyle}>from </span>
                                            <Link to={`/papers?selected=${link.paper_id}`} style={{ ...linkStyle, fontWeight: 400 }}>
                                                {link.paper_title}
                                            </Link>
                                            {link.other_paper_count > 0 && (
                                                <span style={mutedStyle}> and {link.other_paper_count} more</span>
                                            )}
                                        </>
                                    )}
                                </li>
                            ))}
                        </ul>
                    </div>
                );
            })}
        </section>
    );
}

const matchStyle = {
    padding: "14px",
    marginTop: "12px",
    border: "1px solid #eee",
    borderLeft: "4px solid var(--auburn-orange)",
    borderRadius: "8px",
};

// Color always comes with a word ("Strong match"), so meaning never depends on color alone.
const strengthColors = {
    strong: {
        accent: "var(--auburn-orange)",
        badge: { backgroundColor: "#fff1e6", color: "#b54708", border: "1px solid #f3b28f" },
    },
    possible: {
        accent: "#cbd5e1",
        badge: { backgroundColor: "#f1f5f9", color: "#475569", border: "1px solid #d8dee6" },
    },
};

const badgeStyle = {
    display: "inline-block",
    padding: "3px 10px",
    borderRadius: "999px",
    fontSize: "12px",
    fontWeight: 700,
};

const metaRowStyle = {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: "10px",
    margin: "6px 0 10px",
};

const headerStyle = {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "10px",
};

const evidenceListStyle = {
    margin: 0,
    paddingLeft: "18px",
    fontSize: "13px",
    lineHeight: 1.5,
};

const topicStyle = {
    fontWeight: 600,
    color: "var(--auburn-navy)",
};

export default MatchList;
