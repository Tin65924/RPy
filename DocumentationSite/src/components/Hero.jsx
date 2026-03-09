import React from 'react';
import { motion } from 'framer-motion';
import { Terminal, MoveRight, ChevronRight, PlayCircle, BookOpen } from 'lucide-react';
import './Hero.css';

export default function Hero({ setView }) {
    return (
        <section className="hero">
            <div className="hero-bg">
                <div className="glow-1"></div>
                <div className="glow-2"></div>
            </div>

            <div className="container hero-container">
                <div className="hero-content">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6 }}
                        className="hero-badge"
                    >
                        <span className="badge-icon">✨</span>
                        <span className="badge-text">RPy V0.2.0 is arriving</span>
                        <ChevronRight size={14} className="badge-arrow" />
                    </motion.div>

                    <motion.h1
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.1 }}
                        className="hero-title"
                    >
                        Python power for <br />
                        <span className="gradient-text">Roblox Developers</span>
                    </motion.h1>

                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.2 }}
                        className="hero-description"
                    >
                        A high-performance Python to Luau transpiler designed for professional workflows.
                        Native Roblox dev server, modular AST handlers, and native Roblox type support.
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.3 }}
                        className="hero-actions"
                    >
                        <button className="btn btn-primary" onClick={() => setView('docs')}>
                            <BookOpen size={20} /> Get Started
                            <MoveRight size={18} className="btn-arrow" />
                        </button>
                        <button className="btn btn-secondary">
                            <PlayCircle size={20} /> Preview
                        </button>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.8, delay: 0.4 }}
                        className="hero-terminal glass"
                    >
                        <div className="terminal-header">
                            <div className="terminal-dots">
                                <div className="dot red"></div>
                                <div className="dot yellow"></div>
                                <div className="dot green"></div>
                            </div>
                            <div className="terminal-title">bash</div>
                        </div>
                        <div className="terminal-content">
                            <span className="prompt">$</span> rpy build src out
                            <br />
                            <span className="success">✓</span> Built 12 files → out
                            <br />
                            <span className="info">ℹ</span> RPy Dev Server: active
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    );
}
