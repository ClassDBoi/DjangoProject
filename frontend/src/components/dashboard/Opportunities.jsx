import React, { useCallback } from "react";

import DeadlineBadge from "../common/DeadlineBadge";
import ExpandableText from "../common/ExpandableText";
import KeywordChips from "../common/KeywordChips";
import ListToolbar, { FilterSelect } from "../common/ListToolbar";
import Pagination from "../common/Pagination";
import {
    cardStyle, detailCardStyle, detailColumnStyle, layoutStyle, listColumnStyle,
    metaStyle, mutedStyle, pageStyle, sectionTitleStyle, selectedCardStyle,
} from "../common/styles";
import useDeselectOnOutsideClick from "./useDeselectOnOutsideClick";
import useDetail from "../../hooks/useDetail";
import useFilterOptions from "../../hooks/useFilterOptions";
import useList from "../../hooks/useList";
import useListParams from "../../hooks/useListParams";
import useScrollToDetailsOnSmallScreens from "../../hooks/useScrollToDetailsOnSmallScreens";
import { NOT_AVAILABLE, formatDate, formatMoney } from "../../lib/format";

// Every URL parameter this page uses, with its default.
const DEFAULTS = {
    search: "", agency: "", category: "", status: "", min_funding: "",
    sort: "title", order: "asc", page: "1", selected: "",
};

const SORT_OPTIONS = [
    { value: "title", label: "Title" },
    { value: "due_date", label: "Due date" },
    { value: "funding", label: "Estimated total funding" },
    { value: "ceiling", label: "Award ceiling" },
    { value: "agency", label: "Agency" },
];

const STATUS_OPTIONS = [
    { value: "open", label: "Open" },
    { value: "closed", label: "Closed" },
];

const FUNDING_OPTIONS = [100000, 500000, 1000000, 5000000, 10000000].map((n) => ({
    value: String(n), label: `${formatMoney(n)}+`,
}));

function Opportunities() {
    const [params, update, clear] = useListParams(DEFAULTS);
    const options = useFilterOptions();

    const { data, loading, error } = useList("/opportunities/", {
        search: params.search,
        agency: params.agency,
        category: params.category,
        status: params.status,
        min_funding: params.min_funding,
        sort: params.sort,
        order: params.order,
        page: params.page,
    });
    const opportunities = data?.results || [];
    const detail = useDetail("/opportunities/", params.selected);

    const select = useCallback((id) => update({ selected: id }, { keepPage: true, push: true }), [update]);
    const deselect = useCallback(() => update({ selected: "" }, { keepPage: true }), [update]);

    // Click anywhere outside the cards and detail panel to clear the selection.
    useDeselectOnOutsideClick("[data-opportunity-card], [data-opportunity-details]", deselect);
    useScrollToDetailsOnSmallScreens("[data-opportunity-details]", detail.data);

    const canClear = Boolean(params.search || params.agency || params.category || params.status
        || params.min_funding || params.sort !== DEFAULTS.sort || params.order !== DEFAULTS.order);

    const selected = detail.data;

    return (
        <div style={pageStyle}>
            <h1>Funding Opportunities</h1>

            <ListToolbar
                search={params.search}
                onSearch={(search) => update({ search })}
                placeholder="Search by title, agency, category or description..."
                sortOptions={SORT_OPTIONS}
                sort={params.sort}
                order={params.order}
                onSortChange={update}
                resultText={loading && !data ? "Loading opportunities..." : `${data?.count ?? 0} opportunities found`}
                canClear={canClear}
                onClear={clear}
            >
                <FilterSelect
                    label="Agency"
                    value={params.agency}
                    onChange={(agency) => update({ agency })}
                    options={options?.opportunities.agencies || []}
                    allLabel="All agencies"
                />
                <FilterSelect
                    label="Category"
                    value={params.category}
                    onChange={(category) => update({ category })}
                    options={options?.opportunities.categories || []}
                    allLabel="All categories"
                />
                <FilterSelect
                    label="Status"
                    value={params.status}
                    onChange={(status) => update({ status })}
                    options={STATUS_OPTIONS}
                    allLabel="Open and closed"
                />
                <FilterSelect
                    label="Estimated funding"
                    value={params.min_funding}
                    onChange={(min_funding) => update({ min_funding })}
                    options={FUNDING_OPTIONS}
                    allLabel="Any amount"
                />
            </ListToolbar>

            {error && <p style={{ color: "red" }}>{error}</p>}

            <div style={layoutStyle}>
                <div style={listColumnStyle}>
                    {!loading && opportunities.length === 0 && (
                        <p style={mutedStyle}>No opportunities match your search.</p>
                    )}

                    {opportunities.map((opportunity) => (
                        <div
                            key={opportunity.opp_id}
                            data-opportunity-card
                            style={String(opportunity.opp_id) === params.selected ? selectedCardStyle : cardStyle}
                            onClick={() => select(String(opportunity.opp_id))}
                        >
                            <div style={titleRowStyle}>
                                <h3 style={{ margin: 0 }}>{opportunity.title}</h3>
                                <DeadlineBadge dueDate={opportunity.due_date} />
                            </div>
                            <p style={metaStyle}><strong>Agency:</strong> {opportunity.agency || NOT_AVAILABLE}</p>
                            <p style={metaStyle}><strong>Estimated Funding:</strong> {formatMoney(opportunity.estimated_funding)}</p>
                            <p style={{ ...metaStyle, ...mutedStyle }}>
                                Due {formatDate(opportunity.due_date)}
                                {" · "}{opportunity.category || "Category not available"}
                            </p>
                        </div>
                    ))}

                    <Pagination
                        page={data?.current_page || 1}
                        totalPages={data?.total_pages || 1}
                        onPageChange={(page) => update({ page })}
                        disabled={loading}
                    />
                </div>

                <div data-opportunity-details style={detailColumnStyle}>
                    {detail.loading && <p>Loading opportunity details...</p>}
                    {detail.error && <p style={{ color: "red" }}>{detail.error}</p>}

                    {selected && (
                        <div style={detailCardStyle}>
                            <div style={titleRowStyle}>
                                <h2 style={{ margin: 0 }}>{selected.title}</h2>
                                <DeadlineBadge dueDate={selected.due_date} />
                            </div>

                            <p style={metaStyle}><strong>Agency:</strong> {selected.agency || NOT_AVAILABLE}</p>
                            <p style={metaStyle}><strong>Category:</strong> {selected.category || NOT_AVAILABLE}</p>
                            <p style={metaStyle}><strong>Estimated Funding:</strong> {formatMoney(selected.estimated_funding)}</p>
                            <p style={metaStyle}><strong>Award Floor:</strong> {formatMoney(selected.award_floor)}</p>
                            <p style={metaStyle}><strong>Award Ceiling:</strong> {formatMoney(selected.award_ceiling)}</p>
                            <p style={metaStyle}><strong>Due Date:</strong> {formatDate(selected.due_date)}</p>

                            <ExpandableText
                                key={`description-${selected.opp_id}`}
                                title="Description"
                                text={selected.description}
                                previewWords={80}
                                noun="description"
                            />

                            <ExpandableText
                                key={`announcement-${selected.opp_id}`}
                                title="Full Research Announcement"
                                text={selected.full_announcement}
                                previewWords={120}
                                noun="announcement"
                            />

                            <h3 style={sectionTitleStyle}>Topics</h3>
                            <KeywordChips
                                items={(selected.topics || []).map((t) => ({ label: t.topic, score: t.score }))}
                            />

                            <h3 style={sectionTitleStyle}>Domains</h3>
                            {selected.domains?.length > 0 ? (
                                <ul style={{ paddingLeft: "20px" }}>
                                    {selected.domains.map((domain, index) => (
                                        <li key={index} style={{ marginBottom: "10px" }}>
                                            <strong>{domain.domain_name}</strong>
                                            {domain.is_primary && <span style={primaryStyle}>Primary</span>}
                                            <span style={{ ...mutedStyle, marginLeft: "8px" }}>
                                                Confidence {Number(domain.confidence_score).toFixed(3)}
                                            </span>
                                            <br />
                                            <span style={mutedStyle}>{domain.rationale || "No rationale given."}</span>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p>{NOT_AVAILABLE}</p>
                            )}
                        </div>
                    )}

                    {!params.selected && (
                        <p style={mutedStyle}>Select an opportunity to view its details.</p>
                    )}
                </div>
            </div>
        </div>
    );
}

const titleRowStyle = {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "12px",
    marginBottom: "10px",
};

const primaryStyle = {
    marginLeft: "8px",
    padding: "2px 8px",
    borderRadius: "999px",
    backgroundColor: "#fff1e6",
    color: "#b54708",
    fontSize: "12px",
    fontWeight: 700,
};

export default Opportunities;
