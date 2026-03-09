import React, { useState } from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import Features from './components/Features';
import CodeSection from './components/CodeSection';
import Footer from './components/Footer';
import Docs from './pages/Docs';

function App() {
    const [view, setView] = useState('home'); // 'home' or 'docs'

    return (
        <div className="app">
            <Header setView={setView} currentView={view} />
            <main>
                {view === 'home' ? (
                    <>
                        <Hero setView={setView} />
                        <Features />
                        <CodeSection />
                        <Footer />
                    </>
                ) : (
                    <Docs />
                )}
            </main>
        </div>
    );
}

export default App;
