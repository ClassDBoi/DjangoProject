import React from "react";

/** Previous / Next buttons with "Page x of y". Hidden when there is one page. */
function Pagination({ page, totalPages, onPageChange, disabled }) {
    if (totalPages <= 1) return null;

    return (
        <div style={paginationStyle}>
            <button type="button" disabled={disabled || page <= 1} onClick={() => onPageChange(page - 1)}>
                Previous
            </button>
            <span>Page {page} of {totalPages}</span>
            <button type="button" disabled={disabled || page >= totalPages} onClick={() => onPageChange(page + 1)}>
                Next
            </button>
        </div>
    );
}

const paginationStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "20px",
    padding: "20px",
};

export default Pagination;
