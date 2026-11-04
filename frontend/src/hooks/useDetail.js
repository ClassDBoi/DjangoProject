import { useEffect, useState } from "react";

import { getJson, isAbortError } from "../lib/api";

/**
 * Loads one record for the detail panel, e.g. useDetail("/papers/", selectedId).
 * Returns { data, loading, error }; data is null when nothing is selected.
 */
export default function useDetail(basePath, id) {
    const key = id ? `${basePath}${encodeURIComponent(id)}/` : null;
    // `key` records which record the stored result belongs to.
    const [result, setResult] = useState({ key: null, data: null, error: "" });

    useEffect(() => {
        if (!key) return undefined;

        const controller = new AbortController();

        getJson(key, {}, controller.signal)
            .then((data) => setResult({ key, data, error: "" }))
            .catch((error) => {
                if (!isAbortError(error)) {
                    setResult({ key, data: null, error: `Could not load details: ${error.message}` });
                }
            });

        return () => controller.abort();
    }, [key]);

    if (!key) return { data: null, loading: false, error: "" };

    const current = result.key === key;
    return {
        data: current ? result.data : null,
        loading: !current,
        error: current ? result.error : "",
    };
}
