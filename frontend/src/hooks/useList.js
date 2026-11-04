import { useEffect, useState } from "react";

import { getJson, isAbortError } from "../lib/api";

/**
 * Loads a list endpoint whenever its parameters change.
 * Returns { data, loading, error }; data keeps the previous result while a new one loads,
 * so the list does not flash empty between pages.
 *
 * @param {string} path e.g. "/papers/"
 * @param {Record<string, string>} params query parameters (empty values are skipped)
 */
export default function useList(path, params) {
    const key = `${path}?${JSON.stringify(params)}`;
    // `key` records which request the stored result belongs to.
    const [result, setResult] = useState({ key: null, data: null, error: "" });

    useEffect(() => {
        const controller = new AbortController();

        getJson(path, params, controller.signal)
            .then((data) => setResult({ key, data, error: "" }))
            .catch((error) => {
                if (!isAbortError(error)) {
                    setResult((previous) => ({ key, data: previous.data, error: error.message }));
                }
            });

        return () => controller.abort();
        // `key` already captures every value in path and params.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [key]);

    const current = result.key === key;
    return { data: result.data, loading: !current, error: current ? result.error : "" };
}
