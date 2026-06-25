import fs from "fs";
import path from "path";
import http from "http";
import { execSync } from "child_process";
import {
  MemoryLedger,
  TaskDistributor,
  CodeWeaver,
  GitLinker,
  SyntaxFixer,
  SemanticIndexer
} from "./autonomous_engine";

const WORKSPACE_DIR = path.resolve(process.cwd(), "workspace_run");
const TEST_API_BASE = "http://localhost:3000";

// --- HELPERS ---
function postJson(url: string, body: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const postData = JSON.stringify(body);
    
    const req = http.request(
      {
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || 80,
        path: parsedUrl.pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(postData),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => { data += chunk; });
        res.on("end", () => {
          try { resolve(JSON.parse(data)); } catch (e) { resolve(data); }
        });
      }
    );
    req.on("error", reject);
    req.write(postData);
    req.end();
  });
}

function getJson(url: string): Promise<any> {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = "";
      res.on("data", (chunk) => { data += chunk; });
      res.on("end", () => {
        try { resolve(JSON.parse(data)); } catch (e) { resolve(data); }
      });
    }).on("error", reject);
  });
}

// Store results
const testResults: { name: string; category: string; status: "PASS" | "FAIL"; details: string }[] = [];

function recordTest(category: string, name: string, status: "PASS" | "FAIL", details: string) {
  testResults.push({ name, category, status, details });
  const icon = status === "PASS" ? "🟢" : "🔴";
  console.log(`${icon} [${category}] ${name}: ${status} - ${details}`);
}

async function runAllTests() {
  console.log("\n======================================================================");
  console.log("            MASTER SYSTEM TEST SUITE: DEEP COGNITIVE & CHAOS AUDIT");
  console.log("======================================================================\n");

  console.log("----------------------------------------------------------------------");
  console.log("LAYER 1: SANITY & ARCHITECTURAL CHECKS");
  console.log("----------------------------------------------------------------------");
  
  // Test if directories exist
  if (fs.existsSync(WORKSPACE_DIR)) {
    recordTest("Sanity", "Workspace Directory", "PASS", `Verified at: ${WORKSPACE_DIR}`);
  } else {
    recordTest("Sanity", "Workspace Directory", "FAIL", "Workspace directory does not exist.");
  }

  const packageJsonPath = path.resolve(process.cwd(), "package.json");
  if (fs.existsSync(packageJsonPath)) {
    recordTest("Sanity", "Package JSON Manifest", "PASS", "package.json is present in the workspace root.");
  } else {
    recordTest("Sanity", "Package JSON Manifest", "FAIL", "Missing package.json!");
  }

  console.log("\n----------------------------------------------------------------------");
  console.log("LAYER 2: UNIT TESTS - CORE ENGINES INDEPENDENT BEHAVIOR");
  console.log("----------------------------------------------------------------------");

  // 1. MemoryLedger Unit Tests
  try {
    const memory = new MemoryLedger(WORKSPACE_DIR);
    const initialGoal = "Test System Integration Goal";
    memory.setGoal(initialGoal);
    const state = memory.getState();

    if (state.currentGoal === initialGoal && state.checklist.length > 0) {
      recordTest("MemoryLedger", "Goal Initialisation & Checklist Creation", "PASS", "ledger sets goal and initializes checklist DAG.");
    } else {
      recordTest("MemoryLedger", "Goal Initialisation & Checklist Creation", "FAIL", `Goal or checklist mismatch: ${JSON.stringify(state)}`);
    }

    // Register a file
    memory.registerFile("test_sample_file.txt", "txt", 100, 5);
    const stateAfterReg = memory.getState();
    if (stateAfterReg.fileInventory["test_sample_file.txt"]?.size === 100) {
      recordTest("MemoryLedger", "File Inventory Registry", "PASS", "Correctly logged created file metadata.");
    } else {
      recordTest("MemoryLedger", "File Inventory Registry", "FAIL", "File registry missing or incorrect.");
    }

    // Clean up sample file register
    delete stateAfterReg.fileInventory["test_sample_file.txt"];
    memory.save();
  } catch (e: any) {
    recordTest("MemoryLedger", "Exception Raised", "FAIL", e.message);
  }

  // 2. TaskDistributor Unit Tests (Concurrency, Memory Safety, Callbacks)
  try {
    const memoryForDist = new MemoryLedger(WORKSPACE_DIR);
    const distributor = new TaskDistributor(memoryForDist);
    
    let callbackSuccess = false;
    distributor.addTask({
      id: "task_test_1",
      name: "Concurrency Test 1",
      execute: async () => {
        return "result_success";
      },
      onSuccess: (res) => {
        if (res === "result_success") {
          callbackSuccess = true;
        }
      }
    });

    // Wait a brief period to allow the event loop to run the async task queue
    await new Promise((resolve) => setTimeout(resolve, 100));

    if (callbackSuccess) {
      recordTest("TaskDistributor", "Asynchronous Queue & Success Callbacks", "PASS", "Async tasks execute smoothly with decoupled callbacks.");
    } else {
      recordTest("TaskDistributor", "Asynchronous Queue & Success Callbacks", "FAIL", "Task failed to run or callback was never invoked.");
    }

    const metrics = distributor.getMetrics();
    if (metrics.heapUsedMB > 0 && metrics.rssMB > 0) {
      recordTest("TaskDistributor", "Telemetry Metrics Gathering", "PASS", `Fetched RSS: ${metrics.rssMB}MB, heap: ${metrics.heapUsedMB}MB`);
    } else {
      recordTest("TaskDistributor", "Telemetry Metrics Gathering", "FAIL", "Invalid metrics returned.");
    }
  } catch (e: any) {
    recordTest("TaskDistributor", "Exception Raised", "FAIL", e.message);
  }

  // 3. SyntaxFixer / Diagnostic AST Healing
  try {
    const memory = new MemoryLedger(WORKSPACE_DIR);
    const fixer = new SyntaxFixer(WORKSPACE_DIR, memory);
    
    // Create a broken JS file containing an unclosed curly brace and parenthesis
    const brokenJsPath = path.resolve(WORKSPACE_DIR, "broken_test_file.js");
    fs.writeFileSync(brokenJsPath, "function calculate(a, b) {\n  if (a > b) {\n    return (a - b;\n", "utf-8");
    
    // Auto-heal the file
    const result = fixer.analyzeAndHealFile("broken_test_file.js");
    const healedContent = fs.existsSync(brokenJsPath) ? fs.readFileSync(brokenJsPath, "utf-8") : "";

    // Clean up on disk
    if (fs.existsSync(brokenJsPath)) {
      fs.unlinkSync(brokenJsPath);
    }

    if (result.isHealed && healedContent.includes("}") && healedContent.includes(")")) {
      recordTest("SyntaxFixer", "AST Brackets Auto-healing & Balancing", "PASS", "Automatically detects unbalanced curly braces and parentheses, adding correct terminators.");
    } else {
      recordTest("SyntaxFixer", "AST Brackets Auto-healing & Balancing", "FAIL", `Healing failed. Result: ${JSON.stringify(result)}, Content: ${healedContent}`);
    }

    // Markdown file test cleanup
    const markdownWrapperJs = path.resolve(WORKSPACE_DIR, "md_wrapped.js");
    fs.writeFileSync(markdownWrapperJs, "```javascript\nconst a = 12;\nconsole.log(a);\n```", "utf-8");
    const mdResult = fixer.analyzeAndHealFile("md_wrapped.js");
    const mdHealedContent = fs.existsSync(markdownWrapperJs) ? fs.readFileSync(markdownWrapperJs, "utf-8") : "";
    
    if (fs.existsSync(markdownWrapperJs)) fs.unlinkSync(markdownWrapperJs);

    if (mdResult.isHealed && !mdHealedContent.includes("```")) {
      recordTest("SyntaxFixer", "Markdown Wrap Stripping", "PASS", "Cleaned accidental markdown block formatting successfully.");
    } else {
      recordTest("SyntaxFixer", "Markdown Wrap Stripping", "FAIL", "Failed to clear out markdown wrappers.");
    }
  } catch (e: any) {
    recordTest("SyntaxFixer", "Exception Raised", "FAIL", e.message);
  }

  // 4. CodeWeaver Unit Tests
  try {
    const memory = new MemoryLedger(WORKSPACE_DIR);
    const weaver = new CodeWeaver(WORKSPACE_DIR, memory);
    
    // Weave standard Node structure
    const weaveResult = await weaver.weaveFullArchitecture("node_express", "standard");
    
    // Verify files created
    const expectedFiles = ["package.json", "src/index.js", "README.md", ".env"];
    let allExpectedExist = true;
    for (const f of expectedFiles) {
      if (!fs.existsSync(path.resolve(WORKSPACE_DIR, f))) {
        allExpectedExist = false;
        console.warn(`[Weaver Check] Missing expected file: ${f}`);
      }
    }

    if (weaveResult.filesCount > 0 && allExpectedExist) {
      recordTest("CodeWeaver", "Architecture Blueprint Rendering", "PASS", `Weaved Node architecture successfully (${weaveResult.filesCount} files generated).`);
    } else {
      recordTest("CodeWeaver", "Architecture Blueprint Rendering", "FAIL", `Weave completed with issues. Total: ${weaveResult.filesCount}`);
    }

    // Test programmatic Gigantic File Weaver
    const gPath = "src/stress_gigantic_test.js";
    const gResult = await weaver.weaveGiganticFile(gPath, 1500); // Generate 1500 lines as a standard test density
    const actualLines = fs.readFileSync(path.resolve(WORKSPACE_DIR, gPath), "utf-8").split("\n").length;

    // Clean up woven test files on disk
    const cleanFilesList = [
      "package.json", "src/index.js", "README.md", ".env", "src/stress_gigantic_test.js",
      "src/controllers/userController.js", "src/services/userService.js", "src/models/userModel.js", "src/tests/user.test.js"
    ];
    cleanFilesList.forEach(f => {
      const p = path.resolve(WORKSPACE_DIR, f);
      if (fs.existsSync(p)) fs.unlinkSync(p);
    });

    if (gResult.lines >= 1500 && actualLines >= 1500) {
      recordTest("CodeWeaver", "High-Volume Multi-Line File Generation", "PASS", `Successfully programmatically weaved gigantic file: ${gResult.lines} lines.`);
    } else {
      recordTest("CodeWeaver", "High-Volume Multi-Line File Generation", "FAIL", `Lines count mismatch: expected 1500+, found ${actualLines}`);
    }
  } catch (e: any) {
    recordTest("CodeWeaver", "Exception Raised", "FAIL", e.message);
  }

  // 5. SemanticIndexer Unit Tests
  try {
    const memory = new MemoryLedger(WORKSPACE_DIR);
    const indexer = new SemanticIndexer(WORKSPACE_DIR, memory);
    
    // Write sample class and function to workspace
    const sampleFilePath = path.resolve(WORKSPACE_DIR, "sample_index_file.ts");
    fs.writeFileSync(
      sampleFilePath,
      `export class AnalyticalSolver {
        public calculateVelocity(distance: number, time: number) {
          return distance / time;
        }
      }
      export function coreEngineBoot() {
        return true;
      }`,
      "utf-8"
    );

    const result = indexer.indexWorkspace();
    
    // Fetch state to see if index was stored
    const indexState = memory.getState().symbolIndex;
    
    if (fs.existsSync(sampleFilePath)) fs.unlinkSync(sampleFilePath);

    const hasSolverClass = indexState?.symbols["AnalyticalSolver"] !== undefined;
    const hasBootFunc = indexState?.symbols["coreEngineBoot"] !== undefined;

    if (result.totalSymbols > 0 && hasSolverClass && hasBootFunc) {
      recordTest("SemanticIndexer", "Abstract Syntax Tree Parsing & Symbol Extraction", "PASS", `Successfully extracted, mapped and stored symbols in ledger: ${result.totalSymbols} symbols found.`);
    } else {
      recordTest("SemanticIndexer", "Abstract Syntax Tree Parsing & Symbol Extraction", "FAIL", `Symbols missing from ledger state. Found class: ${hasSolverClass}, func: ${hasBootFunc}`);
    }
  } catch (e: any) {
    recordTest("SemanticIndexer", "Exception Raised", "FAIL", e.message);
  }

  // Extra Proactive Auditing & Hardened Unit Tests
  console.log("\n----------------------------------------------------------------------");
  console.log("HARDENED COGNITIVE AUDIT & SECURITY BOUNDS");
  console.log("----------------------------------------------------------------------");
  
  // 1. JS String and Comment Brace Isolation
  try {
    const memory = new MemoryLedger(WORKSPACE_DIR);
    const fixer = new SyntaxFixer(WORKSPACE_DIR, memory);
    const testFile = "js_comments_test.js";
    const filePath = path.resolve(WORKSPACE_DIR, testFile);
    
    // Balanced curlies with unmatched curlies inside strings and comments
    const code = `
      // This has { unclosed comment brace
      const message = "Unclosed string brace {";
      function worksProperly() {
        return true;
      }
    `;
    fs.writeFileSync(filePath, code, "utf-8");
    const res = fixer.analyzeAndHealFile(testFile);
    const content = fs.readFileSync(filePath, "utf-8");
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);

    if (res.isHealed === false && !content.includes("// Autocomplete")) {
      recordTest("SyntaxFixer_Hardening", "JS Comments & String Brace Isolation", "PASS", "Correctly ignored unmatched braces inside string literals and single-line comments.");
    } else {
      recordTest("SyntaxFixer_Hardening", "JS Comments & String Brace Isolation", "FAIL", `Mistakenly auto-completed braces: ${JSON.stringify(res)}, Content: ${content}`);
    }
  } catch (e: any) {
    recordTest("SyntaxFixer_Hardening", "JS Comments & String Brace Isolation", "FAIL", e.message);
  }

  // 2. Python Inline Comment Colon Integration
  try {
    const memory = new MemoryLedger(WORKSPACE_DIR);
    const fixer = new SyntaxFixer(WORKSPACE_DIR, memory);
    const testFile = "py_comments_test.py";
    const filePath = path.resolve(WORKSPACE_DIR, testFile);
    
    // Def statement with inline comment missing colon
    const code = `def run_calc(x, y)  # Inline comment here\n    return x + y\n`;
    fs.writeFileSync(filePath, code, "utf-8");
    const res = fixer.analyzeAndHealFile(testFile);
    const content = fs.readFileSync(filePath, "utf-8");
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);

    if (res.isHealed && content.includes("def run_calc(x, y):  # Inline comment here")) {
      recordTest("SyntaxFixer_Hardening", "Python Inline Comment Colon Healing", "PASS", "Correctly inserted colon BEFORE inline comment rather than appending to end of line.");
    } else {
      recordTest("SyntaxFixer_Hardening", "Python Inline Comment Colon Healing", "FAIL", `Failed to insert colon before inline comment. Content: ${content}`);
    }
  } catch (e: any) {
    recordTest("SyntaxFixer_Hardening", "Python Inline Comment Colon Healing", "FAIL", e.message);
  }

  // 3. Command Chaining and Env Var Security Guards
  try {
    // Attempting block commands chained via &&
    const chainedCmd = "echo hello && sh -c 'id'";
    const res = await postJson(`${TEST_API_BASE}/api/meta/workspace/run`, { command: chainedCmd });
    if (res.success === false && res.output.includes("Security Guardrail: Command 'sh' is not permitted")) {
      recordTest("Security_Hardening", "Shell Operator Command Chaining Interception", "PASS", "Blocked unauthorized chained commands successfully.");
    } else {
      recordTest("Security_Hardening", "Shell Operator Command Chaining Interception", "FAIL", `Failed to block chained command: ${JSON.stringify(res)}`);
    }

    // Testing prefixed environment variable allowance
    const prefixedCmd = "NODE_ENV=test node -v";
    const prefixRes = await postJson(`${TEST_API_BASE}/api/meta/workspace/run`, { command: prefixedCmd });
    if (prefixRes.success === true) {
      recordTest("Security_Hardening", "Prefix Environment Variable Command Allowance", "PASS", "Permitted safe commands prefixed with custom environment variable declarations.");
    } else {
      recordTest("Security_Hardening", "Prefix Environment Variable Command Allowance", "FAIL", `Rejected safe prefixed command: ${JSON.stringify(prefixRes)}`);
    }
  } catch (e: any) {
    recordTest("Security_Hardening", "Security Hardening Test Exception", "FAIL", e.message);
  }

  console.log("\n----------------------------------------------------------------------");
  console.log("LAYER 3: INTEGRATION & HTTP API TESTING - REAL ENDPOINTS");
  console.log("----------------------------------------------------------------------");

  // Verify server is awake and accepting queries
  try {
    const workflows = await getJson(`${TEST_API_BASE}/api/meta/workflows`);
    if (Array.isArray(workflows)) {
      recordTest("API_Integration", "Workflows Index Endpoint", "PASS", "Successfully connected and retrieved workflow register array.");
    } else {
      recordTest("API_Integration", "Workflows Index Endpoint", "FAIL", "Endpoint returned invalid or unexpected non-array format.");
    }

    // Set Goal endpoint test
    const goalMsg = "Comprehensive E2E Auto Diagnostic Goal";
    const goalRes = await postJson(`${TEST_API_BASE}/api/meta/autonomous/goal`, { goal: goalMsg });
    
    if (goalRes.status === "success" && goalRes.ledgerState?.currentGoal === goalMsg) {
      recordTest("API_Integration", "Autonomous Goal Provisioning", "PASS", "Set Goal API correctly persists target state and constructs DAG checklist.");
    } else {
      recordTest("API_Integration", "Autonomous Goal Provisioning", "FAIL", `Persisting goal state failed: ${JSON.stringify(goalRes)}`);
    }

    // Workspace Files Explorer Endpoint test
    const filesRes = await getJson(`${TEST_API_BASE}/api/meta/workspace/files`);
    if (filesRes && Array.isArray(filesRes.files)) {
      recordTest("API_Integration", "Workspace File Indexing", "PASS", "Retrieved directories list and virtual filesystem index.");
    } else {
      recordTest("API_Integration", "Workspace File Indexing", "FAIL", "Files listing endpoint error or malformed structure.");
    }

    // Semantic Indexing Endpoint test
    const indexRes = await postJson(`${TEST_API_BASE}/api/meta/autonomous/index`, {});
    if (indexRes.status === "success" && indexRes.filesIndexed !== undefined) {
      recordTest("API_Integration", "Semantic Cognitive Indexing", "PASS", `Successfully indexed project workspace. Indexed: ${indexRes.filesIndexed} files.`);
    } else {
      recordTest("API_Integration", "Semantic Cognitive Indexing", "FAIL", `API response failed: ${JSON.stringify(indexRes)}`);
    }

    // Metrics and Locks API endpoints test
    const metricsRes = await getJson(`${TEST_API_BASE}/api/meta/autonomous/metrics`);
    const locksRes = await getJson(`${TEST_API_BASE}/api/meta/locks`);
    const debugEnvRes = await getJson(`${TEST_API_BASE}/api/meta/debug-env`);

    if (metricsRes.metrics && locksRes !== undefined && debugEnvRes.hasGeminiKey !== undefined) {
      recordTest("API_Integration", "System Telemetry, Claims Locks & Debug Env", "PASS", "All background diagnostic API endpoints fully operational.");
    } else {
      recordTest("API_Integration", "System Telemetry, Claims Locks & Debug Env", "FAIL", "Failed to retrieve diagnostic endpoints.");
    }

  } catch (e: any) {
    recordTest("API_Integration", "Endpoint Connectivity Failure", "FAIL", `Could not query REST API server: ${e.message}`);
  }

  console.log("\n----------------------------------------------------------------------");
  console.log("LAYER 4: CHAOS, SECURITY BOUNDS & AST DESTRUCTIVE STRESS CHECKS");
  console.log("----------------------------------------------------------------------");

  // 1. Sandbox Jailbreak Prevention / Security Constraints Guardrails
  try {
    // Attempting to run unallowed shell commands e.g. "sh", "rm -rf", "curl"
    const forbiddenCommand = "sh -c 'echo jailbreak'";
    const runRes = await postJson(`${TEST_API_BASE}/api/meta/workspace/run`, { command: forbiddenCommand });
    
    if (runRes.success === false && runRes.output.includes("Security Guardrail")) {
      recordTest("Security", "Sandbox Jailbreak Prevention Guardrails", "PASS", "Blocked execution of unauthorized command (blocked: sh).");
    } else {
      recordTest("Security", "Sandbox Jailbreak Prevention Guardrails", "FAIL", `Jailbreak allowed or did not fail securely! Result: ${JSON.stringify(runRes)}`);
    }

    // Path traversal block test
    const traversalPath = "../../etc/passwd";
    const traversalRes = await getJson(`${TEST_API_BASE}/api/meta/workspace/file?path=${encodeURIComponent(traversalPath)}`);
    
    if (traversalRes.error && traversalRes.error.includes("traversal blocked")) {
      recordTest("Security", "Directory Traversal Prevention Guardrails", "PASS", "Successfully intercepted and blocked path traversal escape attempt.");
    } else {
      recordTest("Security", "Directory Traversal Prevention Guardrails", "FAIL", `Escape not blocked! Result: ${JSON.stringify(traversalRes)}`);
    }
  } catch (e: any) {
    recordTest("Security", "Jailbreak Testing Exception", "FAIL", e.message);
  }

  // 2. Syntax Repair / Self-Heal Verification API
  try {
    // Create a broken file on disk inside workspace
    const badJsPath = path.resolve(WORKSPACE_DIR, "ast_damaged.js");
    fs.writeFileSync(badJsPath, "const express = express();\nfunction startServer() {\n  console.log('Booting');\n  // Missing closing blocks\n", "utf-8");

    // Call diagnostic heal API
    const healRes = await postJson(`${TEST_API_BASE}/api/meta/autonomous/diagnostic`, { filePath: "ast_damaged.js" });
    const repairedCode = fs.existsSync(badJsPath) ? fs.readFileSync(badJsPath, "utf-8") : "";
    
    if (fs.existsSync(badJsPath)) fs.unlinkSync(badJsPath);

    if (healRes.isHealed && repairedCode.includes("}") && repairedCode.includes("express = require(\"express\")")) {
      recordTest("Self_Healing", "REST API AST Code Diagnostic & Repair", "PASS", "Self-healer detected and resolved unbalanced brackets and missing express import dependencies in real-time.");
    } else {
      recordTest("Self_Healing", "REST API AST Code Diagnostic & Repair", "FAIL", `Heal unsuccessful. Response: ${JSON.stringify(healRes)}, Code: ${repairedCode}`);
    }
  } catch (e: any) {
    recordTest("Self_Healing", "Diagnostic API Exception", "FAIL", e.message);
  }

  // 3. Concurrency Stress Burst tests
  try {
    console.log("[Stress] Sending burst of 5 parallel requests to REST endpoints...");
    const promises = Array.from({ length: 5 }).map(() => getJson(`${TEST_API_BASE}/api/meta/workflows`));
    const results = await Promise.all(promises);
    
    const allValid = results.every(res => Array.isArray(res));
    if (allValid) {
      recordTest("Stress_Test", "API Concurrency Burst Load", "PASS", "REST server handled parallel loads without throttling or connection failures.");
    } else {
      recordTest("Stress_Test", "API Concurrency Burst Load", "FAIL", "Some concurrent loads failed.");
    }
  } catch (e: any) {
    recordTest("Stress_Test", "Concurrency Test Exception", "FAIL", e.message);
  }

  console.log("\n======================================================================");
  console.log("                      TEST RESULTS SUMMARY REPORT");
  console.log("======================================================================");
  
  const passedCount = testResults.filter(r => r.status === "PASS").length;
  const failedCount = testResults.filter(r => r.status === "FAIL").length;
  const totalCount = testResults.length;
  const reliability = ((passedCount / totalCount) * 100).toFixed(1);

  console.log(`TOTAL TESTS EXECUTED: ${totalCount}`);
  console.log(`🟢 PASSED TESTS     : ${passedCount}`);
  console.log(`🔴 FAILED TESTS     : ${failedCount}`);
  console.log(`✨ SYSTEM RELIABILITY: ${reliability}%`);
  console.log("======================================================================\n");

  if (failedCount > 0) {
    console.error("Test Suite Completed: SYSTEM ANOMALIES DETECTED.");
    process.exit(1);
  } else {
    console.log("Test Suite Completed: ALL COGNITIVE MODULES AND SANITY LAYERS VERIFIED SECURE AND STABLE.");
    process.exit(0);
  }
}

runAllTests().catch((err) => {
  console.error("Master Test Suite Exception Fatal:", err);
  process.exit(1);
});
