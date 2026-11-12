import { useCallback, useEffect, useRef } from "react";

/**
 * On narrow screens the detail panel sits below the list. After the user picks
 * an item, scroll the panel into view once it has loaded. On wide screens the
 * panel is already beside the list.
 *
 * Only selections the user made trigger the scroll, so the automatic selection
 * of the first result (useAutoSelectFirst) does not jump past the list.
 *
 * @param {string} selector the detail panel, e.g. "[data-paper-details]"
 * @param {unknown} loadedRecord the loaded record (scrolls when it changes)
 * @returns {(alreadyShown?: boolean) => void} call this when the user selects an item;
 *   pass true when that item is already the one shown, so it scrolls straight away
 */
export default function useScrollToDetailsOnSmallScreens(selector, loadedRecord) {
    const pending = useRef(false);

    const scroll = useCallback(() => {
        if (window.innerWidth < 900) {
            document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }, [selector]);

    useEffect(() => {
        if (!loadedRecord || !pending.current) return;
        pending.current = false;
        scroll();
    }, [loadedRecord, scroll]);

    return useCallback((alreadyShown = false) => {
        if (alreadyShown) scroll();
        else pending.current = true;
    }, [scroll]);
}
