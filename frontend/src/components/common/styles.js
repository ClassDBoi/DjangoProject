/**
 * Shared inline styles for the list pages, so the three pages look the same.
 * Colors come from the CSS variables in src/index.css.
 */

export const pageStyle = {
    padding: "32px 40px 40px",
    maxWidth: "1400px",
    margin: "auto",
};

export const layoutStyle = {
    display: "flex",
    gap: "25px",
    flexWrap: "wrap",
    alignItems: "flex-start",
};

export const listColumnStyle = {
    flex: 1,
    minWidth: "300px",
};

export const cardStyle = {
    padding: "18px 20px",
    marginBottom: "14px",
    backgroundColor: "white",
    border: "1px solid #ddd",
    borderRadius: "10px",
    cursor: "pointer",
    overflowWrap: "anywhere",
    transition: "border-color 0.15s, box-shadow 0.15s",
};

export const selectedCardStyle = {
    ...cardStyle,
    borderColor: "var(--auburn-orange)",
    boxShadow: "0 0 0 2px rgba(204, 78, 11, 0.15)",
};

// The detail panel stays in view while the list scrolls, below the sticky navigation bar.
export const detailColumnStyle = {
    flex: 1,
    minWidth: "320px",
    alignSelf: "flex-start",
    position: "sticky",
    top: "calc(var(--nav-height) + 16px)",
    maxHeight: "calc(100vh - var(--nav-height) - 32px)",
    overflowY: "auto",
    paddingRight: "4px",
};

export const detailCardStyle = {
    ...cardStyle,
    cursor: "default",
    marginBottom: 0,
};

export const metaStyle = {
    margin: "4px 0",
    color: "var(--text-main)",
};

export const mutedStyle = {
    color: "var(--text-muted)",
};

export const linkStyle = {
    color: "var(--auburn_second_blue)",
    textDecoration: "none",
    fontWeight: 600,
};

export const sectionTitleStyle = {
    marginTop: "24px",
    marginBottom: "8px",
};
