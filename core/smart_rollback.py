"""
core/smart_rollback.py - Smart Git-based Rollback v7.1
Checkpoints before agent actions, selective rollback of only failed agent's files.
"""

import asyncio
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class SmartRollback:
    """Git-based checkpoint system for agent workflows."""
    
    def __init__(self, workspace_dir: str = "workspaces"):
        self.workspace_dir = Path(workspace_dir)
        self.checkpoint_dir = Path("state/checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self._checkpoints: Dict[str, Dict] = {}
        self._load_history()
    
    def _load_history(self):
        """Load checkpoint history."""
        history_file = self.checkpoint_dir / "history.json"
        if history_file.exists():
            try:
                self._checkpoints = json.loads(history_file.read_text())
            except (json.JSONDecodeError, IOError):
                self._checkpoints = {}
    
    def _save_history(self):
        """Persist checkpoint history."""
        history_file = self.checkpoint_dir / "history.json"
        try:
            history_file.write_text(json.dumps(self._checkpoints, indent=2, default=str))
        except IOError:
            pass
    
    def _git_add(self, repo_path: str) -> bool:
        """Run git add for workspace."""
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "add", "-A"],
                capture_output=True,
                timeout=30
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _git_commit(self, repo_path: str, message: str) -> Optional[str]:
        """Run git commit and return commit hash."""
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "commit", "-m", message],
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0:
                # Get commit hash
                hash_result = subprocess.run(
                    ["git", "-C", repo_path, "rev-parse", "HEAD"],
                    capture_output=True,
                    timeout=10
                )
                if hash_result.returncode == 0:
                    return hash_result.stdout.decode().strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
    
    def _git_diff(self, repo_path: str, commit_a: str, commit_b: str = None) -> str:
        """Get git diff between commits or commit and working tree."""
        try:
            if commit_b is None:
                result = subprocess.run(
                    ["git", "-C", repo_path, "diff", "--stat"],
                    capture_output=True,
                    timeout=30
                )
            else:
                result = subprocess.run(
                    ["git", "-C", repo_path, "diff", commit_a, commit_b, "--stat"],
                    capture_output=True,
                    timeout=30
                )
            return result.stdout.decode()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""
    
    def _get_changed_files(self, repo_path: str, commit: str) -> List[str]:
        """Get list of files changed in a commit."""
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0:
                return [f.strip() for f in result.stdout.decode().split("\n") if f.strip()]
            return []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
    
    def _get_file_at_commit(self, repo_path: str, commit: str, file_path: str) -> Optional[str]:
        """Get file content at specific commit."""
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "show", f"{commit}:{file_path}"],
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout.decode()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
    
    def checkpoint_before(
        self,
        project_id: str,
        agent_id: str,
        task_id: str,
        workspace_path: str
    ) -> Optional[str]:
        """
        Create checkpoint BEFORE agent action.
        Returns checkpoint_id.
        """
        checkpoint_id = f"cp_{uuid.uuid4().hex[:8]}"
        
        # Get current git status
        changed_files = []
        try:
            result = subprocess.run(
                ["git", "-C", workspace_path, "status", "--porcelain"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.decode().split("\n"):
                    if line.strip():
                        changed_files.append(line.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        checkpoint_data = {
            "id": checkpoint_id,
            "type": "before",
            "project_id": project_id,
            "agent_id": agent_id,
            "task_id": task_id,
            "workspace_path": workspace_path,
            "files_before": changed_files,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "outcome": None,
        }
        
        self._checkpoints[checkpoint_id] = checkpoint_data
        self._save_history()
        
        return checkpoint_id
    
    def checkpoint_after(
        self,
        checkpoint_id: str,
        success: bool,
        workspace_path: str,
        modified_files: List[str] = None
    ):
        """
        Create checkpoint AFTER agent action.
        Records outcome and changed files.
        """
        if checkpoint_id not in self._checkpoints:
            return None
        
        checkpoint = self._checkpoints[checkpoint_id]
        checkpoint["status"] = "complete"
        checkpoint["outcome"] = "success" if success else "failed"
        checkpoint["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Get files changed after action
        after_files = modified_files or []
        try:
            result = subprocess.run(
                ["git", "-C", workspace_path, "status", "--porcelain"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                after_files = [f.strip() for f in result.stdout.decode().split("\n") if f.strip()]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        checkpoint["files_after"] = after_files
        checkpoint["newly_changed"] = [
            f for f in after_files if f not in checkpoint.get("files_before", [])
        ]
        
        self._save_history()
        
        return checkpoint_id
    
    async def rollback_agent_only(
        self,
        project_id: str,
        agent_id: str,
        task_id: str,
        workspace_path: str
    ) -> Dict[str, Any]:
        """
        Rollback ONLY this agent's files (not other agents).
        Keeps successful agent changes untouched.
        """
        # Find the checkpoint for this agent
        agent_checkpoint = None
        for cp in self._checkpoints.values():
            if (cp.get("project_id") == project_id and 
                cp.get("agent_id") == agent_id and 
                cp.get("task_id") == task_id and
                cp.get("status") == "complete"):
                agent_checkpoint = cp
                break
        
        if not agent_checkpoint:
            return {"success": False, "error": "No checkpoint found for this agent"}
        
        if agent_checkpoint.get("outcome") == "success":
            return {
                "success": False, 
                "error": "Agent succeeded, no rollback needed"
            }
        
        rollback_id = f"rb_{uuid.uuid4().hex[:8]}"
        files_to_restore = agent_checkpoint.get("newly_changed", [])
        
        # Get parent commit (before this agent)
        try:
            result = subprocess.run(
                ["git", "-C", workspace_path, "rev-parse", "HEAD~1"],
                capture_output=True,
                timeout=10
            )
            parent_commit = result.stdout.decode().strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            parent_commit = None
        
        restored_files = []
        failed_files = []
        
        for file_path in files_to_restore:
            if parent_commit:
                try:
                    # Get file content from parent commit
                    content = self._get_file_at_commit(workspace_path, parent_commit, file_path)
                    
                    if content is not None:
                        # Restore file
                        full_path = Path(workspace_path) / file_path
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        full_path.write_text(content)
                        restored_files.append(file_path)
                    else:
                        # File didn't exist before - delete it
                        full_path = Path(workspace_path) / file_path
                        if full_path.exists():
                            full_path.unlink()
                        restored_files.append(f"{file_path} (deleted)")
                        
                except (IOError, FileNotFoundError):
                    failed_files.append(file_path)
        
        rollback_record = {
            "id": rollback_id,
            "checkpoint_id": checkpoint_id,
            "agent_id": agent_id,
            "project_id": project_id,
            "restored_files": restored_files,
            "failed_files": failed_files,
            "rollback_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self._checkpoints[rollback_id] = rollback_record
        self._save_history()
        
        return {
            "success": True,
            "rollback_id": rollback_id,
            "files_restored": len(restored_files),
            "files_failed": len(failed_files),
            "details": restored_files,
        }
    
    def rollback_history(self) -> List[Dict[str, Any]]:
        """Get all checkpoints and rollbacks."""
        history = []
        
        for cp in sorted(self._checkpoints.values(), 
                        key=lambda x: x.get("created_at", ""), 
                        reverse=True):
            history.append(cp)
        
        return history
    
    def get_checkpoint_diff(self, checkpoint_id: str) -> Dict[str, Any]:
        """Get diff for a checkpoint."""
        if checkpoint_id not in self._checkpoints:
            return {"error": "Checkpoint not found"}
        
        checkpoint = self._checkpoints[checkpoint_id]
        workspace = checkpoint.get("workspace_path", "")
        
        files_before = checkpoint.get("files_before", [])
        files_after = checkpoint.get("files_after", [])
        
        added = [f for f in files_after if f not in files_before]
        removed = [f for f in files_before if f not in files_after]
        modified = [f for f in files_after if f in files_before]
        
        return {
            "checkpoint_id": checkpoint_id,
            "agent_id": checkpoint.get("agent_id"),
            "task_id": checkpoint.get("task_id"),
            "outcome": checkpoint.get("outcome"),
            "added_files": added,
            "removed_files": removed,
            "modified_files": modified,
            "total_added": len(added),
            "total_removed": len(removed),
            "total_modified": len(modified),
        }
    
    def auto_merge_on_success(
        self,
        project_id: str,
        workspace_path: str
    ) -> Dict[str, Any]:
        """
        When all agents in a phase succeed, create a merge commit.
        """
        # Find all successful checkpoints for this project
        project_checkpoints = [
            cp for cp in self._checkpoints.values()
            if cp.get("project_id") == project_id and 
            cp.get("outcome") == "success"
        ]
        
        if not project_checkpoints:
            return {"success": False, "error": "No successful checkpoints"}
        
        # Get all files changed by successful agents
        all_files = set()
        for cp in project_checkpoints:
            all_files.update(cp.get("newly_changed", []))
        
        # Create merge commit
        commit_msg = f"Auto-merge for project {project_id}\n\nFiles: {', '.join(all_files)}"
        commit_hash = self._git_commit(workspace_path, commit_msg)
        
        return {
            "success": True,
            "commit_hash": commit_hash,
            "merged_files": list(all_files),
            "checkpoint_count": len(project_checkpoints),
        }


# Global instance
smart_rollback = SmartRollback()
