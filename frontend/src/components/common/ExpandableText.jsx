import React, { useState } from "react";

import { NOT_AVAILABLE, hasText } from "../../lib/format";

/**
 * Shows the start of a long text with a "Read more" button underneath.
 * Short texts are shown in full with no button.
 *
 * @param {string} title section heading
 * @param {string} text the full text
 * @param {number} [previewWords=60] words shown before "Read more"
 * @param {string} [noun="text"] what the text is ("abstract"), used in the note shown
 *   when the stored text was itself cut off at the source
 */
function ExpandableText({ title, text, previewWords = 60, noun = "text" }) {
    // Parents pass key={text} so a new item always starts collapsed.
    const [expanded, setExpanded] = useState(false);

    if (!hasText(text)) {
        return (
            <section style={sectionStyle}>
                <h3 style={titleStyle}>{title}</h3>
                <p style={emptyStyle}>{NOT_AVAILABLE}</p>
            </section>
        );
    }

    const fullText = String(text).trim();
    const words = fullText.split(/\s+/);
    const isLong = words.length > previewWords;
    // Cut after the Nth word but keep the original line breaks in the preview.
    const cut = isLong ? fullText.match(new RegExp(`^(?:\\S+\\s+){${previewWords - 1}}\\S+`))?.[0] : null;
    const preview = cut ? `${cut}…` : fullText;
    // Much of the client data was collected as snippets that end in "…": the stored text
    // itself stops there, so say so instead of letting it look like a display problem.
    const sourceIsCut = /(\.\.\.|…)$/.test(fullText);
    const showing = expanded || !isLong;

    return (
        <section style={sectionStyle}>
            <h3 style={titleStyle}>{title}</h3>

            <div style={textStyle}>{showing ? fullText : preview}</div>

            {showing && sourceIsCut && (
                <p style={noteStyle}>
                    This is all of the text in the source data; the original {noun} is longer.
                </p>
            )}

            {isLong && (
                <button
                    type="button"
                    onClick={() => setExpanded((current) => !current)}
                    style={buttonStyle}
                    aria-expanded={expanded}
                >
                    {expanded ? "Show less" : `Read more (${words.length.toLocaleString()} words)`}
                </button>
            )}
        </section>
    );
}

const sectionStyle = {
    marginTop: "20px",
    marginBottom: "20px",
};

const titleStyle = {
    margin: "0 0 10px",
};

const textStyle = {
    padding: "14px",
    border: "1px solid #e1e1e1",
    borderRadius: "8px",
    backgroundColor: "#fafafa",
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
    lineHeight: 1.55,
};

const buttonStyle = {
    marginTop: "10px",
    padding: "8px 12px",
    border: "1px solid var(--auburn_second_blue)",
    borderRadius: "6px",
    backgroundColor: "white",
    color: "var(--auburn_second_blue)",
    cursor: "pointer",
    fontWeight: 600,
};

const noteStyle = {
    margin: "8px 0 0",
    fontSize: "13px",
    fontStyle: "italic",
    color: "var(--text-muted)",
};

const emptyStyle = {
    color: "var(--text-muted)",
};

export default ExpandableText;
