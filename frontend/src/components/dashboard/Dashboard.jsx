import React, { useEffect, useState } from "react";

import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    LabelList,
    ResponsiveContainer
} from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE;

function HistogramCard({ title, data, xLabel = "Word-count range", note }) {
    return (
        <div style={chartCard}>
            <h3>{title}</h3>

            <ResponsiveContainer width="100%" height={320}>
                <BarChart
                    data={data}
                    margin={{ top: 25, right: 20, left: 0, bottom: 20 }}
                >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                        dataKey="range"
                        label={{
                            value: xLabel,
                            position: "insideBottom",
                            offset: -10
                        }}
                    />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#236FA5">
                        <LabelList dataKey="count" position="top" />
                    </Bar>
                </BarChart>
            </ResponsiveContainer>

            {note && <p style={chartNoteStyle}>{note}</p>}
        </div>
    );
}

function Dashboard() {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        fetch(`${API_BASE}/dashboard/`)
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to fetch dashboard data");
                }
                return response.json();
            })
            .then((data) => {
                setStats(data);
            })
            .catch((err) => {
                setError(err.message);
            })
            .finally(() => {
                setLoading(false);
            });
    }, []);

    if (loading) {
        return <p>Loading dashboard...</p>;
    }

    if (error) {
        return <p>Error: {error}</p>;
    }

    const chunkWords = stats.rag_chunk_assumptions?.chunk_words ?? 500;
    const overlapWords = stats.rag_chunk_assumptions?.overlap_words ?? 75;

    return (
        <div style={{ padding: "40px" }}>
            <h1>Research Dashboard</h1>

            <div style={statsContainer}>
                <div style={cardStyle}>
                    <h2>Researchers</h2>
                    <h1>{stats.researchers}</h1>
                </div>

                <div style={cardStyle}>
                    <h2>Research Papers</h2>
                    <h1>{stats.papers}</h1>
                </div>

                <div style={cardStyle}>
                    <h2>Funding Opportunities</h2>
                    <h1>{stats.opportunities}</h1>
                </div>

                <div style={cardStyle}>
                    <h2>Papers with Abstracts</h2>
                    <h1>{stats.papers_with_abstracts}</h1>
                    <p style={cardSubtextStyle}>of {stats.papers}</p>
                </div>

                <div style={cardStyle}>
                    <h2>Full Announcements</h2>
                    <h1>{stats.opportunities_with_full_announcements}</h1>
                    <p style={cardSubtextStyle}>of {stats.opportunities}</p>
                </div>
            </div>

            <h2 style={{ marginTop: "40px" }}>Dataset Analysis</h2>


            <div style={chartsContainer}>
                <HistogramCard
                    title="Paper Title Lengths"
                    data={stats.paper_title_lengths}
                />

                <HistogramCard
                    title="Paper Abstract / Description Lengths"
                    data={stats.paper_abstract_lengths}
                />

                <HistogramCard
                    title="Short Funding Description Lengths"
                    data={stats.funding_description_lengths}
                />

                <HistogramCard
                    title="Full Funding Announcement Lengths"
                    data={stats.funding_full_announcement_lengths}
                />

                <HistogramCard
                    title="Estimated RAG Chunks per Full Announcement"
                    data={stats.funding_rag_chunk_estimates}
                    xLabel="Estimated chunk-count range"
                    note={`Planning estimate only: ${chunkWords} words per chunk with ${overlapWords} words of overlap. Final retrieval should use meaningful document sections where possible.`}
                />
            </div>
        </div>
    );
}

const statsContainer = {
    display: "flex",
    gap: "20px",
    flexWrap: "wrap"
};

const cardStyle = {
    padding: "25px",
    border: "1px solid #ddd",
    borderRadius: "10px",
    minWidth: "220px",
    backgroundColor: "white",
    boxShadow: "0 2px 6px rgba(0,0,0,0.08)"
};

const cardSubtextStyle = {
    margin: 0,
    color: "#666"
};

const chartsContainer = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))",
    gap: "20px",
    marginTop: "20px"
};

const chartCard = {
    backgroundColor: "white",
    padding: "20px",
    border: "1px solid #ddd",
    borderRadius: "10px",
    minWidth: 0
};

const chartNoteStyle = {
    margin: "8px 0 0",
    color: "#666",
    fontSize: "0.9rem",
    lineHeight: 1.4
};

export default Dashboard;
