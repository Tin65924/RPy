import React from 'react';
import { Github, BookOpen, Layers, Terminal, Home } from 'lucide-react';
import './Header.css';

export default function Header({ setView, currentView }) {
    return (
        <header className="header glass">
            <div className="container header-content">
                <div className="logo" onClick={() => setView('home')} style={{ cursor: 'pointer' }}>
                    <Layers className="logo-icon" />
                    <span className="logo-text">RPy <span className="logo-dot">.</span></span>
                </div>

                <nav className="nav">
                    {currentView === 'docs' ? (
                        <button onClick={() => setView('home')} className="nav-link">
                            <Home size={18} /> Home
                        </button>
                    ) : (
                        <>
                            <button
                                onClick={() => setView('docs')}
                                className={`nav-link ${currentView === 'docs' ? 'active' : ''}`}
                            >
                                <BookOpen size={18} /> Documentation
                            </button>
                            <a href="#features" className="nav-link">
                                <Terminal size={18} /> Features
                            </a>
                        </>
                    )}

                    <a href="https://github.com/Tin65924/RPy" target="_blank" rel="noopener noreferrer" className="nav-link github">
                        <Github size={18} /> GitHub
                    </a>
                </nav>
            </div>
        </header>
    );
}
