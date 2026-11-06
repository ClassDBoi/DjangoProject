import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Keeps a page's search, filter, sort, page and selection state in the URL
 * query string, so the back button, page refreshes and shared links keep them.
 *
 * @param {Record<string, string>} defaults every parameter the page uses and its
 *   default value. Define it outside the component so it stays the same object.
 * @returns {[Record<string, string>, (changes: object, options?: object) => void, () => void]}
 *   current values, an update function and a function that clears everything.
 *
 * update({ sort: "date" }) also returns to page 1, because the old page number
 * no longer means anything once the list changes. Pass { keepPage: true } to
 * avoid that, and { push: true } to add a browser history entry (used for
 * selecting an item, so Back returns to the previous selection).
 */
export default function useListParams(defaults) {
    const [searchParams, setSearchParams] = useSearchParams();

    const values = useMemo(() => {
        const current = { ...defaults };
        Object.keys(defaults).forEach((key) => {
            const value = searchParams.get(key);
            if (value !== null) current[key] = value;
        });
        return current;
    }, [searchParams, defaults]);

    const update = useCallback((changes, { keepPage = false, push = false } = {}) => {
        setSearchParams((previous) => {
            const next = new URLSearchParams(previous);

            Object.entries(changes).forEach(([key, value]) => {
                if (value === undefined || value === null || value === "" || value === defaults[key]) {
                    next.delete(key);
                } else {
                    next.set(key, String(value));
                }
            });

            if (!keepPage && !("page" in changes)) {
                next.delete("page");
            }

            return next;
        }, { replace: !push });
    }, [setSearchParams, defaults]);

    const clear = useCallback(() => {
        setSearchParams(new URLSearchParams(), { replace: true });
    }, [setSearchParams]);

    return [values, update, clear];
}
