import React, { useState } from 'react';
import {
    ChevronRight,
    Terminal,
    Code2,
    Box,
    Zap,
    ChevronDown,
    Search,
    BookOpen,
    Info,
    AlertTriangle,
    CheckCircle2,
    HelpCircle,
    Book,
    Lightbulb
} from 'lucide-react';
import './Docs.css';

const sections = [
    {
        id: 'getting-started',
        title: 'Getting Started',
        icon: <Zap size={18} />,
        items: [
            { id: 'intro', title: 'Introduction' },
            { id: 'installation', title: 'Installation' },
            { id: 'project-init', title: 'Project Initialization' },
            { id: 'changelog', title: 'Changelog (V0.2.0)' },
            { id: 'resources', title: 'External Resources' },
        ]
    },
    {
        id: 'cli-reference',
        title: 'CLI Reference',
        icon: <Terminal size={18} />,
        items: [
            { id: 'build', title: 'build' },
            { id: 'watch', title: 'watch' },
            { id: 'check', title: 'check' },
        ]
    },
    {
        id: 'syntax-mapping',
        title: 'Syntax Mapping',
        icon: <Code2 size={18} />,
        items: [
            { id: 'variables', title: 'Variables' },
            { id: 'functions', title: 'Functions' },
            { id: 'classes', title: 'Classes' },
            { id: 'loops', title: 'Loops' },
            { id: 'comprehensions', title: 'Comprehensions' },
            { id: 'imports', title: 'Modules & Imports' },
            { id: 'docstrings', title: 'Docstrings' },
            { id: 'roblox-events', title: 'Roblox Events' },
        ]
    },
    {
        id: 'roblox-sync',
        title: 'Roblox Syncing',
        icon: <Box size={18} />,
        items: [
            { id: 'script-types', title: 'Script Types' },
            { id: 'folder-mapping', title: 'Folder Structure' },
        ]
    },
    {
        id: 'roblox-api',
        title: 'Roblox API',
        icon: <Box size={18} />,
        items: [
            { id: 'services', title: 'Services' },
            { id: 'datatypes', title: 'Datatypes' },
            { id: 'globals', title: 'Globals' },
        ]
    },
    {
        id: 'builtins',
        title: 'Built-ins & Methods',
        icon: <Book size={18} />,
        items: [
            { id: 'builtin-functions', title: 'Global Functions' },
            { id: 'list-methods', title: 'List Methods' },
            { id: 'dict-methods', title: 'Dict Methods' },
            { id: 'string-methods', title: 'String Methods' },
        ]
    },
    {
        id: 'advanced',
        title: 'Advanced Concepts',
        icon: <Lightbulb size={18} />,
        items: [
            { id: 'performance', title: 'Performance & Shims' },
            { id: 'cli-internals', title: 'CLI Internals' },
        ]
    },
    {
        id: 'support',
        title: 'Support',
        icon: <HelpCircle size={18} />,
        items: [
            { id: 'troubleshooting', title: 'Troubleshooting' },
            { id: 'faq', title: 'FAQ' },
            { id: 'pitfalls', title: 'Common Pitfalls' },
        ]
    }
];

export default function Docs() {
    const [activeItem, setActiveItem] = useState('intro');

    return (
        <div className="docs-page">
            {/* Sidebar */}
            <aside className="docs-sidebar">
                <div className="sidebar-search">
                    <div className="search-box">
                        <Search size={16} />
                        <input type="text" placeholder="Search docs..." />
                    </div>
                </div>

                <nav className="sidebar-nav">
                    {sections.map(section => (
                        <div key={section.id} className="sidebar-section">
                            <div className="section-title-docs  ">
                                {section.icon}
                                <span>{section.title}</span>
                            </div>
                            <ul className="section-list">
                                {section.items.map(item => (
                                    <li key={item.id}>
                                        <button
                                            className={`nav-item ${activeItem === item.id ? 'active' : ''}`}
                                            onClick={() => setActiveItem(item.id)}
                                        >
                                            {item.title}
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </nav>
            </aside>

            {/* Main Content */}
            <main className="docs-content">
                <div className="content-container">
                    {activeItem === 'intro' && <Introduction />}
                    {activeItem === 'installation' && <Installation />}
                    {activeItem === 'script-types' && <ScriptTypes />}
                    {activeItem === 'classes' && <ClassesContent />}
                    {activeItem === 'build' && <CLIBuild />}
                    {activeItem === 'watch' && <CLIWatch />}
                    {activeItem === 'variables' && <VariablesContent />}
                    {activeItem === 'loops' && <LoopsContent />}
                    {activeItem === 'project-init' && <CLIInit />}
                    {activeItem === 'check' && <CLICheck />}
                    {activeItem === 'functions' && <FunctionsContent />}
                    {activeItem === 'comprehensions' && <ComprehensionsContent />}
                    {activeItem === 'folder-mapping' && <FolderStructureContent />}
                    {activeItem === 'troubleshooting' && <TroubleshootingContent />}
                    {activeItem === 'faq' && <FAQContent />}
                    {activeItem === 'pitfalls' && <PitfallsContent />}
                    {activeItem === 'imports' && <ImportsContent />}
                    {activeItem === 'docstrings' && <DocstringsContent />}
                    {activeItem === 'roblox-events' && <RobloxEventsContent />}
                    {activeItem === 'services' && <RobloxServicesContent />}
                    {activeItem === 'datatypes' && <RobloxDatatypesContent />}
                    {activeItem === 'globals' && <RobloxGlobalsContent />}
                    {activeItem === 'builtin-functions' && <BuiltinFunctionsContent />}
                    {activeItem === 'list-methods' && <ListMethodsContent />}
                    {activeItem === 'dict-methods' && <DictMethodsContent />}
                    {activeItem === 'string-methods' && <StringMethodsContent />}
                    {activeItem === 'performance' && <PerformanceContent />}
                    {activeItem === 'cli-internals' && <InternalsContent />}
                    {activeItem === 'changelog' && <ChangelogContent />}
                    {activeItem === 'resources' && <ResourcesContent />}

                    <div className="content-footer">
                        <div className="footer-nav">
                            <button className="nav-prev">
                                <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />
                                <span>Introduction</span>
                            </button>
                            <button className="nav-next">
                                <span>Installation</span>
                                <ChevronRight size={16} />
                            </button>
                        </div>
                    </div>
                </div>
            </main>

            {/* Right TOC (Hidden on small screens) 
            <aside className="docs-toc">
                <div className="toc-title">On this page</div>
                <ul className="toc-list">
                    <li className="toc-item active">Overview</li>
                    <li className="toc-item">Core Philosophy</li>
                    <li className="toc-item">Why RPy?</li>
                </ul>
            </aside>*/}
        </div>
    );
}

function Introduction() {
    return (
        <article className="prose">
            <div className="breadcrumb">Getting Started <ChevronRight size={14} /> Introduction</div>
            <h1 className="article-title">Introduction</h1>
            <p className="article-lead">
                RPy is a system that lets you write code in Python and converts it into Luau code that runs on Roblox.
            </p>

            <p>
                In plain language, it acts like a <strong>translator</strong> (or &quot;transpiler&quot;).
                Python is a powerful and easy-to-read language used by millions of developers.
                Roblox uses a language called Luau. RPy bridge the gap, so you can build complex systems for Roblox using the modern tools and syntax you already know from Python.
            </p>

            <div className="info-box card">
                <Info className="info-icon" />
                <div className="info-content">
                    <strong>Note:</strong> RPy is currently in V0.2.0 (Beta). Expect frequent updates and new feature additions.
                </div>
            </div>

            <h2>How it Works</h2>
            <p>
                The RPy pipeline is designed to be professional and predictable:
            </p>

            <div className="visual-diagram glass">
                <div className="diagram-step">
                    <span className="step-num">1</span>
                    <span className="step-text"><b>Source Code</b><br />Python (.py)</span>
                </div>
                <div className="diagram-arrow">→</div>
                <div className="diagram-step">
                    <span className="step-num">2</span>
                    <span className="step-text"><b>AST Parser</b><br />Scans syntax</span>
                </div>
                <div className="diagram-arrow">→</div>
                <div className="diagram-step">
                    <span className="step-num">3</span>
                    <span className="step-text"><b>Generator</b><br />Writes Luau</span>
                </div>
                <div className="diagram-arrow">→</div>
                <div className="diagram-step">
                    <span className="step-num">4</span>
                    <span className="step-text"><b>Output</b><br />Luau (.lua)</span>
                </div>
            </div>

            <h3>Key Terms</h3>
            <ul>
                <li><strong>AST (Abstract Syntax Tree):</strong> A tree representation of your code structure. RPy &quot;walks&quot; this tree to understand what you wrote before translating it.</li>
                <li><strong>Transpiler:</strong> A type of compiler that converts source code from one high-level language (Python) to another (Luau).</li>
                <li><strong>RPy Sync:</strong> The native syncing system that bridges local files into Roblox Studio.</li>
            </ul>

            <h3>Why RPy?</h3>
            <div className="grid-2">
                <div className="card-simple">
                    <h4><Zap size={18} color="#8b5cf6" /> Productivity</h4>
                    <p>Use Python's elegant syntax, comprehensions, and classes to build systems faster.</p>
                </div>
                <div className="card-simple">
                    <h4><Lightbulb size={18} color="#0ea5e9" /> Performance</h4>
                    <p>Generated Luau is nearly as fast as hand-written code, thanks to zero-cost abstractions.</p>
                </div>
            </div>
        </article>
    );
}

function Installation() {
    return (
        <article className="prose">
            <div className="breadcrumb">Getting Started <ChevronRight size={14} /> Installation</div>
            <h1 className="article-title">Installation</h1>

            <h2>Prerequisites</h2>
            <p>Before installing RPy, ensure your system has the following requirements:</p>
            <ul className="checklist">
                <li><CheckCircle2 size={16} /> <b>Python 3.10 or higher</b> (Required for modern AST support).</li>
                <li><CheckCircle2 size={16} /> <b>RPy Studio Plugin</b> (Used to receive synced files).</li>
            </ul>

            <p>Once ready, install RPy globally using pip:</p>

            <div className="code-snippet glass">
                <div className="snippet-header">bash</div>
                <pre><code>pip install rpy-transpiler</code></pre>
            </div>

            <div className="tip-box card">
                <Lightbulb className="tip-icon" />
                <div className="tip-content">
                    <strong>Pro Tip:</strong> Use a virtual environment (<code>venv</code>) to keep your project dependencies isolated.
                </div>
            </div>
            {/* NOT PUBLIC YET, SOON TO BE PUBLIC
            <h3>Local Development</h3>
            <p>Alternatively, you can clone the repository and install it in &quot;editable&quot; mode for local development:</p>

            <div className="code-snippet glass">
                <div className="snippet-header">bash</div>
                <pre><code>git clone https://github.com/Tin65924/RPy.git
                    cd RPy
                    pip install -e .</code></pre>
            </div>*/}
        </article>
    );
}

function ScriptTypes() {
    return (
        <article className="prose">
            <div className="breadcrumb">Roblox Syncing <ChevronRight size={14} /> Script Types</div>
            <h1 className="article-title">Script Types</h1>
            <p className="article-lead">RPy uses filename suffixes to detect "script intent." This tells the syncing server exactly which Roblox script instance to create.</p>

            <h3>The Mapping Table</h3>
            <p>Roblox has three main script types. In Python, you distinguish them using special naming conventions:</p>

            <table>
                <thead>
                    <tr>
                        <th>Python Suffix</th>
                        <th>Luau Output</th>
                        <th>Roblox Instance Type</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><code>file.server.py</code></td>
                        <td><code>file.server.lua</code></td>
                        <td><b>Script</b> (Runs on Server)</td>
                    </tr>
                    <tr>
                        <td><code>file.client.py</code></td>
                        <td><code>file.client.lua</code></td>
                        <td><b>LocalScript</b> (Runs on Client)</td>
                    </tr>
                    <tr>
                        <td><code>file.py</code></td>
                        <td><code>file.lua</code></td>
                        <td><b>ModuleScript</b> (Reusable Code)</td>
                    </tr>
                </tbody>
            </table>

            <div className="info-box card">
                <Info className="info-icon" />
                <div className="info-content">
                    <b>Pro Tip:</b> Files without <code>.server</code> or <code>.client</code> are treated as libraries. RPy will automatically wrap them and export all top-level variables.
                </div>
            </div>

            <h2>How to choose?</h2>
            <ul className="checklist">
                <li><CheckCircle2 size={16} /> Use <b>.server</b> for logic that handles players, data saving, or global game rules.</li>
                <li><CheckCircle2 size={16} /> Use <b>.client</b> for local UI interactions, camera effects, or player input.</li>
                <li><CheckCircle2 size={16} /> Use standard <b>.py</b> for shared utilities, classes, and reusable logic.</li>
            </ul>

            <div className="warning-box card">
                <AlertTriangle className="warning-icon" />
                <div className="warning-content">
                    <b>Common Pitfall:</b> Roblox will NOT run code inside a <code>ModuleScript</code> unless it is <code>require()</code>d by a Script or LocalScript.
                </div>
            </div>
        </article>
    );
}

function ClassesContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Syntax Mapping <ChevronRight size={14} /> Classes</div>
            <h1 className="article-title">Classes</h1>
            <p>RPy maps Python classes to Luau metatables using a professional "new" constructor pattern.</p>

            <div className="code-example grid-2">
                <div className="example-box">
                    <div className="box-label">Python</div>
                    <pre><code>{`class Player:
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        print(f"Hi, {self.name}")`}</code></pre>
                </div>
                <div className="example-box">
                    <div className="box-label">Luau</div>
                    <pre><code>{`local Player = {}
Player.__index = Player

function Player.new(name)
    local self = setmetatable({}, Player)
    self.name = name
    return self
end

function Player:greet()
    print("Hi, " .. tostring(self.name))
end`}</code></pre>
                </div>
            </div>
        </article>
    );
}
function CLIInit() {
    return (
        <article className="prose">
            <div className="breadcrumb">Getting Started <ChevronRight size={14} /> Project Initialization</div>
            <h1 className="article-title">Project Initialization</h1>
            <p>The <code>init</code> command scaffolds a new RPy project structure.</p>

            <div className="code-snippet glass">
                <div className="snippet-header">bash</div>
                <pre><code>rpy init my_game</code></pre>
            </div>

            <p>This creates:</p>
            <ul>
                <li><code>src/</code>: Python source files.</li>
                <li><code>out/</code>: Generated Luau output.</li>
                <li><code>rpy.json</code>: Project configuration.</li>
            </ul>
        </article>
    );
}
function CLIBuild() {
    return (
        <article className="prose">
            <div className="breadcrumb">CLI Reference <ChevronRight size={14} /> build</div>
            <h1 className="article-title">build</h1>
            <p className="article-lead">The <code>build</code> command is the core of RPy. It reads your Python source and generates production-ready Luau scripts.</p>

            <h2>Usage</h2>
            <div className="code-snippet glass">
                <div className="snippet-header">bash</div>
                <pre><code>rpy build [src_folder] [out_folder] [flags]</code></pre>
            </div>

            <h3>Step-by-Step Instructions</h3>
            <ol className="manual-steps">
                <li><b>Identify Source:</b> Point <code>src_folder</code> to your Python files (usually <code>src/</code>).</li>
                <li><b>Set Output:</b> Point <code>out_folder</code> to where you want the Luau files (usually <code>out/</code>).</li>
                <li><b>Execute:</b> Run the command. RPy will recursively scan and transpile all <code>.py</code> files.</li>
            </ol>

            <h3>Command Options (Flags)</h3>
            <div className="options-grid">
                <div className="option-card glass">
                    <code>--fast</code>
                    <p>Disables truthiness shims for performance-critical code.</p>
                </div>
                <div className="option-card glass">
                    <code>--fast</code>
                    <p>Disables truthiness shims for performance-critical code.</p>
                </div>
            </div>

            <div className="warning-box card">
                <AlertTriangle className="warning-icon" />
                <div className="warning-content">
                    <b>Warning:</b> Building over an existing folder will overwrite files with the same name. Always use a dedicated <code>out/</code> directory.
                </div>
            </div>
        </article>
    );
}

function CLIWatch() {
    return (
        <article className="prose">
            <div className="breadcrumb">CLI Reference <ChevronRight size={14} /> watch</div>
            <h1 className="article-title">watch</h1>
            <p className="article-lead">Watch mode creates a live development environment where your Luau output updates the moment you save a Python file.</p>

            <h2>The Developer Workflow</h2>
            <div className="visual-diagram glass">
                <div className="diagram-step">
                    <span className="step-num">PY</span>
                    <span className="step-text">Edit &amp; Save</span>
                </div>
                <div className="diagram-arrow">→</div>
                <div className="diagram-step">
                    <span className="step-num">RPY</span>
                    <span className="step-text">Auto-Rebuild</span>
                </div>
                <div className="diagram-arrow">→</div>
                <div className="diagram-step">
                    <span className="step-num">RPY</span>
                    <span className="step-text">Syncing Server</span>
                </div>
                <div className="diagram-arrow">→</div>
                <div className="diagram-step">
                    <span className="step-num">DEV</span>
                    <span className="step-text">Live in Studio</span>
                </div>
            </div>

            <div className="code-snippet glass">
                <div className="snippet-header">bash</div>
                <pre><code>rpy watch src out</code></pre>
            </div>

            <h3>Troubleshooting Watch Issues</h3>
            <ul>
                <li><b>Permissions:</b> On Windows, ensure you run the terminal as Administrator if RPy cannot access files.</li>
                <li><b>File Limits:</b> Very large projects may hit OS watch limits. Consider splitting your project into modules.</li>
            </ul>

            <div className="tip-box card">
                <Lightbulb className="tip-icon" />
                <div className="tip-content">
                    RPy watch will automatically re-transpile your code and notify the dev server when files are updated.
                </div>
            </div>
        </article>
    );
}

function VariablesContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Syntax Mapping <ChevronRight size={14} /> Variables</div>
            <h1 className="article-title">Variables</h1>
            <p className="article-lead">Variables are the building blocks of your scripts. RPy converts Python declarations into local Luau variables.</p>

            <h3>Basic Assignment</h3>
            <p>In Luau, local variables are generally preferred for performance. RPy automatically adds the <code>local</code> keyword.</p>
            <div className="code-example grid-2">
                <div className="example-box">
                    <pre><code>{`# Python
score = 100
name = "Guest"`}</code></pre>
                </div>
                <div className="example-box">
                    <pre><code>{`# Luau
local score = 100
local name = "Guest"`}</code></pre>
                </div>
            </div>

            <h3>The Truthiness Shim</h3>
            <p>One major difference between Python and Luau is <b>Truthiness</b>. In Python, <code>0</code> and <code>&quot;&quot;</code> are False. In Luau, only <code>nil</code> and <code>false</code> are False.</p>
            <div className="tip-box card">
                <Lightbulb className="tip-icon" />
                <div className="tip-content">
                    RPy automatically adds safety shims to ensure Python-style logic works: <code>if not x</code> becomes <code>if not (x ~= 0 and x ~= &quot;&quot; and x)</code>. Use <code>--fast</code> to disable this.
                </div>
            </div>

            <h3>Destructuring</h3>
            <div className="example-box">
                <pre><code>{`# Python
x, y = [1, 2]`}</code></pre>
            </div>
        </article>
    );
}

function LoopsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Syntax Mapping <ChevronRight size={14} /> Loops</div>
            <h1 className="article-title">Loops</h1>
            <p className="article-lead">Iterating over data is handled by Luau&apos;s extremely optimized <code>for</code> and <code>while</code> statements.</p>

            <h3>Numeric Loops</h3>
            <p>The <code>range()</code> function allows you to create numeric loops. RPy handles both start, stop, and step arguments.</p>
            <div className="code-example grid-2">
                <div className="example-box">
                    <pre><code>{`# Python
for i in range(1, 10, 2):
    print(i)`}</code></pre>
                </div>
                <div className="example-box">
                    <pre><code>{`# Luau
for i = 1, 9, 2 do
    print(i)
end`}</code></pre>
                </div>
            </div>

            <h3>Generic For (Tables)</h3>
            <p>Python&apos;s <code>for item in list</code> is mapped to <code>ipairs</code>, while <code>for k, v in dict.items()</code> maps to <code>pairs</code>.</p>
            <div className="example-box">
                <pre><code>{`# Python
for i, item in enumerate(my_list):
    print(i)`}</code></pre>
            </div>
        </article>
    );
}

function CLICheck() {
    return (
        <article className="prose">
            <div className="breadcrumb">CLI Reference <ChevronRight size={14} /> check</div>
            <h1 className="article-title">check</h1>
            <p className="article-lead">The <code>check</code> command verifies your code quality without spending time on file writing.</p>

            <h2>When to use</h2>
            <p>Use this during <b>Continuous Integration (CI)</b> or as a pre-commit hook to catch errors before they reach your Roblox game.</p>

            <div className="code-snippet glass">
                <div className="snippet-header">bash</div>
                <pre><code>rpy check ./src</code></pre>
            </div>

            <h3>Rules Validated</h3>
            <ul className="checklist">
                <li><CheckCircle2 size={16} /> All syntax is valid Python 3.10+.</li>
                <li><CheckCircle2 size={16} /> No unsupported Python features (like <code>eval</code>).</li>
                <li><CheckCircle2 size={16} /> All relative imports can be resolved.</li>
            </ul>
        </article>
    );
}

function FunctionsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Syntax Mapping <ChevronRight size={14} /> Functions</div>
            <h1 className="article-title">Functions</h1>
            <p className="article-lead">Functions are modular blocks of reusable code. RPy handles parameters, return values, and scope with precision.</p>

            <h3>Parameter Mapping</h3>
            <p>Python parameters with default values are converted into Luau &quot;or&quot; assignments at the start of the function body.</p>
            <div className="code-example grid-2">
                <div className="example-box">
                    <pre><code>{`# Python
def spawn_part(pos, color="Red"):
    pass`}</code></pre>
                </div>
                <div className="example-box">
                    <pre><code>{`# Luau
local function spawn_part(pos, color)
    color = color or "Red"
end`}</code></pre>
                </div>
            </div>

            <h3>Strict Typing</h3>
            <p>User Python&apos;s type hints to generate Luau Type definitions automatically with the <code>--typed</code> flag.</p>
            <div className="example-box">
                <pre><code>{`# Python
def add(a: number, b: number) -> number:
    return a + b`}</code></pre>
            </div>

            <div className="warning-box card">
                <AlertTriangle className="warning-icon" />
                <div className="warning-content">
                    <b>Pitfall:</b> Python allows keyword arguments like <code>foo(x=1)</code>. Luau does not support this. RPy converts these to positional arguments, so be careful with the order!
                </div>
            </div>
        </article>
    );
}

function ComprehensionsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Syntax Mapping <ChevronRight size={14} /> Comprehensions</div>
            <h1 className="article-title">Comprehensions</h1>
            <p>RPy provides first-class support for list and dictionary comprehensions, compiled to efficient Luau loops.</p>

            <h3>List Comprehensions</h3>
            <div className="example-box">
                <div className="box-label">Python</div>
                <pre><code>{`evens = [x * 2 for x in nums if x % 2 == 0]`}</code></pre>
            </div>

            <p style={{ marginTop: '1.5rem' }}>These are transpiled into an Immediately Invoked Function Expression (IIFE) in Luau for performance and scope isolation.</p>

            <h3>Dictionary Comprehensions</h3>
            <div className="example-box">
                <div className="box-label">Python</div>
                <pre><code>{`square_map = {x: x**2 for x in range(5)}`}</code></pre>
            </div>
        </article>
    );
}

function FolderStructureContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Roblox Syncing <ChevronRight size={14} /> Folder Structure</div>
            <h1 className="article-title">Folder Structure</h1>
            <p className="article-lead">Folder organization defines where your code &quot;lives&quot; in the Roblox Explorer.</p>

            <p>RPy organizes code by its <b>execution scope</b>:</p>

            <div className="visual-diagram glass">
                <div className="diagram-step">
                    <span className="step-num">S</span>
                    <span className="step-text"><b>src/server</b><br />(Server Scripts)</span>
                </div>
                <div className="diagram-arrow">|</div>
                <div className="diagram-step">
                    <span className="step-num">C</span>
                    <span className="step-text"><b>src/client</b><br />(Client Scripts)</span>
                </div>
                <div className="diagram-arrow">|</div>
                <div className="diagram-step">
                    <span className="step-num">Sh</span>
                    <span className="step-text"><b>src/shared</b><br />(Shared Modules)</span>
                </div>
            </div>

            <h2>Custom Folders</h2>
            <p>Folder settings are controlled by the <code>rpy.json</code> configuration file:</p>

            <ol className="manual-steps">
                <li>Open <code>rpy.json</code> in your project root.</li>
                <li>Find the <code>folders</code> section.</li>
                <li>Add a new entry mapping your source folder to its purpose.</li>
            </ol>

            <div className="tip-box card">
                <Lightbulb className="tip-icon" />
                <div className="tip-content">
                    The RPy Studio Plugin reads this structure to place scripts in their correct parent instances.
                </div>
            </div>
        </article>
    );
}
function TroubleshootingContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Support <ChevronRight size={14} /> Troubleshooting</div>
            <h1 className="article-title">Troubleshooting</h1>
            <p>Encountering issues? Here are the most common problems and how to fix them.</p>

            <div className="trouble-item">
                <h3>&quot;Command not found: rpy&quot;</h3>
                <p><b>Cause:</b> RPy was installed but its location isn't in your system PATH.</p>
                <p><b>Fix:</b> Ensure you installed it globally (<code>pip install rpy-transpiler</code>) or check your Python Scripts folder. On Windows, this is usually <code>%AppData%\Python\Python3xx\Scripts</code>.</p>
            </div>

            <div className="trouble-item">
                <h3>Studio is not syncing changes</h3>
                <p><b>Cause:</b> The RPy dev server may not be running, or the Studio plugin is disconnected.</p>
                <p><b>Fix:</b> Ensure RPy is running in <code>watch</code> mode and the RPy plugin in Studio is active and connected to <code>localhost</code>.</p>
            </div>

            <div className="warning-box card">
                <AlertTriangle className="warning-icon" />
                <div className="warning-content">
                    Always check the RPy terminal for errors if code changes aren't appearing in Studio.
                </div>
            </div>
        </article>
    );
}

function FAQContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Support <ChevronRight size={14} /> FAQ</div>
            <h1 className="article-title">Common Questions</h1>

            <div className="faq-item">
                <h4>Can I use standard Python libraries like <code>os</code> or <code>json</code>?</h4>
                <p>No. RPy is a transpiler for Luau, which runs in a sandboxed environment without file system or OS access. Use Roblox services like <code>HttpService</code> instead.</p>
            </div>

            <div className="faq-item">
                <h4>Does the index start at 0 or 1?</h4>
                <p>RPy uses <strong>0-based indexing</strong> for Python compatibility. It automatically converts this to Luau&apos;s 1-based indexing during transpilation.</p>
            </div>

            <div className="faq-item">
                <h4>What happens to my docstrings?</h4>
                <p>RPy V0.2.0 translates Python docstrings into Luau multiline comments (<code>--[[ ]]</code>) and places them before your function or class headers.</p>
            </div>
        </article>
    );
}

function PitfallsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Support <ChevronRight size={14} /> Common Pitfalls</div>
            <h1 className="article-title">Common Pitfalls</h1>
            <p>Avoid these frequent mistakes when working with RPy.</p>

            <ul className="pitfalls-list">
                <li>
                    <strong>Using <code>eval()</code>:</strong> This will raise an error. Dynamic code execution is not supported in the Luau subset.
                </li>
                <li>
                    <strong>Mutable Default Arguments:</strong> Just like in Python, <code>def foo(x=[])</code> persists across calls. Avoid this pattern.
                </li>
                <li>
                    <strong>Case Sensitivity:</strong> Note that Luau is case-sensitive. While Python is too, mismatching Roblox service names (e.g., <code>workspace</code> vs <code>Workspace</code>) can break builds.
                </li>
            </ul>

            <div className="info-box card">
                <Book className="info-icon" />
                <div className="info-content">
                    For deeper learning, refer to the <a href="https://luau-lang.org/syntax" target="_blank" rel="noreferrer">Luau Language Syntax</a> documentation.
                </div>
            </div>
        </article>
    );
}

function ImportsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Syntax Mapping <ChevronRight size={14} /> Modules &amp; Imports</div>
            <h1 className="article-title">Modules &amp; Imports</h1>
            <p>RPy maps Python&apos;s module system to Luau&apos;s <code>require()</code> system seamlessly.</p>

            <div className="code-example grid-2">
                <div className="example-box">
                    <div className="box-label">Python</div>
                    <pre><code>{`from utils import math
import shared.net as net

math.add(1, 2)`}</code></pre>
                </div>
                <div className="example-box">
                    <div className="box-label">Luau</div>
                    <pre><code>{`local math = require(script.Parent.utils).math
local net = require(game.ReplicatedStorage.shared.net)

math.add(1, 2)`}</code></pre>
                </div>
            </div>

            <div className="info-box card">
                <Info className="info-icon" />
                <div className="info-content">
                    RPy automatically resolves paths relative to the <code>src/</code> directory when generating <code>require</code> statements.
                </div>
            </div>
        </article>
    );
}

function DocstringsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Syntax Mapping <ChevronRight size={14} /> Docstrings</div>
            <h1 className="article-title">Docstrings</h1>
            <p>RPy preserves your documentation by converting Python docstrings into native Luau comments.</p>

            <div className="example-box">
                <div className="box-label">Python Input</div>
                <pre><code>{`def calculate_dist(p1, p2):
    """
    Computes Euclidean distance between two points.
    @param p1: Start point
    @param p2: End point
    """
    return (p1.x - p2.x)**2`}</code></pre>
            </div>

            <div className="example-box" style={{ marginTop: '1rem' }}>
                <div className="box-label">Luau Output</div>
                <pre><code>{`--[[
    Computes Euclidean distance between two points.
    @param p1: Start point
    @param p2: End point
]]
local function calculate_dist(p1, p2)
    return (p1.x - p2.x)^2
end`}</code></pre>
            </div>
        </article>
    );
}

function ChangelogContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Getting Started <ChevronRight size={14} /> Changelog</div>
            <h1 className="article-title">Version Changelog</h1>
            <p>Track the evolution of RPy and its recent feature additions.</p>

            <div className="changelog-item card">
                <h3>V0.2.0 (Feb 2026) <span className="badge success">Latest</span></h3>
                <ul>
                    <li>Added <strong>Script Type</strong> support (<code>.server.py</code>, <code>.client.py</code>).</li>
                    <li>Added <strong>Docstring</strong> translation to Luau multiline comments.</li>
                    <li>Added <code>init</code> CLI command for instant scaffolding.</li>
                    <li>Improved <strong>ModuleScript</strong> return table generation.</li>
                </ul>
            </div>

            <div className="changelog-item card" style={{ marginTop: '1.5rem', opacity: 0.6 }}>
                <h3>V0.1.0 (Jan 2026)</h3>
                <ul>
                    <li>Initial Alpha release with Core AST support.</li>
                    <li>Basic <code>build</code> and <code>watch</code> CLI modes.</li>
                </ul>
            </div>
        </article>
    );
}

function ResourcesContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Getting Started <ChevronRight size={14} /> Resources</div>
            <h1 className="article-title">External Resources</h1>
            <p>Deeper learning resources for mastering the RPy ecosystem.</p>

            <div className="resources-grid">
                <a href="https://docs.python.org/3/library/ast.html" target="_blank" className="resource-link glass">
                    <Book size={20} />
                    <div>
                        <h4>Python AST Docs</h4>
                        <p>Official reference for the Python syntax tree.</p>
                    </div>
                </a>
                <a href="https://luau-lang.org/getting-started" target="_blank" className="resource-link glass">
                    <Code2 size={20} />
                    <div>
                        <h4>Luau Language</h4>
                        <p>Syntax and performance guide for Luau.</p>
                    </div>
                </a>
                <a href="https://create.roblox.com/docs" target="_blank" className="resource-link glass">
                    <Box size={20} />
                    <div>
                        <h4>Roblox Documentation</h4>
                        <p>Official Roblox Engine API reference.</p>
                    </div>
                </a>
            </div>
        </article>
    );
}

function RobloxEventsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Syntax Mapping <ChevronRight size={14} /> Roblox Events</div>
            <h1 className="article-title">Roblox Events</h1>
            <p className="article-lead">RPy handles Roblox events through a &quot;Passthrough&quot; system. Simply use standard Python attribute access to connect functions to signals.</p>

            <h3>The Big Three Methods</h3>
            <p>Signals (Events) in Roblox support three primary methods. In Python, you write these with dot notation:</p>

            <table>
                <thead>
                    <tr>
                        <th>Python Usage</th>
                        <th>Luau Result</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><code>Signal.Connect(fn)</code></td>
                        <td><code>Signal:Connect(fn)</code></td>
                        <td>Registers a permanent listener.</td>
                    </tr>
                    <tr>
                        <td><code>Signal.Once(fn)</code></td>
                        <td><code>Signal:Once(fn)</code></td>
                        <td>Fires only once then disconnects.</td>
                    </tr>
                    <tr>
                        <td><code>Signal.Wait()</code></td>
                        <td><code>Signal:Wait()</code></td>
                        <td>Stops script until event fires.</td>
                    </tr>
                </tbody>
            </table>

            <h2>Handling Character Collision (Touched)</h2>
            <p>Character collision is a staple of Roblox development. Notice how the Python <code>Connect</code> method maps perfectly to Luau.</p>

            <div className="code-block-wrapper card">
                <div className="code-header">python</div>
                <pre><code>{`from roblox import script

part = script.Parent

def on_touched(hit):
    print(f"I was hit by {hit.Name}")

part.Touched.Connect(on_touched)`}</code></pre>
            </div>

            <div className="visual-diagram glass">
                <div className="diagram-step">
                    <span className="step-num">⚡</span>
                    <span className="step-text"><b>Event Fires</b><br />Collision detected</span>
                </div>
                <div className="diagram-arrow">➔</div>
                <div className="diagram-step">
                    <span className="step-num">🐍</span>
                    <span className="step-text"><b>RPy Callback</b><br />Python function runs</span>
                </div>
            </div>

            <div className="info-box card">
                <Info className="info-icon" />
                <div className="info-content">
                    <b>No Shims Required:</b> RPy translates these directly using native Luau signals, meaning 0% performance overhead for event connections.
                </div>
            </div>

            <h2>Popular Examples</h2>
            <div className="options-grid">
                <div className="option-card glass">
                    <code>Players.PlayerAdded</code>
                    <p>Trigger logic when someone joins your server.</p>
                    <pre>Players.PlayerAdded.Connect(on_join)</pre>
                </div>
                <div className="option-card glass">
                    <code>ProximityPrompt.Triggered</code>
                    <p>Perfect for interactive doors/chests.</p>
                    <pre>prompt.Triggered.Connect(on_triggered)</pre>
                </div>
            </div>

            <div className="warning-box card">
                <AlertTriangle className="warning-icon" />
                <div className="warning-content">
                    <b>Roblox Tip:</b> Remember that <code>Wait()</code> returns the event arguments! In Python, you can capture them like this: <code>name = Players.PlayerAdded.Wait()</code>.
                </div>
            </div>
        </article>
    );
}

function RobloxServicesContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Roblox API <ChevronRight size={14} /> Services</div>
            <h1 className="article-title">Services</h1>
            <p className="article-lead">RPy provides direct access to every major Roblox service. These are transpiled to their native global references in Luau.</p>

            <div className="options-grid">
                <div className="option-card glass">
                    <code>Players</code>
                    <p>Manage player loading, character spawning, and joining/leaving events.</p>
                </div>
                <div className="option-card glass">
                    <code>RunService</code>
                    <p>Detect execution context (Client vs Server) and connect frame signals.</p>
                </div>
                <div className="option-card glass">
                    <code>HttpService</code>
                    <p>Perform HTTP requests and handle JSON serialization.</p>
                </div>
                <div className="option-card glass">
                    <code>DataStoreService</code>
                    <p>Save and retrieve persistent player data from Roblox servers.</p>
                </div>
                <div className="option-card glass">
                    <code>UserInputService</code>
                    <p>Catch mouse clicks, key presses, and touch events on the client.</p>
                </div>
                <div className="option-card glass">
                    <code>TweenService</code>
                    <p>Interpolate instance properties for smooth UI/World animations.</p>
                </div>
            </div>

            <div className="info-box card">
                <Info className="info-icon" />
                <div className="info-content">
                    <b>Passthrough Power:</b> If a service isn&apos;t in the SDK stubs, simply use <code>game.GetService(&quot;Name&quot;)</code>—RPy handles it natively.
                </div>
            </div>
        </article>
    );
}

function RobloxDatatypesContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Roblox API <ChevronRight size={14} /> Datatypes</div>
            <h1 className="article-title">Roblox Datatypes</h1>
            <p className="article-lead">Roblox uses specialized datatypes for positioning and math. RPy preserves these types and their methods.</p>

            <div className="options-grid">
                <div className="option-card glass">
                    <code>Vector3</code>
                    <p>3D vectors for positions and directions.</p>
                    <pre>pos = Vector3(0, 5, 0)</pre>
                </div>
                <div className="option-card glass">
                    <code>CFrame</code>
                    <p>Coordinate frames (Position + Rotation).</p>
                    <pre>cf = CFrame.new(pos)</pre>
                </div>
                <div className="option-card glass">
                    <code>Color3</code>
                    <p>RGB color representation.</p>
                    <pre>col = Color3.fromRGB(255, 0, 0)</pre>
                </div>
                <div className="option-card glass">
                    <code>UDim2</code>
                    <p>2D UI scaling and offsets.</p>
                    <pre>size = UDim2.fromScale(1, 1)</pre>
                </div>
            </div>

            <div className="tip-box card">
                <Lightbulb className="tip-icon" />
                <div className="tip-content">
                    <b>Operator Logic:</b> RPy supports Python arithmetic on Vectors. <code>v1 * 2</code> works exactly as expected in the Roblox world.
                </div>
            </div>
        </article>
    );
}

function RobloxGlobalsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Roblox API <ChevronRight size={14} /> Globals</div>
            <h1 className="article-title">Roblox Globals</h1>
            <p className="article-lead">Access core Roblox engine variables and task management from Python.</p>

            <h3>The Big Three</h3>
            <table>
                <thead>
                    <tr>
                        <th>Global</th>
                        <th>Python Usage</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><code>game</code></td>
                        <td><code>from roblox import game</code></td>
                        <td>The root DataModel of the game.</td>
                    </tr>
                    <tr>
                        <td><code>workspace</code></td>
                        <td><code>from roblox import workspace</code></td>
                        <td>The physical 3D world shortcut.</td>
                    </tr>
                    <tr>
                        <td><code>script</code></td>
                        <td><code>from roblox import script</code></td>
                        <td>Reference to the current script instance.</td>
                    </tr>
                </tbody>
            </table>

            <h3>Task Library</h3>
            <p>RPy provides a first-class mapping for the Roblox <code>task</code> library, essential for non-blocking code.</p>

            <ul className="checklist">
                <li><CheckCircle2 size={16} /> <b>task.wait(t)</b>: Non-blocking yield.</li>
                <li><CheckCircle2 size={16} /> <b>task.spawn(fn)</b>: Run a function instantly on a new thread.</li>
                <li><CheckCircle2 size={16} /> <b>task.defer(fn)</b>: Run on the next resumption point.</li>
                <li><CheckCircle2 size={16} /> <b>task.delay(t, fn)</b>: Run after a set number of seconds.</li>
            </ul>
        </article>
    );
}

function BuiltinFunctionsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Built-ins & Methods <ChevronRight size={14} /> Global Functions</div>
            <h1 className="article-title">Built-in Functions</h1>
            <p className="article-lead">RPy maps standard Python built-ins to their corresponding Luau or RPy Runtime equivalents.</p>

            <h3>Supported Functions</h3>
            <table>
                <thead>
                    <tr>
                        <th>Python Function</th>
                        <th>Luau / Runtime Target</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><code>len(obj)</code></td>
                        <td><code>py_len(obj)</code></td>
                        <td>Works on lists, dicts, and strings.</td>
                    </tr>
                    <tr>
                        <td><code>print(*args)</code></td>
                        <td><code>print(...args)</code></td>
                        <td>Native Luau print.</td>
                    </tr>
                    <tr>
                        <td><code>int(v)</code>, <code>float(v)</code></td>
                        <td><code>py_int(v)</code>, <code>py_float(v)</code></td>
                        <td>Numeric conversion shims.</td>
                    </tr>
                    <tr>
                        <td><code>str(v)</code></td>
                        <td><code>py_str(v)</code></td>
                        <td>Converts any object to its string representation.</td>
                    </tr>
                    <tr>
                        <td><code>range(s, e, t)</code></td>
                        <td>Numeric <code>for</code> loop</td>
                        <td>Optimized at the compiler level.</td>
                    </tr>
                    <tr>
                        <td><code>enumerate(iter)</code></td>
                        <td><code>ipairs</code> / <code>py_enumerate</code></td>
                        <td>Returns index-value pairs.</td>
                    </tr>
                    <tr>
                        <td><code>abs(n)</code></td>
                        <td><code>math.abs(n)</code></td>
                        <td>Absolute value (Direct Mapping).</td>
                    </tr>
                    <tr>
                        <td><code>type(v)</code></td>
                        <td><code>typeof(v)</code></td>
                        <td>Roblox-aware type checking.</td>
                    </tr>
                </tbody>
            </table>

            <div className="info-box card">
                <Info className="info-icon" />
                <div className="info-content">
                    <b>Runtime Requirement:</b> Most built-ins (like <code>len</code> or <code>str</code>) rely on the RPy Runtime. This is automatically injected unless the <code>--no-runtime</code> flag is passed.
                </div>
            </div>
        </article>
    );
}

function ListMethodsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Built-ins & Methods <ChevronRight size={14} /> List Methods</div>
            <h1 className="article-title">List Methods</h1>
            <p className="article-lead">Standard Python list operations are available through the RPy Runtime shims.</p>

            <div className="options-grid">
                <div className="option-card glass">
                    <code>append(v)</code>
                    <p>Adds an element to the end of the list.</p>
                </div>
                <div className="option-card glass">
                    <code>pop()</code> / <code>pop(idx)</code>
                    <p>Removes and returns an element.</p>
                </div>
                <div className="option-card glass">
                    <code>insert(idx, v)</code>
                    <p>Inserts an element at a specific index.</p>
                </div>
                <div className="option-card glass">
                    <code>sort()</code>
                    <p>In-place list sorting using Luau&apos;s <code>table.sort</code>.</p>
                </div>
                <div className="option-card glass">
                    <code>reverse()</code>
                    <p>In-place list reversal.</p>
                </div>
                <div className="option-card glass">
                    <code>count(v)</code>
                    <p>Returns the number of times <code>v</code> appears.</p>
                </div>
            </div>

            <div className="warning-box card">
                <AlertTriangle className="warning-icon" />
                <div className="warning-content">
                    <b>Indexing Note:</b> RPy handles the 0-to-1 conversion automatically. <code>list.pop(0)</code> in Python removes the 1st element in Luau.
                </div>
            </div>
        </article>
    );
}

function DictMethodsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Built-ins & Methods <ChevronRight size={14} /> Dict Methods</div>
            <h1 className="article-title">Dict Methods</h1>
            <p className="article-lead">Python dictionary methods for managing key-value pairs in Luau tables.</p>

            <table>
                <thead>
                    <tr>
                        <th>Method</th>
                        <th>Behavior</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><code>keys()</code></td>
                        <td>Returns a list of all table keys.</td>
                    </tr>
                    <tr>
                        <td><code>values()</code></td>
                        <td>Returns a list of all table values.</td>
                    </tr>
                    <tr>
                        <td><code>items()</code></td>
                        <td>Returns pairs for <code>for k, v in dict.items()</code> loops.</td>
                    </tr>
                    <tr>
                        <td><code>get(key, default)</code></td>
                        <td>Safely retrieves a value with an optional fallback.</td>
                    </tr>
                    <tr>
                        <td><code>update(other)</code></td>
                        <td>Merges another dictionary into the current one.</td>
                    </tr>
                    <tr>
                        <td><code>setdefault(k, d)</code></td>
                        <td>Returns value of <code>k</code>; if not there, sets <code>k</code> to <code>d</code>.</td>
                    </tr>
                </tbody>
            </table>
        </article>
    );
}

function StringMethodsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Built-ins & Methods <ChevronRight size={14} /> String Methods</div>
            <h1 className="article-title">String Methods</h1>
            <p className="article-lead">Python-style string manipulation implemented via the Luau <code>string</code> library.</p>

            <ul className="checklist">
                <li><CheckCircle2 size={16} /> <b>upper()</b> / <b>lower()</b>: Case conversion.</li>
                <li><CheckCircle2 size={16} /> <b>split(delimiter)</b>: Returns a list of substrings.</li>
                <li><CheckCircle2 size={16} /> <b>join(iterable)</b>: Concatenates an iterable into a string.</li>
                <li><CheckCircle2 size={16} /> <b>strip()</b> / <b>lstrip()</b> / <b>rstrip()</b>: Trims whitespace.</li>
                <li><CheckCircle2 size={16} /> <b>startswith()</b> / <b>endswith()</b>: Boolean checks.</li>
                <li><CheckCircle2 size={16} /> <b>format()</b>: Python-style string interpolation.</li>
            </ul>

            <div className="tip-box card">
                <Lightbulb className="tip-icon" />
                <div className="tip-content">
                    <b>F-Strings:</b> Instead of <code>.format()</code>, we recommend using Python <b>f-strings</b> (e.g. <code>f&quot;hello {name}&quot;</code>). RPy compiles these into optimized Luau concatenation.
                </div>
            </div>
        </article>
    );
}

function PerformanceContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Advanced Concepts <ChevronRight size={14} /> Performance & Shims</div>
            <h1 className="article-title">Performance & Shims</h1>
            <p className="article-lead">RPy is designed to be &quot;Zero Cost&quot; where possible, but some Python behaviors require shims to remain accurate.</p>

            <h2>The Truthiness Shim</h2>
            <p>In Python, <code>0</code>, <code>&quot;&quot;</code>, and <code>[]</code> are for logic <b>False</b>. In Luau, only <code>nil</code> and <code>false</code> are false.</p>
            <p>By default, RPy wraps conditions in a <code>py_bool()</code> shim to ensure Python-accurate logic.</p>

            <div className="options-grid">
                <div className="option-card glass" style={{ borderLeft: '4px solid var(--accent-success)' }}>
                    <code>--fast</code>
                    <p>Disables the Truthiness Shim. Use this if you only ever check booleans or objects for nil. Improves execution speed.</p>
                </div>
                <div className="option-card glass" style={{ borderLeft: '4px solid var(--accent-primary)' }}>
                    <code>--typed</code>
                    <p>Enables Luau strict type emitting. Reduces runtime overhead and enables Luau VM optimizations.</p>
                </div>
            </div>

            <div className="warning-box card">
                <AlertTriangle className="warning-icon" />
                <div className="warning-content">
                    <b>Warning:</b> Disabling shims with <code>--fast</code> may break code that relies on <code>if 0:</code> or <code>if &quot;&quot;:</code> logic.
                </div>
            </div>

            <h2>Snippet Injection (Tree Shaking)</h2>
            <p>By default, RPy uses <b>Runtime Tree Shaking</b>. Instead of requiring a large external library, it injects only the Luau helper functions your script actually uses.</p>

            <div className="info-box card">
                <Info className="info-icon" />
                <div className="info-content">
                    <b>Self-Contained Scripts:</b> Injection is the default because it makes your generated Luau files completely independent and easier to move within Roblox Studio.
                </div>
            </div>

            <div className="options-grid">
                <div className="option-card glass">
                    <code>--shared-runtime</code>
                    <p>Force RPy to use a central <code>require()</code> statement for the runtime. Best for extremely large projects with hundreds of scripts.</p>
                </div>
                <div className="option-card glass">
                    <code>--no-runtime</code>
                    <p>Completely strips all runtime logic. Use this if you are writing "Pure Luau" within Python envelopes.</p>
                </div>
            </div>
        </article>
    );
}

function InternalsContent() {
    return (
        <article className="prose">
            <div className="breadcrumb">Advanced Concepts <ChevronRight size={14} /> CLI Internals</div>
            <h1 className="article-title">CLI Internals</h1>
            <p className="article-lead">Understanding how the RPy compiler processes your code.</p>

            <p>The RPy transpiler follows a standard compiler pipeline:</p>

            <div className="visual-diagram glass">
                <div className="diagram-step">
                    <span className="step-num">1</span>
                    <span className="step-text"><b>AST Parsing</b><br />Python source to Tree</span>
                </div>
                <div className="diagram-arrow">➔</div>
                <div className="diagram-step">
                    <span className="step-num">2</span>
                    <span className="step-text"><b>Transform</b><br />Apply Shims & Optimizations</span>
                </div>
                <div className="diagram-arrow">➔</div>
                <div className="diagram-step">
                    <span className="step-num">3</span>
                    <span className="step-text"><b>Emission</b><br />Generate final Luau source</span>
                </div>
            </div>

            <h3>Implementation Details</h3>
            <ul className="checklist">
                <li><CheckCircle2 size={16} /> <b>CodeEmitter</b>: Indentation-aware line buffering.</li>
                <li><CheckCircle2 size={16} /> <b>ScopeMap</b>: Tracks variable declaration depth for <code>local</code> keyword placement.</li>
                <li><CheckCircle2 size={16} /> <b>NodeRegistry</b>: Decoupled handlers for easy language feature additions.</li>
            </ul>
        </article>
    );
}


