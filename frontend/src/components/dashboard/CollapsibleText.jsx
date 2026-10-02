import React, { useEffect, useState } from "react";

function CollapsibleText({
    title,
    text,
    showLabel = "Click to show",
    hideLabel = "Hide"
}) {
    const [isOpen, setIsOpen] = useState(false);

    useEffect(() => {
        setIsOpen(false);
    }, [text, title]);

    const hasText = Boolean(text && text !== "Not available");

    return (
        <section style={sectionStyle}>
            <div style={headerStyle}>
                <h3 style={{ margin: 0 }}>{title}</h3>

                {hasText && (
                    <button
                        type="button"
                        onClick={() => setIsOpen((current) => !current)}
                        style={buttonStyle}
                        aria-expanded={isOpen}
                    >
                        {isOpen ? hideLabel : showLabel}
                    </button>
                )}
            </div>

            {!hasText ? (
                <p>Not available</p>
            ) : isOpen ? (
                <div style={textStyle}>{text}</div>
            ) : (
                <p style={hiddenHintStyle}>Hidden by default.</p>
            )}
        </section>
    );
}

const sectionStyle = {
    marginTop: "20px",
    marginBottom: "20px"
};

const headerStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    flexWrap: "wrap"
};

const buttonStyle = {
    padding: "8px 12px",
    border: "1px solid #236FA5",
    borderRadius: "6px",
    backgroundColor: "white",
    color: "#236FA5",
    cursor: "pointer",
    fontWeight: 600
};

const textStyle = {
    marginTop: "12px",
    padding: "14px",
    border: "1px solid #e1e1e1",
    borderRadius: "8px",
    backgroundColor: "#fafafa",
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
    lineHeight: 1.55
};

const hiddenHintStyle = {
    marginTop: "8px",
    color: "#666",
    fontStyle: "italic"
};

export default CollapsibleText;
