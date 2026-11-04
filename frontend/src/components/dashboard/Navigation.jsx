
import React from "react";
import { NavLink } from "react-router-dom";

const links = [
    { path: "/dashboard", label: "Dashboard" },
    { path: "/researchers", label: "Researchers" },
    { path: "/papers", label: "Research Papers" },
    { path: "/opportunities", label: "Funding Opportunities" },
];

function Navigation() {
    return (
        <nav className="app-nav" style={navStyle}>
            <div style={brandStyle}>AUSME Research System</div>

            <div className="app-nav-links" style={linksStyle}>
                {links.map((link) => (
                    <NavLink
                        key={link.path}
                        to={link.path}
                        style={({ isActive }) => ({
                            ...linkStyle,
                            backgroundColor: isActive ? "#e86100" : "transparent",
                            color: "white",
                        })}
                    >
                        {link.label}
                    </NavLink>
                ))}
            </div>
        </nav>
    );
}

// Sticky: the bar stays at the top of the window while the page scrolls.
// Its height is var(--nav-height) in index.css; the detail panels use it to sit below the bar.
const navStyle = {
    position: "sticky",
    top: 0,
    zIndex: 100,
    minHeight: "var(--nav-height)",
    boxSizing: "border-box",
    boxShadow: "0 2px 8px rgba(12, 35, 64, 0.25)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: "15px",
    padding: "15px 30px",
    backgroundColor: "#10243d",
};

const brandStyle = {
    color: "white",
    fontWeight: "bold",
    fontSize: "20px",
};

const linksStyle = {
    display: "flex",
    gap: "10px",
    flexWrap: "wrap",
};

const linkStyle = {
    padding: "10px 15px",
    borderRadius: "6px",
    textDecoration: "none",
    fontWeight: "500",
};

export default Navigation;