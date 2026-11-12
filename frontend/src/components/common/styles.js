/**
 * Shared inline styles for the list pages, so the three pages look the same.
 * Colors come from the CSS variables in src/index.css.
 */

export const pageStyle = {
    padding: "24px 40px 16px",
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
    padding: "16px 18px",
    marginBottom: "12px",
    backgroundColor: "white",
    border: "1px solid #ddd",
    borderRadius: "10px",
    cursor: "pointer",
    overflowWrap: "anywhere",
    transition: "border-color 0.15s, box-shadow 0.15s",
};

// `border` is set in full (not borderColor) so React never mixes the shorthand and
// the longhand when a card switches between the two styles.
export const selectedCardStyle = {
    ...cardStyle,
    border: "1px solid var(--auburn-orange)",
    boxShadow: "0 0 0 2px rgba(204, 78, 11, 0.15)",
};

// The detail panel stays in view while the list scrolls, below the sticky navigation bar.
// Its height leaves the same 16px below it as the page's bottom padding, so the end of
// the page has no extra blank strip.
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
