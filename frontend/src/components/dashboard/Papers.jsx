
import React, { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE;

function Papers() {
    const [papers, setPapers] = useState([]);
    const [researchers, setResearchers] = useState([]);
    const [search, setSearch] = useState("");
    const [researcher, setResearcher] = useState("");
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCount, setTotalCount] = useState(0);
    const [selected, setSelected] = useState(null);
    const [loading, setLoading] = useState(true);
    const [detailLoading, setDetailLoading] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        fetch(`${API_BASE}/researchers/`)
            .then((res) => {
                if (!res.ok) throw new Error("Failed to load researchers");
                return res.json();
            })
            .then(setResearchers)
            .catch((err) => setError(err.message));
    }, []);

    useEffect(() => {
        const controller = new AbortController();

        async function loadPapers() {
            setLoading(true);
            setError("");

            try {
                const params = new URLSearchParams({
                    search,
                    researcher,
                    page: String(page),
                });

                const response = await fetch(
                    `${API_BASE}/papers/?${params}`,
                    { signal: controller.signal }
                );

                if (!response.ok) {
                    throw new Error("Failed to load papers");
                }

                const data = await response.json();

                setPapers(data.results);
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

        loadPapers();

        return () => controller.abort();
    }, [search, researcher, page]);

    async function showDetails(id) {
        setDetailLoading(true);
        setSelected(null);
        setError("");

        try {
            const response = await fetch(`${API_BASE}/papers/${id}/`);

            if (!response.ok) {
                throw new Error("Failed to load paper details");
            }

            const data = await response.json();
            setSelected(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setDetailLoading(false);
        }
    }

    return (
        <div style={{ padding: "40px", maxWidth: "1400px", margin: "auto" }}>
            <h1>Research Papers</h1>

            <div style={filterStyle}>
                <input
                    type="text"
                    placeholder="Search papers by title..."
                    value={search}
                    onChange={(e) => {
                        setSearch(e.target.value);
                        setPage(1);
                    }}
                    style={inputStyle}
                />

                <select
                    value={researcher}
                    onChange={(e) => {
                        setResearcher(e.target.value);
                        setPage(1);
                    }}
                    style={inputStyle}
                >
                    <option value="">All Researchers</option>
                    {researchers.map((r) => (
                        <option key={r.auid} value={r.auid}>
                            {r.name}
                        </option>
                    ))}
                </select>
            </div>

            {error && <p style={{ color: "red" }}>{error}</p>}

            <p>{totalCount} papers found</p>

            <div style={layoutStyle}>
                <div style={{ flex: 1, minWidth: "300px" }}>
                    {loading ? (
                        <p>Loading papers...</p>
                    ) : (
                        papers.map((paper) => (
                            <div
                                key={paper.id}
                                style={cardStyle}
                                onClick={() => showDetails(paper.id)}
                            >
                                <h3>{paper.title}</h3>

                                <p>
                                    <strong>Authors:</strong>{" "}
                                    {paper.authors_display || "Not available"}
                                </p>

                                <p>
                                    <strong>Published:</strong>{" "}
                                    {paper.publication_date || "Not available"}
                                </p>

                                <p>
                                    <strong>Citations:</strong>{" "}
                                    {paper.total_citations ?? "Not available"}
                                </p>
                            </div>
                        ))
                    )}

                    <div style={paginationStyle}>
                        <button
                            disabled={page <= 1 || loading}
                            onClick={() => setPage(page - 1)}
                        >
                            Previous
                        </button>

                        <span>Page {page} of {totalPages}</span>

                        <button
                            disabled={page >= totalPages || loading}
                            onClick={() => setPage(page + 1)}
                        >
                            Next
                        </button>
                    </div>
                </div>

                <div style={{ flex: 1, minWidth: "320px" }}>
                    {detailLoading && <p>Loading paper details...</p>}

                    {selected && (
                        <div style={cardStyle}>
                            <h2>{selected.title}</h2>

                            <p>
                                <strong>Authors:</strong>{" "}
                                {selected.authors_display || "Not available"}
                            </p>

                            <p>
                                <strong>Publication Date:</strong>{" "}
                                {selected.publication_date || "Not available"}
                            </p>

                            <p>
                                <strong>Published In:</strong>{" "}
                                {selected.published_in || "Not available"}
                            </p>

                            <p>
                                <strong>Citations:</strong>{" "}
                                {selected.total_citations ?? "Not available"}
                            </p>

                            <p>
                                <strong>Abstract:</strong>{" "}
                                {selected.abstract || "Not available"}
                            </p>

                            <h3>Associated Researchers</h3>

                            {selected.researchers?.length > 0 ? (
                                <ul>
                                    {selected.researchers.map((r) => (
                                        <li key={r.auid}>{r.name}</li>
                                    ))}
                                </ul>
                            ) : (
                                <p>Not available</p>
                            )}

                            <h3>Keywords and Scores</h3>

                            {selected.keywords?.length > 0 ? (
                                <ul>
                                    {selected.keywords.map((keyword, index) => (
                                        <li key={index}>
                                            {keyword.keyword} — Score:{" "}
                                            {Number(keyword.score).toFixed(3)}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p>Not available</p>
                            )}
                        </div>
                    )}

                    {!selected && !detailLoading && (
                        <p>Select a paper to view its details.</p>
                    )}
                </div>
            </div>
        </div>
    );
}

const filterStyle = {
    display: "flex",
    gap: "15px",
    flexWrap: "wrap",
    marginBottom: "20px"
};

const inputStyle = {
    padding: "12px",
    border: "1px solid #ccc",
    borderRadius: "8px",
    flex: 1,
    minWidth: "250px"
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
    cursor: "pointer",
    overflowWrap: "anywhere"
};

const paginationStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "20px",
    padding: "20px"
};

export default Papers;