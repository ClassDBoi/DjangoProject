import React from "react";
import { Link } from "react-router-dom";

import DeadlineBadge from "./DeadlineBadge";
import { linkStyle, mutedStyle, sectionTitleStyle } from "./styles";

/**
 * Matches for the detail panels, with the evidence behind each one.
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
    const cutoff = Number(data.run.similarity_cutoff).toFixed(2);

    return (
        <section>
            <h3 style={sectionTitleStyle}>
                {forResearcher ? "Matching Funding Opportunities" : "Matching Researchers"}
            </h3>
            <p style={{ ...mutedStyle, fontSize: "13px", marginTop: 0 }}>
                {forResearcher
                    ? "Opportunities whose research topics are closest to keywords from this researcher's papers."
                    : "Researchers whose paper keywords are closest to this opportunity's research topics."}
                {" "}Semantic similarity (0 to 1) measures how close the topics are; it is not a likelihood of
                funding, and eligibility and deadlines are not checked.
            </p>

            {data.unmatched_reason && <p style={mutedStyle}>{data.unmatched_reason}</p>}

            {data.no_close_match && (
                <p style={mutedStyle}>
                    No close match {forResearcher ? "among the current funding opportunities" : "among the current researchers"}
                    {" "}(semantic similarity below {cutoff}).
                </p>
            )}

            {data.matches.map((match) => (
                <div key={forResearcher ? match.opp_id : match.auid} style={matchStyle}>
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

                    <p style={{ ...mutedStyle, margin: "4px 0 8px", fontSize: "13px" }}>
                        {forResearcher ? match.agency || "Agency not available" : match.department || "Department not available"}
                        {" · "}Semantic similarity {Number(match.semantic_similarity).toFixed(2)}
                    </p>

                    <p style={{ margin: "0 0 4px", fontSize: "13px", fontWeight: 600 }}>Matched because:</p>
                    <ul style={evidenceListStyle}>
                        {match.evidence.map((link) => (
                            <li key={`${link.opportunity_topic}-${link.researcher_term}`} style={{ marginBottom: "4px" }}>
                                <span style={topicStyle}>{link.opportunity_topic}</span>
                                {" ↔ "}
                                <span style={topicStyle}>{link.researcher_term}</span>
                                <span style={mutedStyle}> ({Number(link.semantic_similarity).toFixed(2)})</span>
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
            ))}
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
