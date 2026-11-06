import React from "react";

import collegeImages from "../../config/collegeImages";

const SMALL_WORDS = new Set(["college", "of", "and", "the", "&", "for", "school"]);

/** "College of Sciences and Mathematics" -> "SM", "Samuel Ginn College of Engineering" -> "E" */
function collegeInitials(college) {
    const name = String(college || "");
    // Use the subject after "College of" when there is one, so named colleges show their field.
    const subject = /college of (.+)$/i.exec(name)?.[1] || name;
    const words = subject
        .replace(/[,.]/g, " ")
        .split(/\s+/)
        .filter((word) => word && !SMALL_WORDS.has(word.toLowerCase()));
    return words.slice(0, 2).map((word) => word[0].toUpperCase()).join("") || "?";
}

/**
 * The college's image (see src/config/collegeImages.js), or its initials
 * when no image has been added yet.
 */
function CollegeBadge({ college, size = 44 }) {
    const image = college ? collegeImages[college] : null;
    const box = { ...badgeStyle, width: size, height: size, fontSize: Math.round(size * 0.36) };

    if (image) {
        return <img src={image} alt={college} title={college} style={{ ...box, objectFit: "contain", backgroundColor: "white" }} />;
    }

    return (
        <span style={box} title={college || "College not available"} aria-hidden="true">
            {collegeInitials(college)}
        </span>
    );
}

const badgeStyle = {
    flexShrink: 0,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "10px",
    backgroundColor: "var(--auburn-navy)",
    color: "white",
    fontWeight: 700,
    letterSpacing: "0.5px",
};

export default CollegeBadge;
