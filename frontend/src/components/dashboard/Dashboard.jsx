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

    return (
        <div style={{ padding: "40px" }}>
            <h1>Research Dashboard</h1>

            {/* Database statistics */}
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
            </div>

            {/* Data analysis charts */}
            <h2 style={{ marginTop: "40px" }}>Dataset Analysis</h2>

            <div style={chartsContainer}>

                <div style={chartCard}>
                    <h3>Paper Title Lengths</h3>

                    <ResponsiveContainer width="100%" height={320}>
                        <BarChart
                            data={stats.paper_title_lengths}
                            margin={{ top: 25, right: 20, left: 0, bottom: 20 }}
                        >
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis
                                dataKey="range"
                                label={{
                                    value: "Word-count range",
                                    position: "insideBottom",
                                    offset: -10
                                }}
                            />
                            <YAxis allowDecimals={false} />
                            <Tooltip />
                            <Bar dataKey="count" fill="#236FA5">
                                <LabelList
                                    dataKey="count"
                                    position="top"
                                />
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                <div style={chartCard}>
                    <h3>Funding Description Lengths</h3>

                    <ResponsiveContainer width="100%" height={320}>
                        <BarChart
                            data={stats.funding_description_lengths}
                            margin={{ top: 25, right: 20, left: 0, bottom: 20 }}
                        >
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis
                                dataKey="range"
                                label={{
                                    value: "Word-count range",
                                    position: "insideBottom",
                                    offset: -10
                                }}
                            />
                            <YAxis allowDecimals={false} />
                            <Tooltip />
                            <Bar dataKey="count" fill="#236FA5">
                                <LabelList
                                    dataKey="count"
                                    position="top"
                                />
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>

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

export default Dashboard;