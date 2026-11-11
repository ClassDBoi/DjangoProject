/**
 * Chips for ListToolbar's activeFilters: one per search or filter that has a value.
 *
 * @param {{key: string, label: string, format?: (value: string) => string}[]} definitions
 *   which URL parameters are filters, their labels, and how to show a value
 *   (e.g. an AUID as the researcher's name)
 * @param {Record<string, string>} params current URL parameters (useListParams)
 * @param {(changes: object) => void} update useListParams' update function
 */
export function activeFilterChips(definitions, params, update) {
    return definitions
        .filter((definition) => params[definition.key])
        .map((definition) => ({
            key: definition.key,
            label: definition.label,
            value: definition.format ? definition.format(params[definition.key]) : params[definition.key],
            onRemove: () => update({ [definition.key]: "" }),
        }));
}
