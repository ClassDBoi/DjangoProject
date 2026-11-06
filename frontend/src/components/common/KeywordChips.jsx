import React from "react";

import ScoreReveal from "./ScoreReveal";

/**
 * Keywords or topics as small chips. The score, when given, is shown on hover or
 * when the chip is clicked or tapped (the client's scores are kept but not emphasized).
 *
 * @param {{label: string, score?: number}[]} items
 */
function KeywordChips({ items }) {
    if (!items?.length) {
        return <p style={{ color: "var(--text-muted)" }}>Not available</p>;
    }

    return (
        <div style={wrapStyle}>
            {items.map((item, index) => (
                <ScoreReveal
                    key={`${item.label}-${index}`}
                    score={item.score}
                    scoreLabel="Score"
                    digits={3}
                    style={chipStyle}
                >
                    {item.label}
                </ScoreReveal>
            ))}
        </div>
    );
}

const wrapStyle = {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
};

const chipStyle = {
    padding: "5px 10px",
    borderRadius: "999px",
    backgroundColor: "#eef4fa",
    color: "var(--auburn-navy)",
    fontSize: "13px",
    fontWeight: 500,
};

export default KeywordChips;
