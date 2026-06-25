import React, { useState, useEffect, useRef } from "react";
import {
  Terminal as TerminalIcon,
  Shield,
  FolderOpen,
  Play,
  CheckCircle2,
  AlertCircle,
  Cpu,
  Layers,
  Lock,
  Unlock,
  RefreshCw,
  Eye,
  FileText,
  HelpCircle,
  Check,
  ChevronRight,
  Sparkles,
  GitBranch,
  Wrench,
  Settings,
  Brain,
  ListTodo
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

interface WorkflowStep {
  step: number;
  action: string;
  assignedAgent: string;
  file?: string;
  status: "pending" | "running" | "success" | "failed";
  output?: string;
  error?: string;
  qualityScore?: number;
}

interface Workflow {
  id: string;
  goal: string;
  taskType: string;
  complexity: string;
  mode: string;
  status: "running" | "completed" | "failed";
  plan: WorkflowStep[];
  logs: string[];
  createdAt: string;
  completedAt?: string;
}

interface WorkspaceFile {
  name: string;
  path: string;
  size: number;
}

export default function App() {
  const [goal, setGoal] = useState("Build a Node.js web server that calculates Fibonacci numbers and responds on port 8080");
  const [mode, setMode] = useState("safe"); // safe, fast, strict
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);
  
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([]);
  const [fileLocks, setFileLocks] = useState<Record<string, string>>({});
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedFileContent, setSelectedFileContent] = useState<string>("");
  const [fileLoading, setFileLoading] = useState(false);

  const [terminalCommand, setTerminalCommand] = useState("");
  const [terminalOutput, setTerminalOutput] = useState<string>("AI Engineering OS Virtual Workspace Terminal\nType commands in the sandbox console below (e.g., node app.js)\n");
  const [terminalRunning, setTerminalRunning] = useState(false);
  
  const [activeTab, setActiveTab] = useState<"workspace" | "locks" | "architecture" | "autonomous">("workspace");
  const [currentView, setCurrentView] = useState<"ai_agent" | "workspace" | "weavers" | "semantic_memory" | "systems" | "terminal">("ai_agent");
  const [isLoading, setIsLoading] = useState(false);

  // Autonomous Engine States
  const [ledgerState, setLedgerState] = useState<any>({
    currentGoal: "",
    checklist: [],
    fileInventory: {},
    sessionLogs: [],
    systemMetrics: { totalFilesCreated: 0, totalDirectoriesCreated: 0, totalLinesWritten: 0, peakHeapMemoryMB: 0 }
  });
  const [systemMetrics, setSystemMetrics] = useState<any>({
    heapUsedMB: 0,
    heapTotalMB: 0,
    rssMB: 0,
    activeTasks: 0,
    queuedTasks: 0,
    cpuLoad: 0,
    freeMemGB: 0
  });
  
  const [autoGoal, setAutoGoal] = useState("Architect a high-performance modular micro-service codebase with over 1000 files and write a 30,000+ line core script");
  const [techStack, setTechStack] = useState("node_express");
  const [scaleOption, setScaleOption] = useState<"standard" | "massive" | "ultra_massive">("ultra_massive");
  const [giganticFilePath, setGiganticFilePath] = useState("src/core_engine.js");
  const [giganticLines, setGiganticLines] = useState(30100);
  
  const [gitRepoUrl, setGitRepoUrl] = useState("https://github.com/agentsoor-jpg/Agent.git");
  const [gitTargetFolder, setGitTargetFolder] = useState("external_agent");
  const [gitBranch, setGitBranch] = useState("main");
  const [gitCommitMsg, setGitCommitMsg] = useState("Sync complete autonomous modular layer");
  
  const [diagnosticFile, setDiagnosticFile] = useState("src/index.js");
  const [diagnosticResult, setDiagnosticResult] = useState<any>(null);

  const [symbolSearchQuery, setSymbolSearchQuery] = useState("");
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexingResult, setIndexingResult] = useState<any>(null);

  const logEndRef = useRef<HTMLDivElement>(null);

  // Poll for workflows, files, locks and autonomous metrics
  useEffect(() => {
    fetchWorkflows();
    fetchWorkspaceFiles();
    fetchLocks();
    fetchAutonomousMetrics();
    const interval = setInterval(() => {
      fetchWorkflows();
      fetchWorkspaceFiles();
      fetchLocks();
      fetchAutonomousMetrics();
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Sync selected workflow details
  useEffect(() => {
    if (activeWorkflowId) {
      const active = workflows.find((w) => w.id === activeWorkflowId);
      if (active) {
        setSelectedWorkflow(active);
      }
    }
  }, [workflows, activeWorkflowId]);

  // Scroll logs to bottom
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedWorkflow?.logs]);

  const fetchWorkflows = async () => {
    try {
      const res = await fetch("/api/meta/workflows");
      const data = await res.json();
      setWorkflows(data);
    } catch (e) {
      console.error("Error fetching workflows:", e);
    }
  };

  const fetchWorkspaceFiles = async () => {
    try {
      const res = await fetch("/api/meta/workspace/files");
      const data = await res.json();
      setWorkspaceFiles(data.files || []);
    } catch (e) {
      console.error("Error fetching workspace files:", e);
    }
  };

  const fetchLocks = async () => {
    try {
      const res = await fetch("/api/meta/locks");
      const data = await res.json();
      setFileLocks(data || {});
    } catch (e) {
      console.error("Error fetching locks:", e);
    }
  };

  const fetchAutonomousMetrics = async () => {
    try {
      const res = await fetch("/api/meta/autonomous/metrics");
      const data = await res.json();
      if (data.metrics) setSystemMetrics(data.metrics);
      if (data.ledger) setLedgerState(data.ledger);
    } catch (e) {
      console.error("Error fetching autonomous metrics:", e);
    }
  };

  const handleSetAutoGoal = async () => {
    try {
      const res = await fetch("/api/meta/autonomous/goal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: autoGoal }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setLedgerState(data.ledgerState);
        addTerminalLog(`\n>> Set Global Engineering Goal: "${autoGoal}"\n`);
      }
    } catch (e: any) {
      addTerminalLog(`\n[Goal Error] Failed to set goal: ${e.message}\n`);
    }
  };

  const handleWeaveArchitecture = async () => {
    try {
      const res = await fetch("/api/meta/autonomous/weave", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "full_architecture", techStack, size: scaleOption }),
      });
      const data = await res.json();
      addTerminalLog(`\n>> ${data.message || data.error}\n`);
      fetchWorkspaceFiles();
    } catch (e: any) {
      addTerminalLog(`\n[Weave Error] ${e.message}\n`);
    }
  };

  const handleWeaveGigantic = async () => {
    try {
      const res = await fetch("/api/meta/autonomous/weave", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "gigantic_file", filePath: giganticFilePath, targetLines: giganticLines }),
      });
      const data = await res.json();
      addTerminalLog(`\n>> ${data.message || data.error}\n`);
      fetchWorkspaceFiles();
    } catch (e: any) {
      addTerminalLog(`\n[Weave Error] ${e.message}\n`);
    }
  };

  const handleGitAction = async (actionType: string) => {
    try {
      let body: any = { gitAction: actionType };
      if (actionType === "clone") {
        body.url = gitRepoUrl;
        body.targetFolder = gitTargetFolder;
      } else if (actionType === "sync") {
        body.commitMessage = gitCommitMsg;
        body.remoteUrl = gitRepoUrl;
        body.branch = gitBranch;
      } else if (actionType === "raw") {
        body.args = ["status"];
      }

      const res = await fetch("/api/meta/autonomous/git", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      addTerminalLog(`\n$ git ${actionType} results:\n${data.output || JSON.stringify(data)}\n`);
      fetchWorkspaceFiles();
    } catch (e: any) {
      addTerminalLog(`\n[Git Linker Error] ${e.message}\n`);
    }
  };

  const handleRunDiagnostic = async () => {
    try {
      const res = await fetch("/api/meta/autonomous/diagnostic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filePath: diagnosticFile }),
      });
      const data = await res.json();
      setDiagnosticResult(data);
      if (data.isHealed) {
        addTerminalLog(`\n>> [Syntax Healed] Fixed compilation issues in: ${diagnosticFile}\nIssues: ${data.issues.join(", ")}\n`);
      } else {
        addTerminalLog(`\n>> [Diagnostics Completed] File: ${diagnosticFile}\nStatus: ${data.issues.join(", ")}\n`);
      }
      fetchWorkspaceFiles();
    } catch (e: any) {
      addTerminalLog(`\n[Diagnostic Error] ${e.message}\n`);
    }
  };

  const handleRunSemanticIndexing = async () => {
    setIsIndexing(true);
    try {
      const res = await fetch("/api/meta/autonomous/index", {
        method: "POST"
      });
      const data = await res.json();
      setIndexingResult(data);
      if (data.ledgerState) {
        setLedgerState(data.ledgerState);
      }
      addTerminalLog(`\n>> [Semantic Indexing Completed] Indexed ${data.filesIndexed} files, mapped ${data.totalSymbols} symbols.\n`);
    } catch (e: any) {
      addTerminalLog(`\n[Indexing Error] ${e.message}\n`);
    } finally {
      setIsIndexing(false);
    }
  };

  const handleExecute = async () => {
    if (!goal.trim()) return;
    setIsLoading(true);
    try {
      const res = await fetch("/api/meta/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, mode }),
      });
      const data = await res.json();
      if (data.workflow_id) {
        setActiveWorkflowId(data.workflow_id);
        fetchWorkflows();
        addTerminalLog(`\n>> Triggered MetaAgent execution flow for workflow: ${data.workflow_id}\nGoal: "${goal}"\n`);
      }
    } catch (e: any) {
      addTerminalLog(`\n[Execution Error] Failed to trigger workflow: ${e.message}\n`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReadFile = async (path: string) => {
    setSelectedFile(path);
    setFileLoading(true);
    try {
      const res = await fetch(`/api/meta/workspace/file?path=${encodeURIComponent(path)}`);
      const data = await res.json();
      if (data.content) {
        setSelectedFileContent(data.content);
      } else {
        setSelectedFileContent(`// Empty file or error reading contents.`);
      }
    } catch (e: any) {
      setSelectedFileContent(`// Error loading file: ${e.message}`);
    } finally {
      setFileLoading(false);
    }
  };

  const handleRunCommand = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!terminalCommand.trim() || terminalRunning) return;

    const cmd = terminalCommand;
    setTerminalCommand("");
    setTerminalRunning(true);
    addTerminalLog(`\n$ ${cmd}\n`);

    try {
      const res = await fetch("/api/meta/workspace/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd }),
      });
      const data = await res.json();
      addTerminalLog(data.output || "No output returned.");
      fetchWorkspaceFiles();
    } catch (e: any) {
      addTerminalLog(`Execution Error: ${e.message}`);
    } finally {
      setTerminalRunning(false);
    }
  };

  const addTerminalLog = (log: string) => {
    setTerminalOutput((prev) => prev + log + "\n");
  };

  const getAgentColor = (agent: string) => {
    switch (agent.toLowerCase()) {
      case "openhands":
        return "text-indigo-400 border-indigo-500/20 bg-indigo-500/10";
      case "aider":
        return "text-emerald-400 border-emerald-500/20 bg-emerald-500/10";
      case "bolt":
        return "text-amber-400 border-amber-500/20 bg-amber-500/10";
      case "replit":
        return "text-cyan-400 border-cyan-500/20 bg-cyan-500/10";
      default:
        return "text-slate-400 border-slate-500/20 bg-slate-500/10";
    }
  };

  return (
    <div className="min-h-screen bg-[#070a13] text-[#c9d1d9] font-sans antialiased flex flex-col md:flex-row selection:bg-indigo-500 selection:text-white" id="main_container">
      
      {/* SIDEBAR NAVIGATION */}
      <aside className="w-full md:w-80 bg-[#0c0f1a] border-b md:border-b-0 md:border-r border-slate-800/80 flex flex-col justify-between shrink-0" id="app_sidebar">
        <div>
          {/* Logo Brand Header */}
          <div className="p-6 border-b border-slate-800/60 bg-[#090b14]/50">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-indigo-500 to-indigo-700 rounded-lg shadow-lg shadow-indigo-500/20 flex items-center justify-center">
                <Cpu className="w-5 h-5 text-white animate-pulse" />
              </div>
              <div>
                <h1 className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
                  AI Engineering OS <span className="text-[10px] font-mono py-0.5 px-1.5 bg-indigo-950 text-indigo-300 border border-indigo-800/60 rounded-full">v6.0</span>
                </h1>
                <p className="text-[11px] text-slate-500">منظومة هندسة البرمجيات الذكية</p>
              </div>
            </div>
          </div>

          {/* Sidebar Menu Options */}
          <nav className="p-4 flex flex-col gap-1.5">
            <span className="px-3 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-600 block mb-1">
              الخيارات والتحكم / Control Deck
            </span>

            {/* 1. AI Orchestrator */}
            <button
              onClick={() => setCurrentView("ai_agent")}
              className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all text-left ${
                currentView === "ai_agent"
                  ? "bg-indigo-600/10 border-indigo-500/40 text-white"
                  : "bg-transparent border-transparent text-slate-400 hover:bg-slate-800/30 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Layers className={`w-4 h-4 shrink-0 ${currentView === "ai_agent" ? "text-indigo-400" : "text-slate-500"}`} />
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-semibold truncate">🤖 AI Orchestrator</span>
                  <span className="text-[10px] text-slate-500 truncate">المساعد والموجه الذكي</span>
                </div>
              </div>
              {workflows.some(w => w.status === "running") && (
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
              )}
            </button>

            {/* 2. File Explorer */}
            <button
              onClick={() => setCurrentView("workspace")}
              className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all text-left ${
                currentView === "workspace"
                  ? "bg-indigo-600/10 border-indigo-500/40 text-white"
                  : "bg-transparent border-transparent text-slate-400 hover:bg-slate-800/30 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <FolderOpen className={`w-4 h-4 shrink-0 ${currentView === "workspace" ? "text-indigo-400" : "text-slate-500"}`} />
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-semibold truncate">📁 Workspace Files</span>
                  <span className="text-[10px] text-slate-500 truncate">تصفح وتعديل ملفات المشروع</span>
                </div>
              </div>
              <span className="text-[10px] font-mono px-1.5 py-0.5 bg-slate-800 border border-slate-700/60 rounded text-slate-400">
                {workspaceFiles.length}
              </span>
            </button>

            {/* 3. Code Weavers */}
            <button
              onClick={() => setCurrentView("weavers")}
              className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all text-left ${
                currentView === "weavers"
                  ? "bg-indigo-600/10 border-indigo-500/40 text-white"
                  : "bg-transparent border-transparent text-slate-400 hover:bg-slate-800/30 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Wrench className={`w-4 h-4 shrink-0 ${currentView === "weavers" ? "text-indigo-400" : "text-slate-500"}`} />
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-semibold truncate">⚙️ Code Weavers</span>
                  <span className="text-[10px] text-slate-500 truncate">توليد الأنظمة والملفات الضخمة</span>
                </div>
              </div>
            </button>

            {/* 4. Semantic Memory */}
            <button
              onClick={() => setCurrentView("semantic_memory")}
              className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all text-left ${
                currentView === "semantic_memory"
                  ? "bg-indigo-600/10 border-indigo-500/40 text-white"
                  : "bg-transparent border-transparent text-slate-400 hover:bg-slate-800/30 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Brain className={`w-4 h-4 shrink-0 ${currentView === "semantic_memory" ? "text-indigo-400" : "text-slate-500"}`} />
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-semibold truncate">🧠 Semantic Memory</span>
                  <span className="text-[10px] text-slate-500 truncate">الذاكرة الدلالية والبحث الذكي</span>
                </div>
              </div>
              {ledgerState.symbolIndex?.lastIndexedAt && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              )}
            </button>

            {/* 5. Systems Linker & Settings */}
            <button
              onClick={() => setCurrentView("systems")}
              className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all text-left ${
                currentView === "systems"
                  ? "bg-indigo-600/10 border-indigo-500/40 text-white"
                  : "bg-transparent border-transparent text-slate-400 hover:bg-slate-800/30 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Settings className={`w-4 h-4 shrink-0 ${currentView === "systems" ? "text-indigo-400" : "text-slate-500"}`} />
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-semibold truncate">🔌 Sync & Diagnostics</span>
                  <span className="text-[10px] text-slate-500 truncate">ربط Git، الأمان وفحص الأخطاء</span>
                </div>
              </div>
            </button>

            {/* 6. Virtual Terminal */}
            <button
              onClick={() => setCurrentView("terminal")}
              className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all text-left ${
                currentView === "terminal"
                  ? "bg-indigo-600/10 border-indigo-500/40 text-white"
                  : "bg-transparent border-transparent text-slate-400 hover:bg-slate-800/30 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <TerminalIcon className={`w-4 h-4 shrink-0 ${currentView === "terminal" ? "text-cyan-400" : "text-slate-500"}`} />
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-semibold truncate">💻 Virtual Console</span>
                  <span className="text-[10px] text-slate-500 truncate">طرفية كونسول تفاعلية كاملة</span>
                </div>
              </div>
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
              </span>
            </button>
          </nav>
        </div>

        {/* Sidebar Footer with real metrics */}
        <div className="p-4 border-t border-slate-800/60 bg-[#090b14]/30 flex flex-col gap-3 font-mono text-[10px]">
          <div className="flex items-center justify-between text-slate-500">
            <span>HEAP MEM:</span>
            <span className="text-[#a5d6ff]">{systemMetrics.heapUsedMB}MB / {systemMetrics.heapTotalMB}MB</span>
          </div>
          <div className="flex items-center justify-between text-slate-500">
            <span>ACTIVE TASKS:</span>
            <span className="text-[#a5d6ff]">{systemMetrics.activeTasks}</span>
          </div>
          <div className="flex items-center justify-between text-slate-500">
            <span>LINES WRITTEN:</span>
            <span className="text-[#a5d6ff]">{(ledgerState.systemMetrics?.totalLinesWritten || 0).toLocaleString()}</span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-[9px] text-slate-600">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>OS SERVER SYNCED</span>
          </div>
        </div>
      </aside>

      {/* MAIN EXECUTING WORKSPACE */}
      <main className="flex-1 flex flex-col bg-[#070a13] overflow-hidden" id="dashboard_core">
        
        {/* Dynamic Headings Bar */}
        <div className="border-b border-slate-800 bg-[#0d111d]/40 px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white capitalize flex items-center gap-2">
              {currentView === "ai_agent" && "🤖 AI Orchestrator & Live Pipeline"}
              {currentView === "workspace" && "📁 Project Workspace & Code Explorer"}
              {currentView === "weavers" && "⚙️ Code Weaving Factory"}
              {currentView === "semantic_memory" && "🧠 Semantic Intel & Checklist Ledger"}
              {currentView === "systems" && "🔌 Sync, Claims & Diagnostics Panel"}
              {currentView === "terminal" && "💻 Interactive Sandbox Console"}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {currentView === "ai_agent" && "المساعد الذكي لتخطيط وبناء الأنظمة ومتابعة الإجراءات تلقائياً"}
              {currentView === "workspace" && "تصفح شجرة ملفات المشروع البرمجي مع مستعرض الأكواد التفاعلي"}
              {currentView === "weavers" && "محرك البناء التلقائي لبناء الأكواد الضخمة والمليونية دفعة واحدة"}
              {currentView === "semantic_memory" && "الذاكرة الدلالية الذكية وخارطة الرموز البرمجية وقائمة المهام المنجزة"}
              {currentView === "systems" && "إدارة الربط بمستودعات Git الخارجية، معالجة أخطاء الصياغة، وحجز ملفات التنسيق"}
              {currentView === "terminal" && "طرفية التحكم والكونسول التفاعلية لتجربة الأكواد البرمجية مباشرة بنظام الصندوق الرملي"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-slate-500 bg-[#121826] border border-slate-800 px-2 py-1 rounded">
              SERVER TIME: {new Date().toLocaleTimeString()}
            </span>
          </div>
        </div>

        {/* Dynamic Sub-Views Section */}
        <div className="flex-1 overflow-y-auto p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentView}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.15 }}
              className="h-full"
            >
              {/* 1. VIEW: AI AGENT ORCHESTRATOR */}
              {currentView === "ai_agent" && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-full items-start">
                  
                  {/* Left Column: Input triggers */}
                  <div className="lg:col-span-5 flex flex-col gap-6">
                    <div className="bg-[#0d111d] border border-slate-800/80 rounded-xl p-5 shadow-lg">
                      <h3 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2 uppercase tracking-wider font-mono border-b border-slate-800/40 pb-2">
                        <Layers className="w-3.5 h-3.5 text-indigo-400" /> Meta-Agent Trigger Control
                      </h3>
                      <p className="text-[11px] text-slate-500 mb-4 leading-relaxed">
                        قم بكتابة الهدف البرمجي الذي تريد تحقيقه، وسيتولى الوكيل الذكي إنشاء وبناء الكود بدقة.
                      </p>
                      
                      <div className="flex flex-col gap-4">
                        <textarea
                          value={goal}
                          onChange={(e) => setGoal(e.target.value)}
                          placeholder="مثال: Build an express web application displaying system status on port 8080..."
                          className="w-full bg-[#161b26] border border-slate-800 rounded-lg p-3 text-sm text-[#e6edf3] placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40 h-28 resize-none transition-all font-mono"
                        />
                        
                        <div className="flex flex-col gap-3">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-slate-400 font-mono">وضع التنفيذ / Mode:</span>
                            <div className="inline-flex rounded-lg bg-[#161b26] p-0.5 border border-slate-800">
                              {["safe", "fast", "strict"].map((m) => (
                                <button
                                  key={m}
                                  type="button"
                                  onClick={() => setMode(m)}
                                  className={`text-xs px-3 py-1 rounded-md font-mono transition-all capitalize ${
                                    mode === m
                                      ? "bg-indigo-600 text-white shadow-sm font-bold"
                                      : "text-slate-400 hover:text-slate-300"
                                  }`}
                                >
                                  {m}
                                </button>
                              ))}
                            </div>
                          </div>
                          
                          <button
                            onClick={handleExecute}
                            disabled={isLoading || !goal.trim()}
                            className="w-full mt-2 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold rounded-lg shadow-md flex items-center justify-center gap-2 transition-all text-sm"
                          >
                            {isLoading ? (
                              <RefreshCw className="w-4 h-4 animate-spin" />
                            ) : (
                              <Play className="w-4 h-4 fill-current" />
                            )}
                            بث الهدف إلى الوكيل الذكي / Execute Goal
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Active agent summary list */}
                    <div className="bg-[#0d111d] border border-slate-800/80 rounded-xl p-5">
                      <h4 className="text-xs font-bold text-slate-300 mb-3 uppercase tracking-wider font-mono">
                        ⚙️ Agent Collaboration Stack
                      </h4>
                      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                        <div className="p-2.5 rounded-lg border border-slate-800 bg-[#070a12] flex flex-col gap-1">
                          <span className="text-indigo-400 font-bold">OpenHands Agent</span>
                          <span className="text-slate-500 text-[10px]">Context Weaver, AST Fixer</span>
                        </div>
                        <div className="p-2.5 rounded-lg border border-slate-800 bg-[#070a12] flex flex-col gap-1">
                          <span className="text-emerald-400 font-bold">Aider Agent</span>
                          <span className="text-slate-500 text-[10px]">Code Weaver, Fast File Builder</span>
                        </div>
                        <div className="p-2.5 rounded-lg border border-slate-800 bg-[#070a12] flex flex-col gap-1">
                          <span className="text-amber-400 font-bold">Bolt Agent</span>
                          <span className="text-slate-500 text-[10px]">Claims & Resource Locking</span>
                        </div>
                        <div className="p-2.5 rounded-lg border border-slate-800 bg-[#070a12] flex flex-col gap-1">
                          <span className="text-cyan-400 font-bold">Replit Core</span>
                          <span className="text-slate-500 text-[10px]">Sandbox Environment Broker</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Execution results & live steps */}
                  <div className="lg:col-span-7 flex flex-col gap-6">
                    <div className="bg-[#0d111d] border border-slate-800/80 rounded-xl p-5 flex flex-col min-h-[450px]">
                      <div className="flex items-center justify-between border-b border-slate-800/50 pb-3 mb-4">
                        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono flex items-center gap-2">
                          <Cpu className="w-4 h-4 text-indigo-400 animate-pulse" /> Live Pipeline & Execution DAG
                        </h3>
                        {workflows.length > 0 && (
                          <select
                            onChange={(e) => setActiveWorkflowId(e.target.value)}
                            value={activeWorkflowId || ""}
                            className="bg-[#161b26] border border-slate-800 text-xs rounded-md py-1 px-2.5 focus:outline-none text-slate-300 font-mono"
                          >
                            <option value="" disabled>Select Workflow</option>
                            {workflows.map((wf) => (
                              <option key={wf.id} value={wf.id}>
                                {wf.id} ({wf.status})
                              </option>
                            ))}
                          </select>
                        )}
                      </div>

                      {selectedWorkflow ? (
                        <div className="flex flex-col gap-5 flex-1 justify-between">
                          <div>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-[#161b26] p-3 rounded-lg border border-slate-800/80 mb-4 text-xs font-mono">
                              <div>
                                <span className="text-slate-500 block text-[9px]">WORKFLOW ID</span>
                                <span className="text-indigo-400 font-semibold">{selectedWorkflow.id}</span>
                              </div>
                              <div>
                                <span className="text-slate-500 block text-[9px]">GOAL TYPE</span>
                                <span className="text-slate-300 capitalize">{selectedWorkflow.taskType.replace(/_/g, " ")}</span>
                              </div>
                              <div>
                                <span className="text-slate-500 block text-[9px]">COMPLEXITY</span>
                                <span className="text-slate-300 capitalize">{selectedWorkflow.complexity}</span>
                              </div>
                              <div>
                                <span className="text-slate-500 block text-[9px]">STATUS</span>
                                <span
                                  className={`font-bold capitalize ${
                                    selectedWorkflow.status === "completed"
                                      ? "text-emerald-400"
                                      : selectedWorkflow.status === "failed"
                                      ? "text-red-400"
                                      : "text-indigo-400 animate-pulse"
                                  }`}
                                >
                                  {selectedWorkflow.status}
                                </span>
                              </div>
                            </div>

                            <h4 className="text-[10px] font-bold text-slate-400 uppercase font-mono tracking-wider mb-3">Plan Step Progression</h4>
                            <div className="flex flex-col gap-2 max-h-[300px] overflow-y-auto scrollbar-thin pr-1">
                              {selectedWorkflow.plan.map((step) => (
                                <div
                                  key={step.step}
                                  className={`border rounded-lg p-3 transition-all flex items-start justify-between gap-4 ${
                                    step.status === "success"
                                      ? "border-emerald-920 bg-emerald-950/15"
                                      : step.status === "failed"
                                      ? "border-red-920 bg-red-950/15"
                                      : step.status === "running"
                                      ? "border-indigo-500/60 bg-indigo-500/5 animate-pulse"
                                      : "border-slate-800/80 bg-slate-900/10"
                                  }`}
                                >
                                  <div className="flex items-start gap-3 min-w-0 flex-1">
                                    <div className={`mt-0.5 rounded-full p-1 shrink-0 flex items-center justify-center ${
                                      step.status === "success"
                                        ? "bg-emerald-500/20 text-emerald-400"
                                        : step.status === "failed"
                                        ? "bg-red-500/20 text-red-400"
                                        : step.status === "running"
                                        ? "bg-indigo-500/20 text-indigo-400"
                                        : "bg-slate-800 text-slate-500"
                                    }`}>
                                      {step.status === "success" ? (
                                        <CheckCircle2 className="w-3.5 h-3.5" />
                                      ) : step.status === "failed" ? (
                                        <AlertCircle className="w-3.5 h-3.5" />
                                      ) : step.status === "running" ? (
                                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                      ) : (
                                        <span className="text-[10px] font-mono px-1 font-bold">{step.step}</span>
                                      )}
                                    </div>
                                    <div className="min-w-0 flex-1">
                                      <p className="text-xs font-semibold text-white tracking-tight flex items-center gap-1.5 flex-wrap">
                                        <span>{step.action.replace(/_/g, " ")}</span>
                                        {step.file && (
                                          <span className="text-[10px] font-mono font-normal text-slate-400 bg-slate-800/80 py-0.5 px-1.5 border border-slate-700/60 rounded">
                                            {step.file}
                                          </span>
                                        )}
                                      </p>
                                      {step.output && <p className="text-[11px] text-slate-400 mt-1 font-mono leading-relaxed truncate">{step.output}</p>}
                                      {step.error && <p className="text-[11px] text-red-400 mt-1 font-mono leading-relaxed">{step.error}</p>}
                                    </div>
                                  </div>

                                  <div className="flex flex-col items-end gap-1 shrink-0">
                                    <span className={`text-[9px] uppercase font-mono px-2 py-0.5 border rounded-full font-bold ${getAgentColor(step.assignedAgent)}`}>
                                      {step.assignedAgent}
                                    </span>
                                    {step.qualityScore !== undefined && (
                                      <span className="text-[9px] font-mono text-slate-500">
                                        QA: <span className="text-indigo-400 font-semibold">{(step.qualityScore * 100).toFixed(0)}%</span>
                                      </span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div className="mt-4 border-t border-slate-800/60 pt-4 flex-1 flex flex-col">
                            <h4 className="text-[10px] font-bold text-slate-400 uppercase font-mono tracking-wider mb-2">Meta Routing Logs</h4>
                            <div className="bg-[#060810] border border-slate-800/80 rounded-lg p-3 font-mono text-xs text-slate-400 overflow-y-auto max-h-[140px] flex-1">
                              {selectedWorkflow.logs.map((log, idx) => (
                                <div key={idx} className="mb-1 leading-relaxed">
                                  {log}
                                </div>
                              ))}
                              <div ref={logEndRef} />
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-center p-8 bg-[#131926]/20 border border-slate-800/60 rounded-xl" id="empty_workflow">
                          <Sparkles className="w-12 h-12 text-slate-700 mb-3 animate-pulse" />
                          <h3 className="text-xs font-bold text-slate-400 font-mono uppercase tracking-wider">System Operational & Ready</h3>
                          <p className="text-xs text-slate-500 max-w-sm mt-1.5 leading-relaxed">
                            أدخل هدفًا برمجيًا في لوحة التحكم على اليسار لبدء تنفيذ الأكواد التلقائي والمتابعة الفورية.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* 2. VIEW: PROJECT WORKSPACE & FILE EXPLORER */}
              {currentView === "workspace" && (
                <div className="bg-[#0d111d] border border-slate-800/80 rounded-xl p-5 flex flex-col min-h-[500px]">
                  <div className="flex items-center justify-between border-b border-slate-800/60 pb-3.5 mb-4">
                    <h3 className="text-xs font-bold text-slate-300 font-mono uppercase tracking-wider flex items-center gap-2">
                      <FolderOpen className="w-4 h-4 text-indigo-400" /> Virtual Workspace Files & Source View
                    </h3>
                    <button
                      onClick={fetchWorkspaceFiles}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded text-xs font-mono flex items-center gap-1.5 transition-colors border border-slate-700"
                      title="Refresh Files"
                    >
                      <RefreshCw className="w-3 h-3" /> Sync Files
                    </button>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-full min-h-[400px]">
                    {/* File List Column */}
                    <div className="lg:col-span-4 bg-[#060810] border border-slate-800 rounded-lg p-2.5 overflow-y-auto max-h-[500px] scrollbar-thin">
                      {workspaceFiles.length === 0 ? (
                        <p className="text-xs text-slate-500 p-4 font-mono italic text-center">No files generated yet. Use the AI Orchestrator or Weaver to create some files.</p>
                      ) : (
                        <div className="flex flex-col gap-1">
                          {workspaceFiles.map((f) => (
                            <button
                              key={f.path}
                              onClick={() => handleReadFile(f.path)}
                              className={`flex items-center gap-2.5 text-left w-full px-2.5 py-2.5 rounded text-xs font-mono border transition-all ${
                                selectedFile === f.path
                                  ? "bg-indigo-600/10 border-indigo-500/40 text-indigo-300"
                                  : "bg-transparent border-transparent text-slate-400 hover:bg-slate-800/40 hover:text-slate-300"
                              }`}
                            >
                              <FileText className="w-3.5 h-3.5 flex-shrink-0 text-slate-500" />
                              <span className="truncate flex-1">{f.path}</span>
                              <span className="text-[10px] text-slate-600 bg-slate-900 border border-slate-850 px-1 py-0.2 rounded shrink-0">
                                {(f.size / 1024).toFixed(1)}k
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Code Viewer Column */}
                    <div className="lg:col-span-8 bg-[#05070a] border border-slate-800/80 rounded-lg p-4 flex flex-col max-h-[500px]">
                      <div className="text-[10px] font-mono text-slate-500 border-b border-slate-800/60 pb-2 mb-3 flex items-center justify-between">
                        <span className="text-slate-400 font-bold">SOURCE VIEW: {selectedFile || "Select a File"}</span>
                        {selectedFile && <span className="text-emerald-500 bg-emerald-500/10 px-1.5 py-0.2 rounded text-[9px] font-bold">READ ONLY</span>}
                      </div>
                      
                      {fileLoading ? (
                        <div className="flex-1 flex items-center justify-center">
                          <div className="flex flex-col items-center gap-2">
                            <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
                            <span className="text-xs font-mono text-slate-500">Loading code buffer...</span>
                          </div>
                        </div>
                      ) : (
                        <pre className="flex-1 overflow-auto text-xs text-[#a5d6ff] font-mono whitespace-pre leading-relaxed scrollbar-thin bg-black/30 p-3 rounded border border-slate-900">
                          {selectedFileContent || "// Please select a generated file from the list to view its real contents."}
                        </pre>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* 3. VIEW: CODE WEAVERS FACTORY */}
              {currentView === "weavers" && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full items-start">
                  
                  {/* Architecture Weaver */}
                  <div className="bg-[#0d111d] border border-slate-800/80 rounded-xl p-5">
                    <div className="border-b border-slate-800/50 pb-3 mb-4">
                      <h3 className="text-sm font-bold text-slate-300 font-mono uppercase tracking-wider flex items-center gap-2">
                        📁 Autonomous Architecture Weaver
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        توليد فوري لكامل هيكلية وبنية المشروع البرمجي مع مئات المجلدات والملفات الجاهزة وبدون أخطاء.
                      </p>
                    </div>

                    <div className="flex flex-col gap-4 font-mono text-xs">
                      <div className="flex flex-col gap-1.5">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">بيئة البرمجة المستخدمة / Tech Stack</span>
                        <select
                          value={techStack}
                          onChange={(e) => setTechStack(e.target.value)}
                          className="bg-[#161b26] border border-slate-800 rounded p-2.5 focus:outline-none text-slate-300 text-xs w-full"
                        >
                          <option value="node_express">Node.js + Express REST API</option>
                          <option value="python_fastapi">Python + FastAPI Microservice</option>
                          <option value="general">Vanilla Javascript Structure</option>
                        </select>
                      </div>

                      <div className="flex flex-col gap-1.5">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">حجم النطاق / Scale Option</span>
                        <select
                          value={scaleOption}
                          onChange={(e) => setScaleOption(e.target.value as any)}
                          className="bg-[#161b26] border border-slate-800 rounded p-2.5 focus:outline-none text-slate-300 text-xs w-full"
                        >
                          <option value="standard">Standard (~50 modular files)</option>
                          <option value="massive">Massive (600+ folders & files)</option>
                          <option value="ultra_massive">Ultra-Massive (1000+ folders & files)</option>
                        </select>
                      </div>

                      <div className="bg-[#080b11] p-3 border border-slate-800/60 rounded text-[11px] text-slate-400 leading-relaxed mb-1">
                        📌 <span className="font-bold text-slate-300">طريقة العمل:</span> يقوم المنسق الذكي بإنشاء مجلدات فرعية للموديلات والمتحكمات والاختبارات دفعة واحدة، مع تفادي مشكلات الذاكرة وتثبيت الملفات بأمان.
                      </div>

                      <button
                        onClick={handleWeaveArchitecture}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-lg text-xs transition-colors flex items-center justify-center gap-1.5"
                      >
                        <RefreshCw className="w-3.5 h-3.5" /> توليد هيكلية المشروع البرمجي كاملة / Weave Base Structure
                      </button>
                    </div>
                  </div>

                  {/* Big File Weaver */}
                  <div className="bg-[#0d111d] border border-slate-800/80 rounded-xl p-5">
                    <div className="border-b border-slate-800/50 pb-3 mb-4">
                      <h3 className="text-sm font-bold text-slate-300 font-mono uppercase tracking-wider flex items-center gap-2">
                        📝 High-Fidelity Big File Weaver
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        توليد صياغة كود خالية من العيوب والأخطاء لملفات فردية ضخمة تصل لـ 30,000 سطر بشكل تلقائي.
                      </p>
                    </div>

                    <div className="flex flex-col gap-4 font-mono text-xs">
                      <div className="flex flex-col gap-1.5">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">مسار الملف المستهدف / Target File Path</span>
                        <input
                          type="text"
                          value={giganticFilePath}
                          onChange={(e) => setGiganticFilePath(e.target.value)}
                          className="bg-[#161b26] border border-slate-800 rounded p-2.5 text-xs text-slate-300 focus:outline-none w-full"
                        />
                      </div>

                      <div className="flex flex-col gap-1.5">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">العدد المستهدف للأسطر / Target Lines Limit</span>
                        <input
                          type="number"
                          value={giganticLines}
                          onChange={(e) => setGiganticLines(parseInt(e.target.value) || 10100)}
                          className="bg-[#161b26] border border-slate-800 rounded p-2.5 text-xs text-slate-300 focus:outline-none w-full"
                        />
                      </div>

                      <div className="bg-[#080b11] p-3 border border-slate-800/60 rounded text-[11px] text-slate-400 leading-relaxed mb-1">
                        ⚡ <span className="font-bold text-slate-300">ملاحظة أمان:</span> يقوم النظام بتقسيم التوليد على دفعات لمنع كسر مهلة الاتصال بالخادم، ويقوم بالتحقق الذاتي من تماسك بنية الكود.
                      </div>

                      <button
                        onClick={handleWeaveGigantic}
                        className="bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-3 rounded-lg text-xs transition-colors"
                      >
                        توليد الملف البرمجي العملاق / Weave High-Line File
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* 4. VIEW: SEMANTIC INTEL & MEMORY */}
              {currentView === "semantic_memory" && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-full items-start">
                  
                  {/* Symbol Indexer & Search */}
                  <div className="lg:col-span-7 bg-[#0d111d] border border-slate-800/80 rounded-xl p-5 flex flex-col min-h-[450px]">
                    <div className="border-b border-slate-800/50 pb-3 mb-4">
                      <h3 className="text-sm font-bold text-slate-300 font-mono uppercase tracking-wider flex items-center gap-2">
                        🧠 Semantic Memory Explorer
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        بناء الذاكرة الهيكلية الشاملة للتعرف التلقائي على الفئات (Classes) والوظائف (Functions) ومنع الهلوسة.
                      </p>
                    </div>

                    <div className="flex flex-col gap-4 flex-1">
                      <div className="flex gap-2">
                        <button
                          onClick={handleRunSemanticIndexing}
                          disabled={isIndexing}
                          className={`font-mono font-bold px-4 py-2.5 rounded text-xs transition-colors flex-1 text-center ${
                            isIndexing
                              ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-transparent"
                              : "bg-indigo-600 hover:bg-indigo-700 text-white border border-indigo-500"
                          }`}
                        >
                          {isIndexing ? "Analyzing Code Base..." : "توليد ومزامنة الذاكرة الذكية / Build Semantic Memory"}
                        </button>
                      </div>

                      {ledgerState.symbolIndex?.lastIndexedAt ? (
                        <div className="flex flex-col gap-3 flex-1">
                          <div className="flex justify-between items-center text-[10px] text-slate-500 font-mono">
                            <span>آخر فحص: {new Date(ledgerState.symbolIndex.lastIndexedAt).toLocaleTimeString()}</span>
                            <span className="text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">MEMORY LOADED</span>
                          </div>

                          {/* Search Input */}
                          <div className="relative">
                            <input
                              type="text"
                              placeholder="البحث عن كلاس أو دالة برمجية... (e.g., service, controller)"
                              value={symbolSearchQuery}
                              onChange={(e) => setSymbolSearchQuery(e.target.value)}
                              className="w-full bg-[#161b26] border border-slate-850 rounded px-3 py-2 text-xs text-slate-300 focus:outline-none placeholder-slate-600 font-mono"
                            />
                          </div>

                          {/* Search Results */}
                          <div className="flex-1 max-h-[300px] overflow-y-auto bg-[#05070a] rounded border border-slate-850/80 p-2.5 flex flex-col gap-1.5 scrollbar-thin">
                            {(() => {
                              const query = symbolSearchQuery.toLowerCase().trim();
                              const allSymbols: any[] = [];
                              if (ledgerState.symbolIndex?.symbols) {
                                Object.values(ledgerState.symbolIndex.symbols).forEach((symList: any) => {
                                  symList.forEach((s: any) => allSymbols.push(s));
                                });
                              }

                              const filtered = query
                                ? allSymbols.filter(
                                    (s) =>
                                      s.name.toLowerCase().includes(query) ||
                                      s.filePath.toLowerCase().includes(query)
                                  )
                                : allSymbols.slice(0, 40);

                              if (filtered.length === 0) {
                                return (
                                  <div className="text-[11px] text-slate-600 py-8 text-center font-mono">
                                    لا توجد رموز مطابقة في الذاكرة النشطة حالياً.
                                  </div>
                                );
                              }

                              return filtered.map((sym, index) => (
                                <div
                                  key={index}
                                  onClick={() => {
                                    setCurrentView("workspace");
                                    handleReadFile(sym.filePath);
                                  }}
                                  className="flex items-center justify-between p-2.5 rounded hover:bg-indigo-950/20 border border-transparent hover:border-indigo-900/30 cursor-pointer transition-all font-mono"
                                >
                                  <div className="flex flex-col gap-0.5 min-w-0 pr-2">
                                    <span className="font-bold text-[#a5d6ff] text-[11px] truncate">
                                      {sym.name}
                                    </span>
                                    <span className="text-[9px] text-slate-500 truncate">
                                      {sym.filePath}
                                    </span>
                                  </div>
                                  <span className={`text-[8px] px-2 py-0.5 rounded font-bold uppercase shrink-0 ${
                                    sym.type === "class"
                                      ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                                      : sym.type === "function"
                                      ? "bg-sky-500/10 text-sky-400 border border-sky-500/20"
                                      : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                  }`}>
                                    {sym.type}
                                  </span>
                                </div>
                              ));
                            })()}
                          </div>
                        </div>
                      ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-800 rounded-lg">
                          <Brain className="w-10 h-10 text-slate-700 mb-2 animate-bounce" />
                          <span className="text-xs font-mono text-slate-500">مخزن الرموز فارغ. اضغط على الزر أعلاه للمزامنة.</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Checklist & Goal State Ledger */}
                  <div className="lg:col-span-5 bg-[#0d111d] border border-slate-800/80 rounded-xl p-5 flex flex-col">
                    <div className="border-b border-slate-800/50 pb-3 mb-4">
                      <h3 className="text-sm font-bold text-slate-300 font-mono uppercase tracking-wider flex items-center gap-2">
                        <ListTodo className="w-4 h-4 text-indigo-400" /> Goal Checklist Ledger
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        متابعة قائمة الأهداف الإرشادية البرمجية المعرفة للنظام حالياً.
                      </p>
                    </div>

                    <div className="flex flex-col gap-4">
                      <div className="flex flex-col gap-2 bg-[#161b26] p-3 rounded-lg border border-slate-800">
                        <span className="text-[10px] text-slate-500 font-mono uppercase">تعديل الهدف الحالي / Set active goal</span>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={autoGoal}
                            onChange={(e) => setAutoGoal(e.target.value)}
                            className="flex-1 bg-[#0c0f1a] border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-300 font-mono focus:outline-none focus:border-indigo-500"
                          />
                          <button
                            onClick={handleSetAutoGoal}
                            className="bg-indigo-600 hover:bg-indigo-700 text-white font-mono px-3 py-1 text-xs rounded font-bold uppercase whitespace-nowrap"
                          >
                            Set
                          </button>
                        </div>
                      </div>

                      {ledgerState.checklist && ledgerState.checklist.length > 0 ? (
                        <div className="flex flex-col gap-2 bg-[#060810] p-3 rounded border border-slate-850 font-mono text-xs">
                          {ledgerState.checklist.map((item: any, i: number) => (
                            <div key={i} className="flex items-start gap-2.5 text-slate-400 p-1.5 rounded hover:bg-slate-900/40">
                              <span className={`text-sm shrink-0 leading-none ${item.completed ? "text-emerald-400 font-bold" : "text-amber-500"}`}>
                                {item.completed ? "✓" : "○"}
                              </span>
                              <span className={item.completed ? "line-through text-slate-600" : "text-slate-300"}>{item.task}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="p-6 text-center text-slate-500 text-xs font-mono border border-dashed border-slate-800 rounded-lg">
                          No active checklist. Set a goal above or run AI Orchestration.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* 5. VIEW: SYSTEMS, CLAIMS & DIAGNOSTICS */}
              {currentView === "systems" && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-full items-start">
                  
                  {/* Git Linker System */}
                  <div className="lg:col-span-7 bg-[#0d111d] border border-slate-800/80 rounded-xl p-5 flex flex-col">
                    <div className="border-b border-slate-800/50 pb-3 mb-4">
                      <h3 className="text-sm font-bold text-slate-300 font-mono uppercase tracking-wider flex items-center gap-2">
                        <GitBranch className="w-4 h-4 text-emerald-400" /> Git Upstream Repository Linker
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        ربط المشروع وتصدير أو جلب الملفات من وإلى مستودعات Git الخارجية.
                      </p>
                    </div>

                    <div className="flex flex-col gap-4 font-mono text-xs">
                      <div className="flex flex-col gap-1.5">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">رابط المستودع / Repos URL</span>
                        <input
                          type="text"
                          value={gitRepoUrl}
                          onChange={(e) => setGitRepoUrl(e.target.value)}
                          className="bg-[#161b26] border border-slate-800 rounded px-2.5 py-2 text-xs text-slate-300 focus:outline-none"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="flex flex-col gap-1.5">
                          <span className="text-[10px] text-slate-500 uppercase font-bold">مجلد الحفظ / Target Folder</span>
                          <input
                            type="text"
                            value={gitTargetFolder}
                            onChange={(e) => setGitTargetFolder(e.target.value)}
                            className="bg-[#161b26] border border-slate-800 rounded px-2.5 py-2 text-xs text-slate-300 focus:outline-none"
                          />
                        </div>
                        <div className="flex flex-col gap-1.5">
                          <span className="text-[10px] text-slate-500 uppercase font-bold">الفرع / Branch</span>
                          <input
                            type="text"
                            value={gitBranch}
                            onChange={(e) => setGitBranch(e.target.value)}
                            className="bg-[#161b26] border border-slate-800 rounded px-2.5 py-2 text-xs text-slate-300 focus:outline-none"
                          />
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <button
                          onClick={() => handleGitAction("clone")}
                          className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-3 py-2.5 rounded text-xs flex-1 transition-colors"
                        >
                          جلب المستودع / Clone Remote Repo
                        </button>
                        <button
                          onClick={() => handleGitAction("raw")}
                          className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-2.5 rounded text-xs transition-colors border border-slate-700"
                        >
                          حالة المستودع / Check status
                        </button>
                      </div>

                      <div className="border-t border-slate-800/80 pt-4 flex flex-col gap-2">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">رسالة المزامنة والرفع / Git Commit Msg</span>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={gitCommitMsg}
                            onChange={(e) => setGitCommitMsg(e.target.value)}
                            className="bg-[#161b26] border border-slate-800 rounded px-2.5 py-2 text-xs text-slate-300 focus:outline-none flex-1"
                          />
                          <button
                            onClick={() => handleGitAction("sync")}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded text-xs font-bold"
                          >
                            مزامنة / Sync Upstream
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* AST healer & claim locks */}
                  <div className="lg:col-span-5 flex flex-col gap-6">
                    {/* Healer */}
                    <div className="bg-[#0d111d] border border-slate-800/80 rounded-xl p-5">
                      <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono mb-3 flex items-center gap-1.5">
                        🩺 AST Syntax Diagnostic Healer
                      </h4>
                      <p className="text-[11px] text-slate-500 mb-4 leading-relaxed">
                        قم بفحص وتصحيح صياغة أي ملف برمجي لمعالجة الأقواس الناقصة والعيوب الهيكلية تلقائياً.
                      </p>

                      <div className="flex flex-col gap-3 font-mono">
                        <input
                          type="text"
                          value={diagnosticFile}
                          onChange={(e) => setDiagnosticFile(e.target.value)}
                          className="w-full bg-[#161b26] border border-slate-800 rounded px-2.5 py-2 text-xs text-[#e6edf3] focus:outline-none"
                        />
                        <button
                          onClick={handleRunDiagnostic}
                          className="bg-amber-600 hover:bg-amber-700 text-white font-bold py-2 rounded text-xs transition-colors"
                        >
                          بدء فحص وتصحيح الملف / Heal Syntax
                        </button>

                        {diagnosticResult && (
                          <div className="bg-[#05070a] p-2.5 rounded border border-slate-850 text-[10px] text-slate-400">
                            <span className="text-slate-300 block font-bold mb-1">نتيجة الفحص الأخير:</span>
                            <div>حالة التصحيح: <span className={diagnosticResult.isHealed ? "text-emerald-400 font-bold" : "text-slate-300"}>{diagnosticResult.isHealed ? "تم الإصلاح والتصحيح بنجاح" : "الملف سليم ولا يحتاج لتصحيح"}</span></div>
                            <div className="mt-1 font-mono">المشاكل: {diagnosticResult.issues.join(", ")}</div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Claims Locking */}
                    <div className="bg-[#0d111d] border border-slate-800/80 rounded-xl p-5">
                      <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono mb-2 flex items-center gap-1.5">
                        <Lock className="w-3.5 h-3.5 text-indigo-400" /> Coordination Locks
                      </h4>
                      <p className="text-[11px] text-slate-500 mb-3">
                        حجز ملفات التنسيق النشطة لمنع تضارب الكتابة بين كبسولات العملاء الذكية.
                      </p>
                      <div className="bg-[#080b11] border border-slate-850 rounded-lg p-3 font-mono text-xs">
                        {Object.keys(fileLocks).length === 0 ? (
                          <div className="py-2 text-slate-500 flex items-center gap-2 text-[11px]">
                            <Unlock className="w-3.5 h-3.5 text-emerald-400" />
                            <span>جميع الموارد غير محجوزة ومتاحة بالكامل.</span>
                          </div>
                        ) : (
                          Object.entries(fileLocks).map(([file, agent]) => (
                            <div key={file} className="flex justify-between py-1.5 border-b border-slate-900/60 items-center">
                              <span className="text-indigo-300 truncate pr-2 max-w-[140px]">{file}</span>
                              <span className={`text-[9px] font-bold px-2 py-0.5 border rounded-full shrink-0 ${getAgentColor(agent as string)}`}>
                                {(agent as string).toUpperCase()}
                              </span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* 6. VIEW: VIRTUAL INTERACTIVE TERMINAL */}
              {currentView === "terminal" && (
                <div className="bg-[#0d111d] border border-slate-800/80 rounded-xl p-5 flex flex-col h-full min-h-[500px]">
                  <div className="flex items-center justify-between border-b border-slate-800/60 pb-3 mb-4">
                    <h3 className="text-xs font-bold text-slate-300 font-mono uppercase tracking-wider flex items-center gap-2">
                      <TerminalIcon className="w-4 h-4 text-cyan-400" /> Interactive Sandbox Terminal Console
                    </h3>
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                      <span className="text-[10px] font-mono text-slate-500">SANDBOX SHELL ENABLED</span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-500 mb-4 font-mono">
                    قم بتجربة الأكواد البرمجية مباشرة وتشغيل ملفات Node أو Python واختبارات pytest داخل الحاوية المعزولة بأمان.
                  </p>

                  <div className="flex-1 bg-[#05070e] border border-slate-850 rounded-lg p-4 font-mono text-xs text-[#a5d6ff] overflow-y-auto mb-4 min-h-[300px] scrollbar-thin">
                    <pre className="whitespace-pre-wrap leading-relaxed">{terminalOutput}</pre>
                  </div>

                  <form onSubmit={handleRunCommand} className="flex gap-2">
                    <span className="bg-[#161b26] border border-slate-800 rounded-lg px-3 py-2.5 text-xs text-slate-500 font-mono flex items-center justify-center">
                      $
                    </span>
                    <input
                      type="text"
                      value={terminalCommand}
                      onChange={(e) => setTerminalCommand(e.target.value)}
                      placeholder="e.g., node src/index.js or npm run lint or python app/main.py ..."
                      className="flex-1 bg-[#161b26] border border-slate-800 rounded-lg px-3.5 py-2.5 text-xs text-[#e6edf3] font-mono placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
                    />
                    <button
                      type="submit"
                      disabled={terminalRunning || !terminalCommand.trim()}
                      className="px-6 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-40 text-white font-bold text-xs rounded-lg font-mono flex items-center justify-center gap-1.5 transition-colors shrink-0"
                    >
                      {terminalRunning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : "إرسال / Run"}
                    </button>
                  </form>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
