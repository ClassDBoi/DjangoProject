import React, { useState } from "react";

/**
 * Wraps a label so its underlying score shows on hover (desktop) and on
 * click or tap (any device, including phones without hover).
 *
 * @param {React.ReactNode} children what is normally shown (a badge, a phrase, a chip)
 * @param {number} score the number to reveal
 * @param {string} [scoreLabel="Semantic similarity"] what the number is
 * @param {number} [digits=2] decimal places
 * @param {object} [style] style for the clickable element
 */
function ScoreReveal({ children, score, scoreLabel = "Semantic similarity", digits = 2, style }) {
    const [open, setOpen] = useState(false);

    if (score === undefined || score === null || Number.isNaN(Number(score))) {
        return <span style={style}>{children}</span>;
    }

    const text = `${scoreLabel}: ${Number(score).toFixed(digits)}`;
    const toggle = () => setOpen((current) => !current);

    // A span acting as a button (rather than <button>) so long phrases wrap
    // naturally inside sentences and list items.
    return (
        <span
            role="button"
            tabIndex={0}
            onClick={toggle}
            onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    toggle();
                }
            }}
            title={text}
            aria-expanded={open}
            data-score-reveal
            style={{ ...buttonReset, ...style }}
        >
            {children}
            {open && <span style={revealedStyle}> · {text}</span>}
        </span>
    );
}

const buttonReset = {
    cursor: "pointer",
};

const revealedStyle = {
    fontWeight: 400,
    color: "var(--text-muted)",
    whiteSpace: "nowrap",
};

export default ScoreReveal;
