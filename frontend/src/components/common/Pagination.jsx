import React from "react";

/** Previous / Next buttons with "Page x of y". Hidden when there is one page. */
function Pagination({ page, totalPages, onPageChange, disabled }) {
    if (totalPages <= 1) return null;

    const atStart = disabled || page <= 1;
    const atEnd = disabled || page >= totalPages;

    return (
        <nav style={paginationStyle} aria-label="Pages">
            <button type="button" disabled={atStart} onClick={() => onPageChange(page - 1)} style={buttonStyle(atStart)}>
                <i className="fa-solid fa-chevron-left" /> Previous
            </button>
            <span style={{ fontWeight: 600, color: "var(--text-main)" }}>Page {page} of {totalPages}</span>
            <button type="button" disabled={atEnd} onClick={() => onPageChange(page + 1)} style={buttonStyle(atEnd)}>
                Next <i className="fa-solid fa-chevron-right" />
            </button>
        </nav>
    );
}

const paginationStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "16px",
    padding: "8px 0 4px",
};

const buttonStyle = (inactive) => ({
    padding: "8px 14px",
    border: "1px solid #d5dde7",
    borderRadius: "8px",
    backgroundColor: inactive ? "#f5f7fa" : "white",
    color: inactive ? "#b6c0cc" : "var(--auburn-navy)",
    fontWeight: 600,
    cursor: inactive ? "default" : "pointer",
});

export default Pagination;
