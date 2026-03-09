import React from 'react';
import './Footer.css';

export default function Footer() {
    return (
        <footer className="footer">
            <div className="container">
                <div className="footer-content">
                    <div className="footer-copyright">
                        © 2026 RPy Transpiler. Built for the Roblox community.
                    </div>
                    <div className="footer-links">
                        <a href="https://github.com/Tin65924/RPy" target="_blank" rel="noopener noreferrer">GitHub</a>
                        <a href="#docs">Documentation</a>
                        <a href="#playground">Playground</a>
                    </div>
                </div>
            </div>
        </footer>
    );
}
