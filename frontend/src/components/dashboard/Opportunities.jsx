
import React, { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE;

function Opportunities() {
    const [opportunities, setOpportunities] = useState([]);
    const [search, setSearch] = useState("");
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCount, setTotalCount] = useState(0);

    const [selected, setSelected] = useState(null);
    const [loading, setLoading] = useState(true);
    const [detailLoading, setDetailLoading] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        const controller = new AbortController();

        async function loadOpportunities() {
            setLoading(true);
            setError("");

            try {
                const params = new URLSearchParams({
                    search,
                    page: String(page),
                });

                const response = await fetch(
                    `${API_BASE}/opportunities/?${params}`,
                    { signal: controller.signal }
                );

                if (!response.ok) {
                    throw new Error("Failed to load funding opportunities");
                }

                const data = await response.json();

                setOpportunities(data.results);
                setTotalCount(data.count);
                setTotalPages(data.total_pages);
            } catch (err) {
                if (err.name !== "AbortError") {
                    setError(err.message);
                }
            } finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        }

        loadOpportunities();

        return () => controller.abort();
    }, [search, page]);

    async function showDetails(id) {
        setDetailLoading(true);
        setSelected(null);
        setError("");

        try {
            const response = await fetch(
                `${API_BASE}/opportunities/${id}/`
            );

            if (!response.ok) {
                throw new Error("Failed to load opportunity details");
            }

            const data = await response.json();
            setSelected(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setDetailLoading(false);
        }
    }

    function formatMoney(value) {
        if (value === null || value === undefined || value === "") {
            return "Not available";
        }

        return Number(value).toLocaleString("en-US", {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 2
        });
    }

    function formatDate(value) {
        if (!value) return "Not available";
        return value.slice(0, 10);
    }

    return (
        <div style={{ padding: "40px", maxWidth: "1400px", margin: "auto" }}>
            <h1>Funding Opportunities</h1>

            <input
                type="text"
                placeholder="Search funding opportunities..."
                value={search}
                onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                    setSelected(null);
                }}
                style={inputStyle}
            />

            {error && <p style={{ color: "red" }}>{error}</p>}

            <p>{totalCount} opportunities found</p>

            <div style={layoutStyle}>
                <div style={{ flex: 1, minWidth: "300px" }}>
                    {loading ? (
                        <p>Loading opportunities...</p>
                    ) : (
                        opportunities.map((opportunity) => (
                            <div
                                key={opportunity.opp_id}
                                style={cardStyle}
                                onClick={() => showDetails(opportunity.opp_id)}
                            >
                                <h3>{opportunity.title}</h3>

                                <p>
                                    <strong>Agency:</strong>{" "}
                                    {opportunity.agency || "Not available"}
                                </p>

                                <p>
                                    <strong>Category:</strong>{" "}
                                    {opportunity.category || "Not available"}
                                </p>

                                <p>
                                    <strong>Estimated Funding:</strong>{" "}
                                    {formatMoney(opportunity.estimated_funding)}
                                </p>

                                <p>
                                    <strong>Due Date:</strong>{" "}
                                    {formatDate(opportunity.due_date)}
                                </p>
                            </div>
                        ))
                    )}

                    <div style={paginationStyle}>
                        <button
                            disabled={page <= 1 || loading}
                            onClick={() => {
                                setPage(page - 1);
                                setSelected(null);
                            }}
                        >
                            Previous
                        </button>

                        <span>Page {page} of {totalPages}</span>

                        <button
                            disabled={page >= totalPages || loading}
                            onClick={() => {
                                setPage(page + 1);
                                setSelected(null);
                            }}
                        >
                            Next
                        </button>
                    </div>
                </div>

                <div style={{ flex: 1, minWidth: "320px" }}>
                    {detailLoading && <p>Loading opportunity details...</p>}

                    {selected && (
                        <div style={cardStyle}>
                            <h2>{selected.title}</h2>

                            <p><strong>Agency:</strong> {selected.agency || "Not available"}</p>
                            <p><strong>Category:</strong> {selected.category || "Not available"}</p>

                            <p>
                                <strong>Estimated Funding:</strong>{" "}
                                {formatMoney(selected.estimated_funding)}
                            </p>

                            <p>
                                <strong>Award Floor:</strong>{" "}
                                {formatMoney(selected.award_floor)}
                            </p>

                            <p>
                                <strong>Award Ceiling:</strong>{" "}
                                {formatMoney(selected.award_ceiling)}
                            </p>

                            <p>
                                <strong>Due Date:</strong>{" "}
                                {formatDate(selected.due_date)}
                            </p>

                            <h3>Description</h3>
                            <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                                {selected.description || "Not available"}
                            </p>

                            <h3>Topics</h3>

                            {selected.topics?.length > 0 ? (
                                <ul>
                                    {selected.topics.map((topic, index) => (
                                        <li key={index}>
                                            {topic.topic} — Score:{" "}
                                            {Number(topic.score).toFixed(3)}
                                            {" | Source: "}
                                            {topic.source || "Not available"}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p>Not available</p>
                            )}

                            <h3>Domains</h3>

                            {selected.domains?.length > 0 ? (
                                <ul>
                                    {selected.domains.map((domain, index) => (
                                        <li key={index}>
                                            <strong>{domain.domain_name}</strong>
                                            <br />
                                            Confidence:{" "}
                                            {Number(domain.confidence_score).toFixed(3)}
                                            <br />
                                            Rationale:{" "}
                                            {domain.rationale || "Not available"}
                                            <br />
                                            Primary: {domain.is_primary ? "Yes" : "No"}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p>Not available</p>
                            )}
                        </div>
                    )}

                    {!selected && !detailLoading && (
                        <p>Select an opportunity to view its details.</p>
                    )}
                </div>
            </div>
        </div>
    );
}

const inputStyle = {
    width: "100%",
    padding: "14px",
    marginBottom: "20px",
    border: "1px solid #ccc",
    borderRadius: "8px",
    boxSizing: "border-box"
};

const layoutStyle = {
    display: "flex",
    gap: "25px",
    flexWrap: "wrap"
};

const cardStyle = {
    padding: "20px",
    marginBottom: "15px",
    backgroundColor: "white",
    border: "1px solid #ddd",
    borderRadius: "10px",
    overflowWrap: "anywhere",
    whiteSpace: "pre-line"
};

const paginationStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "20px",
    padding: "20px"
};

export default Opportunities;