/**
 * Small helpers for calling the Django REST API.
 *
 * VITE_API_BASE (frontend/.env) can point at another server; when it is not set,
 * requests go to /api and the Vite dev server proxies them to Django
 * (see vite.config.js).
 */
export const API_BASE = (import.meta.env.VITE_API_BASE || "/api").replace(/\/+$/, "");

/**
 * GET a JSON endpoint. Empty parameters are left out of the query string.
 *
 * @param {string} path e.g. "/papers/"
 * @param {Record<string, string | number | undefined | null>} [params]
 * @param {AbortSignal} [signal] lets an effect cancel a request it no longer needs
 */
export async function getJson(path, params = {}, signal) {
    const query = new URLSearchParams();

    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
            query.set(key, String(value));
        }
    });

    const queryString = query.toString();
    const response = await fetch(
        `${API_BASE}${path}${queryString ? `?${queryString}` : ""}`,
        { signal }
    );

    if (!response.ok) {
        throw new Error(`Request failed (${response.status} ${response.statusText})`);
    }

    return response.json();
}

/** Ignore errors caused by cancelling a request on purpose. */
export function isAbortError(error) {
    return error?.name === "AbortError";
}
