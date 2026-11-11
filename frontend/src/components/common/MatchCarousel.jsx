import React, { useState } from "react";
import { Link } from "react-router-dom";

import CollegeBadge from "./CollegeBadge";
import DeadlineBadge from "./DeadlineBadge";
import ResearcherPhoto from "./ResearcherPhoto";
import ScoreReveal from "./ScoreReveal";
import { linkStyle, mutedStyle, sectionTitleStyle } from "./styles";
import { linkPhrase, matchStrength } from "../../config/matchStrength";
import { formatDate, formatMoney } from "../../lib/format";

/**
 * Matches for the detail panels, one at a time.
 *
 * Arrows (or the dots, or the left/right arrow keys) move between matches, best
 * first. Each match shows its basic information and strength; clicking it opens
 * the evidence ("Matched because ...") and a link to the matched record. The
 * open/closed choice is kept while moving between matches, so evidence can be
 * compared without clicking again.
 *
 * Strength is shown in words ("Strong match", "closely matches") rather than as
 * numbers, which are easy to misread as percentages or probabilities. The semantic
 * similarity behind each label appears on hover, click or tap (ScoreReveal).
 * Thresholds: src/config/matchStrength.js.
 *
 * Give the component a `key` of the selected record, so it starts at the first
 * match whenever another record is selected.
 *
 * @param {"researcher" | "opportunity"} kind whose panel this is
 * @param {object} data response of /api/researchers/<auid>/matches/ or
 *   /api/opportunities/<id>/matches/
 * @param {boolean} loading
 *
 * Hidden entirely until a match run has been imported (data.run is null).
 */
function MatchCarousel({ kind, data, loading }) {
    const [index, setIndex] = useState(0);
    const [expanded, setExpanded] = useState(false);

    if (loading) {
        return <p style={mutedStyle}>Loading matches...</p>;
    }
    if (!data?.run) {
        return null;
    }

    const forResearcher = kind === "researcher";
    const matches = data.matches || [];
    const count = matches.length;
    const current = Math.min(index, Math.max(count - 1, 0));
    const match = matches[current];

    const go = (next) => setIndex(Math.max(0, Math.min(count - 1, next)));
    const onKeyDown = (event) => {
        if (event.key === "ArrowLeft") { event.preventDefault(); go(current - 1); }
        if (event.key === "ArrowRight") { event.preventDefault(); go(current + 1); }
    };

    return (
        <section
            aria-roledescription="carousel"
            aria-label={forResearcher ? "Matching funding opportunities" : "Matching researchers"}
            onKeyDown={count > 1 ? onKeyDown : undefined}
        >
            <div style={headerRowStyle}>
                <h3 style={{ ...sectionTitleStyle, margin: 0 }}>
                    {forResearcher ? "Matching Funding Opportunities" : "Matching Researchers"}
                </h3>

                {count > 1 && (
                    <div style={navStyle}>
                        <button
                            type="button"
                            style={arrowStyle(current === 0)}
                            onClick={() => go(current - 1)}
                            disabled={current === 0}
                            aria-label="Previous match"
                        >
                            <i className="fa-solid fa-chevron-left" />
                        </button>
                        <span style={counterStyle} aria-live="polite">
                            {current + 1} of {count}
                        </span>
                        <button
                            type="button"
                            style={arrowStyle(current === count - 1)}
                            onClick={() => go(current + 1)}
                            disabled={current === count - 1}
                            aria-label="Next match"
                        >
                            <i className="fa-solid fa-chevron-right" />
                        </button>
                    </div>
                )}
            </div>

            <p style={noteStyle}>
                Ranked by how closely research topics overlap, not by the chance of funding;
                eligibility and deadlines are not checked. Tap a label to see its score.
            </p>

            {data.unmatched_reason && <p style={mutedStyle}>{data.unmatched_reason}</p>}

            {data.no_close_match && (
                <p style={mutedStyle}>
                    No close match {forResearcher ? "among the current funding opportunities" : "among the current researchers"}.
                </p>
            )}

            {match && (
                <MatchCard
                    key={forResearcher ? match.opp_id : match.auid}
                    match={match}
                    forResearcher={forResearcher}
                    expanded={expanded}
                    onToggle={() => setExpanded((open) => !open)}
                />
            )}

            {count > 1 && (
                <div style={dotsStyle}>
                    {matches.map((item, position) => (
                        <button
                            key={forResearcher ? item.opp_id : item.auid}
                            type="button"
                            onClick={() => go(position)}
                            aria-label={`Show match ${position + 1}`}
                            aria-current={position === current ? "true" : undefined}
                            style={dotStyle(position === current)}
                        />
                    ))}
                </div>
            )}
        </section>
    );
}

function MatchCard({ match, forResearcher, expanded, onToggle }) {
    const strength = matchStrength(match.semantic_similarity);
    const colors = strengthColors[strength.key];
    const target = forResearcher
        ? { to: `/opportunities?selected=${match.opp_id}`, label: "Go to this opportunity" }
        : { to: `/researchers?selected=${encodeURIComponent(match.auid)}`, label: "Go to this researcher's profile" };

    const onKeyDown = (event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onToggle();
        }
    };

    return (
        <div style={{ ...cardStyle, borderLeft: `4px solid ${colors.accent}` }}>
            <div
                role="button"
                tabIndex={0}
                aria-expanded={expanded}
                onClick={onToggle}
                onKeyDown={onKeyDown}
                style={summaryStyle}
            >
                <div style={summaryRowStyle}>
                    {forResearcher ? (
                        <span className="match-icon" style={opportunityIconStyle} aria-hidden="true">
                            <i className="fa-solid fa-landmark" />
                        </span>
                    ) : (
                        <ResearcherPhoto auid={match.auid} name={match.name} size={52} />
                    )}

                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={nameRowStyle}>
                            <strong style={nameStyle}>{forResearcher ? match.title : match.name}</strong>
                            {forResearcher && <DeadlineBadge dueDate={match.due_date} />}
                        </div>

                        {forResearcher ? (
                            <p style={infoStyle}>
                                {match.agency || "Agency not available"}
                                {match.estimated_funding != null && <> · {formatMoney(match.estimated_funding)} estimated</>}
                                {match.due_date && <> · Due {formatDate(match.due_date)}</>}
                            </p>
                        ) : (
                            <>
                                {match.title && <p style={infoStyle}>{match.title}</p>}
                                <p style={infoStyle}>{match.department || "Department not available"}</p>
                                {match.college && (
                                    <p style={{ ...infoStyle, display: "flex", alignItems: "center", gap: "6px" }}>
                                        <CollegeBadge college={match.college} size={18} />
                                        {match.college}
                                    </p>
                                )}
                            </>
                        )}

                        <div style={badgeRowStyle}>
                            <ScoreReveal score={match.semantic_similarity} style={{ ...badgeStyle, ...colors.badge }}>
                                <span style={{ whiteSpace: "nowrap" }}>{strength.label}</span>
                            </ScoreReveal>
                            <span style={hintStyle}>
                                {expanded ? "Hide the reasons" : "Why this match?"}
                                {" "}<i className={`fa-solid ${expanded ? "fa-chevron-up" : "fa-chevron-down"}`} />
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {expanded && (
                <div style={detailStyle}>
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

                    <Link to={target.to} style={goButtonStyle}>
                        {target.label} <i className="fa-solid fa-arrow-right" />
                    </Link>
                </div>
            )}
        </div>
    );
}

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

const headerRowStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: "10px",
    marginTop: "22px",
};

const navStyle = {
    display: "flex",
    alignItems: "center",
    gap: "8px",
};

const arrowStyle = (disabled) => ({
    width: "34px",
    height: "34px",
    borderRadius: "50%",
    border: "1px solid #d5dde7",
    backgroundColor: disabled ? "#f5f7fa" : "white",
    color: disabled ? "#b6c0cc" : "var(--auburn-navy)",
    cursor: disabled ? "default" : "pointer",
});

const counterStyle = {
    minWidth: "54px",
    textAlign: "center",
    fontSize: "14px",
    fontWeight: 600,
    color: "var(--text-main)",
};

const noteStyle = {
    ...mutedStyle,
    fontSize: "12px",
    margin: "4px 0 10px",
};

// borderLeft is set per card (strength color); the other sides are set one by one so
// the shorthand never overlaps it.
const cardStyle = {
    borderTop: "1px solid #e5e9ef",
    borderRight: "1px solid #e5e9ef",
    borderBottom: "1px solid #e5e9ef",
    borderRadius: "10px",
    backgroundColor: "white",
};

const summaryStyle = {
    padding: "14px",
    cursor: "pointer",
    borderRadius: "10px",
};

const summaryRowStyle = {
    display: "flex",
    alignItems: "flex-start",
    gap: "14px",
};

const opportunityIconStyle = {
    flexShrink: 0,
    width: "52px",
    height: "52px",
    borderRadius: "10px",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#e8eef5",
    color: "var(--auburn-navy)",
    fontSize: "20px",
};

const nameRowStyle = {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "6px 10px",
};

const nameStyle = {
    flex: "1 1 180px",
    fontSize: "15px",
    color: "var(--auburn-navy)",
    overflowWrap: "anywhere",
};

const infoStyle = {
    margin: "3px 0 0",
    fontSize: "13px",
    color: "var(--text-muted)",
};

const badgeRowStyle = {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: "12px",
    marginTop: "8px",
};

const badgeStyle = {
    display: "inline-block",
    padding: "3px 10px",
    borderRadius: "999px",
    fontSize: "12px",
    fontWeight: 700,
};

const hintStyle = {
    fontSize: "13px",
    fontWeight: 600,
    color: "var(--auburn_second_blue)",
};

const detailStyle = {
    padding: "0 14px 14px clamp(14px, 12%, 80px)",
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

const goButtonStyle = {
    display: "inline-block",
    marginTop: "10px",
    padding: "8px 14px",
    borderRadius: "8px",
    backgroundColor: "var(--auburn-navy)",
    color: "white",
    textDecoration: "none",
    fontSize: "13px",
    fontWeight: 600,
};

const dotsStyle = {
    display: "flex",
    justifyContent: "center",
    flexWrap: "wrap",
    gap: "6px",
    marginTop: "10px",
};

const dotStyle = (active) => ({
    width: active ? "20px" : "8px",
    height: "8px",
    padding: 0,
    border: "none",
    borderRadius: "999px",
    backgroundColor: active ? "var(--auburn-orange)" : "#cfd7e1",
    cursor: "pointer",
    transition: "width 0.15s",
});

export default MatchCarousel;
