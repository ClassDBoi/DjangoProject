import { useEffect } from "react";

/**
 * Clears the page's current selection when the user clicks anywhere that is
 * not a list card, the detail panel, or a form control / link.
 *
 * Ported from Cunzhi's cunzhi-frontend branch
 * (IKUNR2025/AI-SGCOE-Tool-2026Fall @ a4642bc), adapted so the existing
 * detail panel layout is unchanged: clearing simply returns the panel to its
 * "Select ... to view details" placeholder.
 *
 * @param {string} protectedSelector CSS selector for areas that must not clear
 *   the selection, e.g. "[data-paper-card], [data-paper-details]".
 * @param {(value: null) => void} setSelected The page's selection setter
 *   (a stable React state setter); it is called with null to clear.
 */
export default function useDeselectOnOutsideClick(protectedSelector, setSelected) {
    useEffect(() => {
        function handleDocumentClick(event) {
            if (!(event.target instanceof Element)) return;

            const insideProtectedArea = event.target.closest(
                `${protectedSelector}, input, select, textarea, button, a, label`
            );

            if (!insideProtectedArea) {
                setSelected(null);
            }
        }

        document.addEventListener("click", handleDocumentClick);
        return () => document.removeEventListener("click", handleDocumentClick);
    }, [protectedSelector, setSelected]);
}
