import { useEffect } from "react";

/**
 * On narrow screens the detail panel sits below the list, so after a selection
 * loads, scroll it into view. On wide screens the panel is already beside the list.
 *
 * @param {string} selector the detail panel, e.g. "[data-paper-details]"
 * @param {unknown} loadedRecord the loaded record (scrolls when it changes)
 */
export default function useScrollToDetailsOnSmallScreens(selector, loadedRecord) {
    useEffect(() => {
        if (!loadedRecord || window.innerWidth >= 900) return;
        document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, [selector, loadedRecord]);
}
