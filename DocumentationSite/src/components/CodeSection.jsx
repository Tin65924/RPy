import React, { useState } from 'react';
import { Code2, ArrowRight } from 'lucide-react';
import './CodeSection.css';

const example = {
    python: `"""
A simple item class.
"""
class Item:
    """Represents a collectible item."""
    def __init__(self, name):
        """Initialize the item."""
        self.name = name

apple = Item("Apple")
`,
    luau: `-- A simple item class.
local Item = {}
Item.__index = Item

-- Represents a collectible item.
-- Initialize the item.
function Item.new(name)
    local self = setmetatable({}, Item)
    self.name = name
    return self
end

local apple = Item.new("Apple")

return { Item = Item, apple = apple }
`
};

export default function CodeSection() {
    return (
        <section className="code-section">
            <div className="container">
                <div className="code-header">
                    <div className="badge-small">Comparison</div>
                    <h2 className="section-title">Clean, professional <span className="gradient-text">conversion.</span></h2>
                    <p className="section-subtitle">No boilerplate. No magic. Just high-quality Luau code that you can understand and debug.</p>
                </div>

                <div className="code-comparison">
                    <div className="code-block python-block">
                        <div className="block-header">
                            <span className="lang">Python</span>
                            <Code2 size={16} />
                        </div>
                        <pre><code>{example.python}</code></pre>
                    </div>

                    <div className="code-arrow">
                        <ArrowRight size={32} />
                    </div>

                    <div className="code-block luau-block">
                        <div className="block-header">
                            <span className="lang">Luau</span>
                            <Code2 size={16} />
                        </div>
                        <pre><code>{example.luau}</code></pre>
                    </div>
                </div>
            </div>
        </section>
    );
}
