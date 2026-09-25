import React from "react";
import {
    BrowserRouter,
    Navigate,
    Outlet,
    Route,
    Routes
} from "react-router-dom";

import Dashboard from "./components/dashboard/Dashboard";
import Researchers from "./components/dashboard/Researchers";
import Papers from "./components/dashboard/Papers";
import Opportunities from "./components/dashboard/Opportunities";
import Navigation from "./components/dashboard/Navigation";

function ResearchLayout() {
    return (
        <>
            <Navigation />
            <Outlet />
        </>
    );
}

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route element={<ResearchLayout />}>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/researchers" element={<Researchers />} />
                    <Route path="/papers" element={<Papers />} />
                    <Route path="/opportunities" element={<Opportunities />} />
                </Route>

                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
