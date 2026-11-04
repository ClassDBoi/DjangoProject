/** Display helpers shared by the list and detail pages. */

export const NOT_AVAILABLE = "Not available";

export function formatMoney(value) {
    if (value === null || value === undefined || value === "") {
        return NOT_AVAILABLE;
    }

    return Number(value).toLocaleString("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
    });
}

/** "2026-11-04T00:00:00Z" or "2026-11-04" -> "2026-11-04" */
export function formatDate(value) {
    if (!value) return NOT_AVAILABLE;
    return String(value).slice(0, 10);
}

export function hasText(value) {
    return Boolean(value && String(value).trim() && value !== NOT_AVAILABLE);
}
