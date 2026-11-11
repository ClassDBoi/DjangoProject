import { useEffect } from "react";

/**
 * Shows the first result in the detail panel whenever nothing is selected:
 * when the page opens, and after a search, filter, sort or page change
 * (useListParams clears the selection on those).
 *
 * A selection already in the URL (a shared link, a cross-link from another page,
 * the back button) is kept, even when it is not on the current page of results.
 *
 * @param {object[]} items the results currently shown
 * @param {(item: object) => string} idOf the item's id, as used in `selected`
 * @param {string} selected the `selected` URL parameter
 * @param {boolean} loading true while the list is loading
 * @param {(id: string) => void} selectFirst sets `selected` without adding a history entry
 */
export default function useAutoSelectFirst(items, idOf, selected, loading, selectFirst) {
    const firstId = items.length > 0 ? idOf(items[0]) : "";

    useEffect(() => {
        if (!loading && !selected && firstId) {
            selectFirst(firstId);
        }
    }, [loading, selected, firstId, selectFirst]);
}
