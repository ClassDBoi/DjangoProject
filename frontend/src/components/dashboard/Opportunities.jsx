import React, { useCallback } from "react";

import DeadlineBadge from "../common/DeadlineBadge";
import ExpandableText from "../common/ExpandableText";
import FieldGrid from "../common/FieldGrid";
import KeywordChips from "../common/KeywordChips";
import MatchCarousel from "../common/MatchCarousel";
import ListToolbar, { FilterSelect } from "../common/ListToolbar";
import Pagination from "../common/Pagination";
import {
    cardStyle, detailCardStyle, detailColumnStyle, layoutStyle, listColumnStyle,
    metaStyle, mutedStyle, pageStyle, sectionTitleStyle, selectedCardStyle,
} from "../common/styles";
import useAutoSelectFirst from "../../hooks/useAutoSelectFirst";
import useDetail from "../../hooks/useDetail";
import useFilterOptions from "../../hooks/useFilterOptions";
import useList from "../../hooks/useList";
import useListParams from "../../hooks/useListParams";
import useScrollToDetailsOnSmallScreens from "../../hooks/useScrollToDetailsOnSmallScreens";
import { activeFilterChips } from "../../lib/filters";
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

const FILTERS = [
    { key: "search", label: "Search", format: (value) => `"${value}"` },
    { key: "agency", label: "Agency" },
    { key: "category", label: "Category" },
    { key: "status", label: "Status", format: (value) => STATUS_OPTIONS.find((o) => o.value === value)?.label || value },
    { key: "min_funding", label: "Estimated funding", format: (value) => `${formatMoney(value)}+` },
];

const idOf = (opportunity) => String(opportunity.opp_id);

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
    const matches = useDetail("/opportunities/", params.selected, "matches/");

    const scrollToDetails = useScrollToDetailsOnSmallScreens("[data-opportunity-details]", detail.data);
    // Clicking the item already shown only scrolls to it (on phones).
    const select = useCallback((id) => {
        if (id === params.selected) {
            scrollToDetails(true);
            return;
        }
        scrollToDetails();
        update({ selected: id }, { keepPage: true, push: true });
    }, [update, scrollToDetails, params.selected]);
    const selectFirst = useCallback((id) => update({ selected: id }, { keepPage: true }), [update]);
    useAutoSelectFirst(opportunities, idOf, params.selected, loading, selectFirst);

    const changePage = (page) => {
        update({ page });
        window.scrollTo({ top: 0 });
    };

    const canClear = Boolean(params.search || params.agency || params.category || params.status
        || params.min_funding || params.sort !== DEFAULTS.sort || params.order !== DEFAULTS.order);

    const selected = detail.data;

    return (
        <div className="page" style={pageStyle}>
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
                activeFilters={activeFilterChips(FILTERS, params, update)}
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
                                <h3 style={{ margin: 0, fontSize: "17px" }}>{opportunity.title}</h3>
                                <DeadlineBadge dueDate={opportunity.due_date} />
                            </div>
                            <p style={metaStyle}>{opportunity.agency || "Agency not available"}</p>
                            <p style={{ ...metaStyle, ...mutedStyle, fontSize: "14px" }}>
                                {opportunity.estimated_funding != null
                                    ? `${formatMoney(opportunity.estimated_funding)} estimated`
                                    : "Funding not available"}
                                {" · "}Due {formatDate(opportunity.due_date)}
                                {" · "}{opportunity.category || "Category not available"}
                            </p>
                        </div>
                    ))}

                    <Pagination
                        page={data?.current_page || 1}
                        totalPages={data?.total_pages || 1}
                        onPageChange={changePage}
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

                            <FieldGrid
                                fields={[
                                    { label: "Agency", value: selected.agency || NOT_AVAILABLE },
                                    { label: "Category", value: selected.category || NOT_AVAILABLE },
                                    { label: "Due date", value: formatDate(selected.due_date) },
                                    { label: "Estimated funding", value: formatMoney(selected.estimated_funding) },
                                    { label: "Award floor", value: formatMoney(selected.award_floor) },
                                    { label: "Award ceiling", value: formatMoney(selected.award_ceiling) },
                                ]}
                            />

                            <MatchCarousel
                                key={`matches-${selected.opp_id}`}
                                kind="opportunity"
                                data={matches.data}
                                loading={matches.loading}
                            />

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
                                <ul style={{ paddingLeft: "20px", marginBottom: 0 }}>
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

                    {!loading && opportunities.length === 0 && !params.selected && (
                        <p style={mutedStyle}>No opportunity to show.</p>
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
    marginBottom: "6px",
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
