
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
        <nav style={navStyle}>
            <div style={brandStyle}>AUSME Research System</div>

            <div style={linksStyle}>
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

const navStyle = {
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