import React from 'react';
import { Zap, Cpu, Code2, ShieldCheck, Box, MessageSquareCode } from 'lucide-react';
import './Features.css';

const features = [
    {
        icon: <Zap size={24} />,
        title: "High Performance",
        description: "Built on a modular AST-based transpilation engine, RPy converts Python to high-quality Luau code in milliseconds."
    },
    {
        icon: <Box size={24} />,
        title: "Roblox Native Sync",
        description: "Automatic .server.lua, .client.lua, and module mappings. Sync your changes to Roblox Studio with the RPy dev server."
    },
    {
        icon: <MessageSquareCode size={24} />,
        title: "Docstring Support",
        description: "Full support for Python docstrings, automatically translated into Luau multiline comments for professional documentation."
    },
    {
        icon: <Cpu size={24} />,
        title: "Type Inferrer",
        description: "Optional typed mode adds Luau type annotations to your generated code for better IDE support and runtime stability."
    },
    {
        icon: <Code2 size={24} />,
        title: "Modern Syntax",
        description: "Supports f-strings, list comprehensions, decorators, and basic class inheritance for a modern coding experience."
    },
    {
        icon: <ShieldCheck size={24} />,
        title: "Production Ready",
        description: "Strict compiler checks and a robust runtime helper library ensure your code runs reliably on any Roblox server."
    }
];

export default function Features() {
    return (
        <section id="features" className="features">
            <div className="container">
                <div className="section-header">
                    <h2 className="section-title">Everything you need to <span className="gradient-text">Master Roblox Scripting</span></h2>
                    <p className="section-subtitle">RPy bridges the gap between Python's productivity and Roblox's ecosystem.</p>
                </div>

                <div className="features-grid">
                    {features.map((f, i) => (
                        <div key={i} className="feature-card card">
                            <div className="feature-icon">{f.icon}</div>
                            <h3 className="feature-title">{f.title}</h3>
                            <p className="feature-description">{f.description}</p>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
