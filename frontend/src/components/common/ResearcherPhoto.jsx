import React, { useState } from "react";

import researcherPhotos from "../../config/researcherPhotos";

/** "Jane A. Doe" -> "JD" */
function nameInitials(name) {
    const words = String(name || "").replace(/[,.]/g, " ").split(/\s+/).filter(Boolean);
    if (words.length === 0) return "?";
    const first = words[0][0];
    const last = words.length > 1 ? words[words.length - 1][0] : "";
    return `${first}${last}`.toUpperCase();
}

/**
 * The researcher's headshot (see src/config/researcherPhotos.js), or their
 * initials when no photo has been added or the image fails to load.
 */
function ResearcherPhoto({ auid, name, size = 48 }) {
    const photo = auid ? researcherPhotos[auid] : null;
    const [failed, setFailed] = useState(null);
    const box = { ...circleStyle, width: size, height: size, fontSize: Math.round(size * 0.38) };

    if (photo && failed !== photo) {
        return (
            <img
                src={photo}
                alt={name ? `Photo of ${name}` : "Researcher photo"}
                style={{ ...box, objectFit: "cover" }}
                onError={() => setFailed(photo)}
            />
        );
    }

    return (
        <span style={box} aria-hidden="true">
            {nameInitials(name)}
        </span>
    );
}

const circleStyle = {
    flexShrink: 0,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "50%",
    backgroundColor: "#e8eef5",
    color: "var(--auburn-navy)",
    fontWeight: 700,
    letterSpacing: "0.5px",
    border: "2px solid white",
    boxShadow: "0 0 0 1px #d5dde7",
};

export default ResearcherPhoto;
