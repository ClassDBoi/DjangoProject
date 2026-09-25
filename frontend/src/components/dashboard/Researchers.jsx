import React, { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE;

function Researchers() {
    const [researchers, setResearchers] = useState([]);
    const [search, setSearch] = useState("");
    const [selected, setSelected] = useState(null);
    const [loading, setLoading] = useState(true);
    const [detailLoading, setDetailLoading] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        const controller = new AbortController();

        async function loadResearchers() {
            setLoading(true);
            setError("");

            try {
                const response = await fetch(
                    `${API_BASE}/researchers/?search=${encodeURIComponent(search)}`,
                    { signal: controller.signal }
                );

                if (!response.ok) {
                    throw new Error("Failed to load researchers");
                }

                const data = await response.json();
                setResearchers(data);
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

        loadResearchers();

        return () => controller.abort();
    }, [search]);

    async function showDetails(auid) {
        setDetailLoading(true);
        setSelected(null);
        setError("");

        try {
            const response = await fetch(
                `${API_BASE}/researchers/${encodeURIComponent(auid)}/`
            );

            if (!response.ok) {
                throw new Error("Failed to load researcher details");
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
        <div style={{ padding: "40px", maxWidth: "1200px", margin: "auto" }}>
            <h1>Researchers</h1>

            <input
                type="text"
                placeholder="Search researchers by name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={inputStyle}
            />

            {error && <p style={{ color: "red" }}>{error}</p>}

            {loading ? (
                <p>Loading researchers...</p>
            ) : (
                <p>{researchers.length} researchers found</p>
            )}

            <div style={layoutStyle}>
                <div style={{ flex: 1, minWidth: "280px" }}>
                    {researchers.map((researcher) => (
                        <div
                            key={researcher.auid}
                            style={cardStyle}
                            onClick={() => showDetails(researcher.auid)}
                        >
                            <h3>{researcher.name}</h3>
                            <p>{researcher.title || "Not available"}</p>
                            <p>{researcher.department || "Not available"}</p>
                        </div>
                    ))}
                </div>

                <div style={{ flex: 2, minWidth: "320px" }}>
                    {detailLoading && <p>Loading details...</p>}

                    {selected && (
                        <div style={cardStyle}>
                            <h2>{selected.name}</h2>

                            <p><strong>Title:</strong> {selected.title || "Not available"}</p>
                            <p><strong>Department:</strong> {selected.department || "Not available"}</p>
                            <p><strong>College:</strong> {selected.college || "Not available"}</p>

                            <h3>Associated Research Papers</h3>

                            {selected.papers?.length > 0 ? (
                                selected.papers.map((paper) => (
                                    <div key={paper.id} style={paperStyle}>
                                        <h4>{paper.title}</h4>

                                        <p>
                                            <strong>Publication Date:</strong>{" "}
                                            {paper.publication_date || "Not available"}
                                        </p>

                                        <p>
                                            <strong>Published In:</strong>{" "}
                                            {paper.published_in || "Not available"}
                                        </p>

                                        <p>
                                            <strong>Citations:</strong>{" "}
                                            {paper.total_citations ?? "Not available"}
                                        </p>

                                        <strong>Keywords:</strong>

                                        {paper.keywords?.length > 0 ? (
                                            <ul>
                                                {paper.keywords.map((keyword, index) => (
                                                    <li key={index}>
                                                        {keyword.keyword} — Score: {keyword.score}
                                                    </li>
                                                ))}
                                            </ul>
                                        ) : (
                                            <p>Not available</p>
                                        )}
                                    </div>
                                ))
                            ) : (
                                <p>No associated papers found.</p>
                            )}
                        </div>
                    )}

                    {!selected && !detailLoading && (
                        <p>Select a researcher to view details.</p>
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
    cursor: "pointer"
};

const paperStyle = {
    padding: "15px",
    marginTop: "15px",
    border: "1px solid #eee",
    borderRadius: "8px"
};

export default Researchers;