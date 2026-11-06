import { useEffect, useState } from "react";

import { getJson } from "../lib/api";

// Fetched once per page load and shared by every page.
let cachedRequest = null;

/**
 * Values for the filter dropdowns (colleges, departments, agencies, years...),
 * from GET /api/filters/. Returns null until they have loaded.
 */
export default function useFilterOptions() {
    const [options, setOptions] = useState(null);

    useEffect(() => {
        let active = true;

        if (!cachedRequest) {
            cachedRequest = getJson("/filters/").catch((error) => {
                cachedRequest = null; // allow a retry on the next page visit
                throw error;
            });
        }

        cachedRequest
            .then((data) => { if (active) setOptions(data); })
            .catch(() => { if (active) setOptions(null); });

        return () => { active = false; };
    }, []);

    return options;
}
