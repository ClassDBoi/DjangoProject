import React, { useCallback } from "react";
import { Link } from "react-router-dom";

import ExpandableText from "../common/ExpandableText";
import FieldGrid from "../common/FieldGrid";
import KeywordChips from "../common/KeywordChips";
import ListToolbar, { FilterSelect } from "../common/ListToolbar";
import Pagination from "../common/Pagination";
import ResearcherPhoto from "../common/ResearcherPhoto";
import {
    cardStyle, detailCardStyle, detailColumnStyle, layoutStyle, linkStyle, listColumnStyle,
    metaStyle, mutedStyle, pageStyle, sectionTitleStyle, selectedCardStyle,
} from "../common/styles";
import useAutoSelectFirst from "../../hooks/useAutoSelectFirst";
import useDetail from "../../hooks/useDetail";
import useFilterOptions from "../../hooks/useFilterOptions";
import useList from "../../hooks/useList";
import useListParams from "../../hooks/useListParams";
import useScrollToDetailsOnSmallScreens from "../../hooks/useScrollToDetailsOnSmallScreens";
import { activeFilterChips } from "../../lib/filters";
import { NOT_AVAILABLE, formatDate } from "../../lib/format";

// Every URL parameter this page uses, with its default.
const DEFAULTS = {
    search: "", researcher: "", year_from: "", year_to: "", min_citations: "",
    sort: "title", order: "asc", page: "1", selected: "",
};

const SORT_OPTIONS = [
    { value: "title", label: "Title" },
    { value: "date", label: "Publication date" },
    { value: "citations", label: "Citations" },
    { value: "journal", label: "Journal" },
];

const CITATION_OPTIONS = [1, 10, 25, 50, 100].map((n) => ({ value: String(n), label: `${n}+` }));

const idOf = (paper) => String(paper.id);

function Papers() {
    const [params, update, clear] = useListParams(DEFAULTS);
    const options = useFilterOptions();
    const researchers = useList("/researchers/", {}).data || [];

    const { data, loading, error } = useList("/papers/", {
        search: params.search,
        researcher: params.researcher,
        year_from: params.year_from,
        year_to: params.year_to,
        min_citations: params.min_citations,
        sort: params.sort,
        order: params.order,
        page: params.page,
    });
    const papers = data?.results || [];
    const detail = useDetail("/papers/", params.selected);

    const scrollToDetails = useScrollToDetailsOnSmallScreens("[data-paper-details]", detail.data);
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
    useAutoSelectFirst(papers, idOf, params.selected, loading, selectFirst);

    const changePage = (page) => {
        update({ page });
        window.scrollTo({ top: 0 });
    };

    const researcherName = (auid) => researchers.find((r) => r.auid === auid)?.name || auid;
    const filters = [
        { key: "search", label: "Search", format: (value) => `"${value}"` },
        { key: "researcher", label: "Researcher", format: researcherName },
        { key: "year_from", label: "Published from" },
        { key: "year_to", label: "Published to" },
        { key: "min_citations", label: "Citations", format: (value) => `${value}+` },
    ];

    const years = [];
    if (options?.papers.first_year && options?.papers.last_year) {
        for (let year = options.papers.last_year; year >= options.papers.first_year; year -= 1) {
            years.push(String(year));
        }
    }

    const canClear = Boolean(params.search || params.researcher || params.year_from || params.year_to
        || params.min_citations || params.sort !== DEFAULTS.sort || params.order !== DEFAULTS.order);

    const selected = detail.data;

    return (
        <div className="page" style={pageStyle}>
            <h1>Research Papers</h1>

            <ListToolbar
                search={params.search}
                onSearch={(search) => update({ search })}
                placeholder="Search by title, author, journal or keyword..."
                sortOptions={SORT_OPTIONS}
                sort={params.sort}
                order={params.order}
                onSortChange={update}
                resultText={loading && !data ? "Loading papers..." : `${data?.count ?? 0} papers found`}
                activeFilters={activeFilterChips(filters, params, update)}
                canClear={canClear}
                onClear={clear}
            >
                <FilterSelect
                    label="Researcher"
                    value={params.researcher}
                    onChange={(researcher) => update({ researcher })}
                    options={researchers.map((r) => ({ value: r.auid, label: r.name }))}
                    allLabel="All researchers"
                />
                <FilterSelect
                    label="Published from"
                    value={params.year_from}
                    onChange={(year_from) => update({ year_from })}
                    options={years}
                    allLabel="Any year"
                />
                <FilterSelect
                    label="Published to"
                    value={params.year_to}
                    onChange={(year_to) => update({ year_to })}
                    options={years}
                    allLabel="Any year"
                />
                <FilterSelect
                    label="Citations"
                    value={params.min_citations}
                    onChange={(min_citations) => update({ min_citations })}
                    options={CITATION_OPTIONS}
                    allLabel="Any"
                />
            </ListToolbar>

            {error && <p style={{ color: "red" }}>{error}</p>}

            <div style={layoutStyle}>
                <div style={listColumnStyle}>
                    {!loading && papers.length === 0 && (
                        <p style={mutedStyle}>No papers match your search.</p>
                    )}

                    {papers.map((paper) => (
                        <div
                            key={paper.id}
                            data-paper-card
                            style={String(paper.id) === params.selected ? selectedCardStyle : cardStyle}
                            onClick={() => select(String(paper.id))}
                        >
                            <h3 style={{ margin: "0 0 8px", fontSize: "17px" }}>{paper.title}</h3>
                            <p style={metaStyle}>{paper.authors_display || "Authors not available"}</p>
                            <p style={{ ...metaStyle, ...mutedStyle }}>
                                {formatDate(paper.publication_date)}
                                {" · "}{paper.published_in || "Journal not available"}
                                {" · "}{paper.total_citations ?? 0} citations
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

                <div data-paper-details style={detailColumnStyle}>
                    {detail.loading && <p>Loading paper details...</p>}
                    {detail.error && <p style={{ color: "red" }}>{detail.error}</p>}

                    {selected && (
                        <div style={detailCardStyle}>
                            <h2 style={{ margin: 0 }}>{selected.title}</h2>

                            <FieldGrid
                                fields={[
                                    { label: "Authors", value: selected.authors_display || NOT_AVAILABLE, wide: true },
                                    { label: "Published", value: formatDate(selected.publication_date) },
                                    { label: "Journal", value: selected.published_in || NOT_AVAILABLE },
                                    { label: "Citations", value: selected.total_citations ?? NOT_AVAILABLE },
                                ]}
                            />

                            <ExpandableText
                                key={selected.abstract}
                                title="Abstract / Research Description"
                                text={selected.abstract}
                                previewWords={80}
                                noun="abstract"
                            />

                            <h3 style={sectionTitleStyle}>Researchers</h3>
                            {selected.researchers?.length > 0 ? (
                                <div style={researcherListStyle}>
                                    {selected.researchers.map((r) => (
                                        <Link
                                            key={r.auid}
                                            to={`/researchers?selected=${encodeURIComponent(r.auid)}`}
                                            style={researcherLinkStyle}
                                        >
                                            <ResearcherPhoto auid={r.auid} name={r.name} size={32} />
                                            {r.name}
                                        </Link>
                                    ))}
                                </div>
                            ) : (
                                <p>{NOT_AVAILABLE}</p>
                            )}

                            <h3 style={sectionTitleStyle}>Keywords</h3>
                            <KeywordChips
                                items={(selected.keywords || []).map((k) => ({ label: k.keyword, score: k.score }))}
                            />
                        </div>
                    )}

                    {!loading && papers.length === 0 && !params.selected && (
                        <p style={mutedStyle}>No paper to show.</p>
                    )}
                </div>
            </div>
        </div>
    );
}

const researcherListStyle = {
    display: "flex",
    flexWrap: "wrap",
    gap: "10px 18px",
};

const researcherLinkStyle = {
    ...linkStyle,
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
};

export default Papers;
