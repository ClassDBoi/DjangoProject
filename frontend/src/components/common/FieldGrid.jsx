import React from "react";

/**
 * Short labelled values (department, agency, due date...) laid out side by side,
 * so detail panels use their width instead of one line per value.
 *
 * @param {{label: string, value: React.ReactNode, wide?: boolean}[]} fields
 *   `wide` fields span the full row (e.g. a long author list).
 */
function FieldGrid({ fields }) {
    return (
        <dl style={gridStyle}>
            {fields.map((field) => (
                <div key={field.label} style={field.wide ? { ...cellStyle, gridColumn: "1 / -1" } : cellStyle}>
                    <dt style={labelStyle}>{field.label}</dt>
                    <dd style={valueStyle}>{field.value}</dd>
                </div>
            ))}
        </dl>
    );
}

const gridStyle = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
    gap: "10px 18px",
    margin: "12px 0 0",
};

const cellStyle = {
    minWidth: 0,
};

const labelStyle = {
    fontSize: "11px",
    fontWeight: 700,
    letterSpacing: "0.6px",
    textTransform: "uppercase",
    color: "var(--text-muted)",
    marginBottom: "2px",
};

const valueStyle = {
    margin: 0,
    color: "var(--text-main)",
    overflowWrap: "anywhere",
};

export default FieldGrid;
