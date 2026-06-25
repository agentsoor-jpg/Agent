"""
Execution Engine - Secure and robust execution core.
Supports full filesystem manipulation and shell command execution with guardrails,
timeouts, logging, and structured error handling.
"""

import os
import subprocess
import time
from typing import Dict, Any, List, Optional
from loguru import logger

class ExecutionError(Exception):
    """Structured execution exceptions."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ExecutionEngine:
    def __init__(self, workspace_root: str = "./workspace_run"):
        self.workspace_root = os.path.abspath(workspace_root)
        self.allowed_commands = {"python", "pip", "pytest", "node", "npm", "git", "echo", "cat", "ls", "mkdir", "rm", "mv", "cp"}
        self.execution_log: List[Dict[str, Any]] = []
        
        # Ensure workspace exists
        os.makedirs(self.workspace_root, exist_ok=True)
        logger.info(f"ExecutionEngine initialized with workspace: {self.workspace_root}")

    def _get_secure_path(self, relative_path: str) -> str:
        """Resolve path and ensure it remains inside the workspace sandbox."""
        full_path = os.path.abspath(os.path.join(self.workspace_root, relative_path))
        if not full_path.startswith(self.workspace_root):
            raise ExecutionError(
                "Path Traversal Blocked",
                {"attempted_path": relative_path, "resolved_path": full_path, "workspace": self.workspace_root}
            )
        return full_path

    def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Create or overwrite a file with contents."""
        start_time = time.time()
        try:
            full_path = self._get_secure_path(file_path)
            # Create parent directories if they do not exist
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            duration = time.time() - start_time
            result = {
                "action": "write_file",
                "file_path": file_path,
                "bytes_written": len(content),
                "duration_ms": round(duration * 1000, 2),
                "success": True
            }
            self._log_event(result)
            return result
        except Exception as e:
            err_msg = f"Failed to write file {file_path}: {e}"
            logger.error(err_msg)
            raise ExecutionError(err_msg, {"file_path": file_path})

    def read_file(self, file_path: str) -> Dict[str, Any]:
        """Read file contents safely."""
        try:
            full_path = self._get_secure_path(file_path)
            if not os.path.exists(full_path):
                raise ExecutionError("File not found", {"file_path": file_path})

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            result = {
                "action": "read_file",
                "file_path": file_path,
                "content": content,
                "bytes_read": len(content),
                "success": True
            }
            return result
        except Exception as e:
            err_msg = f"Failed to read file {file_path}: {e}"
            logger.error(err_msg)
            raise ExecutionError(err_msg, {"file_path": file_path})

    def create_directory(self, dir_path: str) -> Dict[str, Any]:
        """Create a new folder inside workspace."""
        try:
            full_path = self._get_secure_path(dir_path)
            os.makedirs(full_path, exist_ok=True)
            result = {
                "action": "create_directory",
                "directory": dir_path,
                "success": True
            }
            self._log_event(result)
            return result
        except Exception as e:
            err_msg = f"Failed to create directory {dir_path}: {e}"
            logger.error(err_msg)
            raise ExecutionError(err_msg, {"dir_path": dir_path})

    def modify_file(self, file_path: str, target: str, replacement: str) -> Dict[str, Any]:
        """Perform search-and-replace modification on a file."""
        try:
            full_path = self._get_secure_path(file_path)
            if not os.path.exists(full_path):
                raise ExecutionError("File not found", {"file_path": file_path})

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            if target not in content:
                raise ExecutionError("Target string for replacement not found in file", {"file_path": file_path, "target": target})

            updated_content = content.replace(target, replacement, 1)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            result = {
                "action": "modify_file",
                "file_path": file_path,
                "success": True
            }
            self._log_event(result)
            return result
        except Exception as e:
            err_msg = f"Failed to modify file {file_path}: {e}"
            logger.error(err_msg)
            raise ExecutionError(err_msg, {"file_path": file_path})

    def run_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a shell command with an allowlist guardrail, timeout, and logs."""
        start_time = time.time()
        logger.info(f"ExecutionEngine: Running command: {command}")
        
        # Guardrail check
        parts = command.strip().split()
        if not parts:
            raise ExecutionError("Empty command provided")
        
        base_cmd = parts[0]
        if base_cmd not in self.allowed_commands:
            raise ExecutionError(
                f"Command '{base_cmd}' is blocked by execution guardrails.",
                {"command": command, "allowed_commands": list(self.allowed_commands)}
            )

        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=self.workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                return_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                return_code = -1
                logger.error(f"Command '{command}' timed out after {timeout} seconds.")
                result = {
                    "command": command,
                    "stdout": stdout,
                    "stderr": stderr + f"\n[Error: Command timed out after {timeout}s]",
                    "return_code": return_code,
                    "success": False,
                    "timed_out": True,
                    "duration_ms": round((time.time() - start_time) * 1000, 2)
                }
                self._log_event(result)
                return result

            duration = time.time() - start_time
            result = {
                "command": command,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code,
                "success": return_code == 0,
                "timed_out": False,
                "duration_ms": round(duration * 1000, 2)
            }
            self._log_event(result)
            return result
        except Exception as e:
            err_msg = f"Shell execution crash on command: {command}. Error: {e}"
            logger.error(err_msg)
            raise ExecutionError(err_msg, {"command": command})

    def _log_event(self, event: Dict[str, Any]):
        event["timestamp"] = time.time()
        self.execution_log.append(event)
        
    def get_logs(self) -> List[Dict[str, Any]]:
        return self.execution_log
