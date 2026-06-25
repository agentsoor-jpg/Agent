import express from "express";
import path from "path";
import fs from "fs";
import { exec } from "child_process";
import { createServer as createViteServer } from "vite";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

app.use(express.json());

const WORKSPACE_DIR = path.resolve(process.cwd(), "workspace_run");
if (!fs.existsSync(WORKSPACE_DIR)) {
  fs.mkdirSync(WORKSPACE_DIR, { recursive: true });
}

/**
 * 1. Robust and Secure Programmatic Execution Engine
 * Crucially, all actions strictly produce genuine, non-simulated output.
 * Every result has real stdout, every failure has real stderr.
 */
export class ExecutionEngine {
  private workspaceDir: string;

  constructor(workspaceDir: string) {
    this.workspaceDir = workspaceDir;
  }

  private resolvePath(targetPath: string): string {
    const fullPath = path.resolve(this.workspaceDir, targetPath);
    if (!fullPath.startsWith(this.workspaceDir)) {
      throw new Error("Access denied. Paths must be inside the workspace.");
    }
    return fullPath;
  }

  public async writeFile(targetPath: string, content: string): Promise<{ success: boolean; stdout: string; stderr: string }> {
    try {
      const fullPath = this.resolvePath(targetPath);
      await fs.promises.mkdir(path.dirname(fullPath), { recursive: true });
      await fs.promises.writeFile(fullPath, content || "", "utf-8");
      return {
        success: true,
        stdout: `SUCCESS: File successfully written to ${targetPath}. (Size: ${(content || "").length} bytes)`,
        stderr: ""
      };
    } catch (err: any) {
      return {
        success: false,
        stdout: "",
        stderr: `ERROR: Failed to write file to ${targetPath}. Details: ${err.message || err}`
      };
    }
  }

  public async readFile(targetPath: string): Promise<{ success: boolean; stdout: string; stderr: string }> {
    try {
      const fullPath = this.resolvePath(targetPath);
      if (!fs.existsSync(fullPath)) {
        return {
          success: false,
          stdout: "",
          stderr: `ERROR: File not found at path: ${targetPath}`
        };
      }
      const content = await fs.promises.readFile(fullPath, "utf-8");
      return {
        success: true,
        stdout: content,
        stderr: ""
      };
    } catch (err: any) {
      return {
        success: false,
        stdout: "",
        stderr: `ERROR: Failed to read file from ${targetPath}. Details: ${err.message || err}`
      };
    }
  }

  public async createDirectory(targetPath: string): Promise<{ success: boolean; stdout: string; stderr: string }> {
    try {
      const fullPath = this.resolvePath(targetPath);
      await fs.promises.mkdir(fullPath, { recursive: true });
      return {
        success: true,
        stdout: `SUCCESS: Directory created successfully at ${targetPath}`,
        stderr: ""
      };
    } catch (err: any) {
      return {
        success: false,
        stdout: "",
        stderr: `ERROR: Failed to create directory at ${targetPath}. Details: ${err.message || err}`
      };
    }
  }

  public async runCommand(command: string, timeout: number = 15000): Promise<{ success: boolean; stdout: string; stderr: string; exitCode: number }> {
    return new Promise((resolve) => {
      exec(command, { cwd: this.workspaceDir, timeout }, (error, stdout, stderr) => {
        let exitCode = 0;
        if (error) {
          exitCode = error.code !== undefined ? error.code : 1;
          if (error.killed) {
            resolve({
              success: false,
              stdout: stdout || "",
              stderr: (stderr || "") + `\nCommand timed out after ${timeout}ms`,
              exitCode
            });
            return;
          }
          resolve({
            success: false,
            stdout: stdout || "",
            stderr: stderr || error.message || "Command execution failed",
            exitCode
          });
          return;
        }
        resolve({
          success: true,
          stdout: stdout || "",
          stderr: stderr || "",
          exitCode
        });
      });
    });
  }
}

/**
 * 2. System Planner
 * Handles validation, parsing, planning of requests, and pipes execution steps to the ExecutionEngine.
 */
export class Planner {
  private engine: ExecutionEngine;

  constructor(engine: ExecutionEngine) {
    this.engine = engine;
  }

  public async planAndExecute(action: string, params: { targetPath?: string; content?: string; command?: string; timeout?: number }): Promise<{
    status: "success" | "failed";
    steps: Array<{ action: string; status: "success" | "failed"; path?: string; command?: string }>;
    stdout: string;
    stderr: string;
    exit_code: number;
    files_created: string[];
  }> {
    // Validate action presence
    if (!action) {
      return {
        status: "failed",
        steps: [],
        stdout: "",
        stderr: "Missing 'action' parameter.",
        exit_code: 1,
        files_created: []
      };
    }

    try {
      switch (action) {
        case "write_file": {
          if (!params.targetPath) {
            return {
              status: "failed",
              steps: [],
              stdout: "",
              stderr: "Missing 'path' parameter for write_file.",
              exit_code: 1,
              files_created: []
            };
          }
          const result = await this.engine.writeFile(params.targetPath, params.content || "");
          return {
            status: result.success ? "success" : "failed",
            steps: [{ action: "write_file", status: result.success ? "success" : "failed", path: params.targetPath }],
            stdout: result.stdout,
            stderr: result.stderr,
            exit_code: result.success ? 0 : 1,
            files_created: result.success ? [params.targetPath] : []
          };
        }

        case "read_file": {
          if (!params.targetPath) {
            return {
              status: "failed",
              steps: [],
              stdout: "",
              stderr: "Missing 'path' parameter for read_file.",
              exit_code: 1,
              files_created: []
            };
          }
          const result = await this.engine.readFile(params.targetPath);
          return {
            status: result.success ? "success" : "failed",
            steps: [{ action: "read_file", status: result.success ? "success" : "failed", path: params.targetPath }],
            stdout: result.stdout,
            stderr: result.stderr,
            exit_code: result.success ? 0 : 1,
            files_created: []
          };
        }

        case "create_directory": {
          if (!params.targetPath) {
            return {
              status: "failed",
              steps: [],
              stdout: "",
              stderr: "Missing 'path' parameter for create_directory.",
              exit_code: 1,
              files_created: []
            };
          }
          const result = await this.engine.createDirectory(params.targetPath);
          return {
            status: result.success ? "success" : "failed",
            steps: [{ action: "create_directory", status: result.success ? "success" : "failed", path: params.targetPath }],
            stdout: result.stdout,
            stderr: result.stderr,
            exit_code: result.success ? 0 : 1,
            files_created: []
          };
        }

        case "run_command": {
          if (!params.command) {
            return {
              status: "failed",
              steps: [],
              stdout: "",
              stderr: "Missing 'command' parameter for run_command.",
              exit_code: 1,
              files_created: []
            };
          }
          const cmdTimeout = typeof params.timeout === "number" ? params.timeout : 15000;
          const result = await this.engine.runCommand(params.command, cmdTimeout);
          return {
            status: result.success ? "success" : "failed",
            steps: [{ action: "run_command", status: result.success ? "success" : "failed", command: params.command }],
            stdout: result.stdout,
            stderr: result.stderr,
            exit_code: result.exitCode,
            files_created: []
          };
        }

        case "execute_plan":
        case "execute_goal": {
          return {
            status: "failed",
            steps: [],
            stdout: "",
            stderr: "Agent-based execution and planning are disabled per system integrity directives. Only direct verified programmatic execution is supported.",
            exit_code: 1,
            files_created: []
          };
        }

        default:
          return {
            status: "failed",
            steps: [],
            stdout: "",
            stderr: `Unknown action: ${action}`,
            exit_code: 1,
            files_created: []
          };
      }
    } catch (err: any) {
      return {
        status: "failed",
        steps: [],
        stdout: "",
        stderr: err.message || "Internal execution core failure",
        exit_code: 1,
        files_created: []
      };
    }
  }
}

// Global Instances
const executionEngine = new ExecutionEngine(WORKSPACE_DIR);
const planner = new Planner(executionEngine);

// Single unified execute endpoint: API -> Planner -> ExecutionEngine -> OS
app.post("/api/meta/execute", async (req, res) => {
  const { action, path: targetPath, content, command, timeout } = req.body;

  const result = await planner.planAndExecute(action, {
    targetPath,
    content,
    command,
    timeout
  });

  if (result.status === "failed") {
    return res.status(400).json(result);
  }

  return res.json(result);
});

async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Execution Engine server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
