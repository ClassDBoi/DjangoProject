import React, { useCallback } from "react";
import { Link } from "react-router-dom";

import CollegeBadge from "../common/CollegeBadge";
import ExpandableText from "../common/ExpandableText";
import KeywordChips from "../common/KeywordChips";
import ListToolbar, { FilterSelect } from "../common/ListToolbar";
import {
    cardStyle, detailCardStyle, detailColumnStyle, layoutStyle, linkStyle, listColumnStyle,
    metaStyle, mutedStyle, pageStyle, sectionTitleStyle, selectedCardStyle,
} from "../common/styles";
import useDeselectOnOutsideClick from "./useDeselectOnOutsideClick";
import useDetail from "../../hooks/useDetail";
import useFilterOptions from "../../hooks/useFilterOptions";
import useList from "../../hooks/useList";
import useListParams from "../../hooks/useListParams";
import useScrollToDetailsOnSmallScreens from "../../hooks/useScrollToDetailsOnSmallScreens";
import { NOT_AVAILABLE, formatDate } from "../../lib/format";

// Every URL parameter this page uses, with its default.
const DEFAULTS = { search: "", college: "", department: "", sort: "name", order: "asc", selected: "" };

const SORT_OPTIONS = [
    { value: "name", label: "Name" },
    { value: "department", label: "Department" },
    { value: "college", label: "College" },
    { value: "auid", label: "AUID" },
    { value: "papers", label: "Number of papers" },
];

function Researchers() {
    const [params, update, clear] = useListParams(DEFAULTS);
    const options = useFilterOptions();

    const { data, loading, error } = useList("/researchers/", {
        search: params.search,
        college: params.college,
        department: params.department,
        sort: params.sort,
        order: params.order,
    });
    const researchers = data || [];
    const detail = useDetail("/researchers/", params.selected);

    const select = useCallback((auid) => update({ selected: auid }, { keepPage: true, push: true }), [update]);
    const deselect = useCallback(() => update({ selected: "" }, { keepPage: true }), [update]);

    // Click anywhere outside the cards and detail panel to clear the selection.
    useDeselectOnOutsideClick("[data-researcher-card], [data-researcher-details]", deselect);
    useScrollToDetailsOnSmallScreens("[data-researcher-details]", detail.data);

    // Departments of the chosen college only.
    const departments = (options?.researchers.departments || [])
        .filter((item) => !params.college || item.college === params.college)
        .map((item) => item.department);

    const canClear = Boolean(params.search || params.college || params.department
        || params.sort !== DEFAULTS.sort || params.order !== DEFAULTS.order);

    const selected = detail.data;
    const papers = [...(selected?.papers || [])].sort(
        (a, b) => String(b.publication_date || "").localeCompare(String(a.publication_date || ""))
    );

    return (
        <div style={pageStyle}>
            <h1>Researchers</h1>

            <ListToolbar
                search={params.search}
                onSearch={(search) => update({ search })}
                placeholder="Search by name, AUID, department or college..."
                sortOptions={SORT_OPTIONS}
                sort={params.sort}
                order={params.order}
                onSortChange={update}
                resultText={loading ? "Loading researchers..." : `${researchers.length} researchers found`}
                canClear={canClear}
                onClear={clear}
            >
                <FilterSelect
                    label="College"
                    value={params.college}
                    onChange={(college) => update({ college, department: "" })}
                    options={options?.researchers.colleges || []}
                    allLabel="All colleges"
                />
                <FilterSelect
                    label="Department"
                    value={params.department}
                    onChange={(department) => update({ department })}
                    options={departments}
                    allLabel="All departments"
                />
            </ListToolbar>

            {error && <p style={{ color: "red" }}>{error}</p>}

            <div style={layoutStyle}>
                <div style={listColumnStyle}>
                    {!loading && researchers.length === 0 && (
                        <p style={mutedStyle}>No researchers match your search.</p>
                    )}

                    {researchers.map((researcher) => (
                        <div
                            key={researcher.auid}
                            data-researcher-card
                            style={researcher.auid === params.selected ? selectedCardStyle : cardStyle}
                            onClick={() => select(researcher.auid)}
                        >
                            <div style={cardHeaderStyle}>
                                <CollegeBadge college={researcher.college} />
                                <div>
                                    <h3 style={{ margin: "0 0 4px" }}>{researcher.name}</h3>
                                    <p style={metaStyle}>{researcher.title || NOT_AVAILABLE}</p>
                                </div>
                            </div>
                            <p style={metaStyle}>{researcher.department || NOT_AVAILABLE}</p>
                            <p style={{ ...metaStyle, ...mutedStyle }}>
                                {researcher.college || "College not available"}
                                {" · "}{researcher.paper_count} paper{researcher.paper_count === 1 ? "" : "s"}
                                {" · "}AUID {researcher.auid}
                            </p>
                        </div>
                    ))}
                </div>

                <div data-researcher-details style={{ ...detailColumnStyle, flex: 2 }}>
                    {detail.loading && <p>Loading details...</p>}
                    {detail.error && <p style={{ color: "red" }}>{detail.error}</p>}

                    {selected && (
                        <div style={detailCardStyle}>
                            <div style={cardHeaderStyle}>
                                <CollegeBadge college={selected.college} size={56} />
                                <div>
                                    <h2 style={{ margin: "0 0 4px" }}>{selected.name}</h2>
                                    <p style={metaStyle}>{selected.title || NOT_AVAILABLE}</p>
                                </div>
                            </div>

                            <p style={metaStyle}><strong>Department:</strong> {selected.department || NOT_AVAILABLE}</p>
                            <p style={metaStyle}><strong>College:</strong> {selected.college || NOT_AVAILABLE}</p>
                            <p style={metaStyle}><strong>AUID:</strong> {selected.auid}</p>

                            <h3 style={sectionTitleStyle}>Research Papers ({papers.length})</h3>

                            {papers.length > 0 ? (
                                papers.map((paper) => (
                                    <div key={paper.id} style={paperStyle}>
                                        <Link to={`/papers?selected=${paper.id}`} style={{ ...linkStyle, fontSize: "16px" }}>
                                            {paper.title}
                                        </Link>

                                        <p style={{ ...metaStyle, ...mutedStyle, marginTop: "6px" }}>
                                            {formatDate(paper.publication_date)}
                                            {" · "}{paper.published_in || "Journal not available"}
                                            {" · "}{paper.total_citations ?? 0} citations
                                        </p>

                                        <ExpandableText
                                            key={paper.abstract}
                                            title="Abstract"
                                            text={paper.abstract}
                                            previewWords={40}
                                        />

                                        <KeywordChips
                                            items={(paper.keywords || []).map((k) => ({ label: k.keyword, score: k.score }))}
                                        />
                                    </div>
                                ))
                            ) : (
                                <p>No associated papers found.</p>
                            )}
                        </div>
                    )}

                    {!params.selected && (
                        <p style={mutedStyle}>Select a researcher to view details.</p>
                    )}
                </div>
            </div>
        </div>
    );
}

const cardHeaderStyle = {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    marginBottom: "8px",
};

const paperStyle = {
    padding: "15px",
    marginTop: "15px",
    border: "1px solid #eee",
    borderRadius: "8px",
};

export default Researchers;
