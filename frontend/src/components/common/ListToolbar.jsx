import React, { useEffect, useState } from "react";

import useDebouncedValue from "../../hooks/useDebouncedValue";

/**
 * Search box, sort controls, page-specific filters and a result count.
 *
 * @param {string} search current search text (from the URL)
 * @param {(value: string) => void} onSearch called after typing pauses
 * @param {string} placeholder search box hint
 * @param {{value: string, label: string}[]} sortOptions
 * @param {string} sort current sort key
 * @param {string} order "asc" or "desc"
 * @param {(changes: {sort?: string, order?: string}) => void} onSortChange
 * @param {React.ReactNode} children filter controls (use FilterSelect)
 * @param {string} resultText e.g. "42 papers found"
 * @param {boolean} canClear whether any search or filter is active
 * @param {() => void} onClear resets search, filters and sort
 */
function ListToolbar({
    search, onSearch, placeholder, sortOptions, sort, order, onSortChange,
    children, resultText, canClear, onClear,
}) {
    const [text, setText] = useState(search);
    const [lastSearch, setLastSearch] = useState(search);
    const debounced = useDebouncedValue(text, 300);

    // Follow outside changes to the search (e.g. "Clear" or the back button).
    if (search !== lastSearch) {
        setLastSearch(search);
        setText(search);
    }

    useEffect(() => {
        if (debounced !== search) onSearch(debounced);
        // Only react to the user's typing, not to search changing from outside.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [debounced]);

    return (
        <div style={toolbarStyle}>
            <input
                type="search"
                placeholder={placeholder}
                value={text}
                onChange={(event) => setText(event.target.value)}
                style={searchStyle}
                aria-label={placeholder}
            />

            <div style={rowStyle}>
                {children}

                <label style={labelStyle}>
                    Sort by
                    <select
                        value={sort}
                        onChange={(event) => onSortChange({ sort: event.target.value })}
                        style={controlStyle}
                    >
                        {sortOptions.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                </label>

                <button
                    type="button"
                    onClick={() => onSortChange({ order: order === "desc" ? "asc" : "desc" })}
                    style={orderButtonStyle}
                    title="Change sort direction"
                >
                    <i className={`fa-solid ${order === "desc" ? "fa-arrow-down-wide-short" : "fa-arrow-up-short-wide"}`} />
                    {" "}{order === "desc" ? "Descending" : "Ascending"}
                </button>
            </div>

            <div style={summaryStyle}>
                <span>{resultText}</span>
                {canClear && (
                    <button type="button" onClick={onClear} style={clearButtonStyle}>
                        Clear search and filters
                    </button>
                )}
            </div>
        </div>
    );
}

/** A labelled dropdown for ListToolbar. */
export function FilterSelect({ label, value, onChange, options, allLabel = "All" }) {
    return (
        <label style={labelStyle}>
            {label}
            <select value={value} onChange={(event) => onChange(event.target.value)} style={controlStyle}>
                <option value="">{allLabel}</option>
                {options.map((option) => {
                    const item = typeof option === "string" ? { value: option, label: option } : option;
                    return <option key={item.value} value={item.value}>{item.label}</option>;
                })}
            </select>
        </label>
    );
}

const toolbarStyle = {
    marginBottom: "18px",
};

const searchStyle = {
    width: "100%",
    padding: "14px",
    marginBottom: "12px",
    border: "1px solid #ccc",
    borderRadius: "8px",
    boxSizing: "border-box",
    fontSize: "15px",
};

const rowStyle = {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    alignItems: "flex-end",
};

const labelStyle = {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    fontSize: "13px",
    fontWeight: 600,
    color: "var(--text-muted)",
};

const controlStyle = {
    padding: "9px 10px",
    border: "1px solid #ccc",
    borderRadius: "8px",
    backgroundColor: "white",
    fontSize: "14px",
    maxWidth: "260px",
    color: "var(--text-main)",
};

const orderButtonStyle = {
    ...controlStyle,
    cursor: "pointer",
};

const summaryStyle = {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: "14px",
    marginTop: "14px",
    color: "var(--text-main)",
};

const clearButtonStyle = {
    padding: "6px 10px",
    border: "none",
    background: "none",
    color: "var(--auburn_second_blue)",
    cursor: "pointer",
    fontWeight: 600,
    textDecoration: "underline",
};

export default ListToolbar;
