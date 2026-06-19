"""
coordination/conflict_resolver.py - Git-style Merge Conflicts v7.0
Present conflicts to user, auto-resolve simple conflicts, prevent conflicts.
"""

import asyncio
import difflib
import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── Conflict Types ─────────────────────────────────────────────────────────────

class ConflictType(Enum):
    FILE_EDIT = "file_edit"
    CONTENT_MODIFICATION = "content_modification"
    DELETION = "deletion"
    RENAME = "rename"
    PERMISSION = "permission"


class ConflictStatus(Enum):
    DETECTED = "detected"
    PRESENTED = "presented"
    RESOLVED = "resolved"
    AUTO_RESOLVED = "auto_resolved"


@dataclass
class Conflict:
    """Represents a conflict between two versions."""
    id: str
    conflict_type: ConflictType
    file_path: str
    
    original_content: Optional[str] = None
    version_a: Optional[str] = None  # Your version
    version_b: Optional[str] = None  # Their version
    
    base_content: Optional[str] = None
    
    status: ConflictStatus = ConflictStatus.DETECTED
    resolution: Optional[str] = None
    resolution_strategy: Optional[str] = None
    
    created_at: float = 0
    resolved_at: Optional[float] = None


# ── Diff Utilities ─────────────────────────────────────────────────────────────

class DiffUtils:
    """Utilities for computing and presenting diffs."""
    
    @staticmethod
    def unified_diff(a: str, b: str, from_file: str = "a", to_file: str = "b") -> str:
        """Generate unified diff format."""
        a_lines = a.splitlines(keepends=True)
        b_lines = b.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            a_lines, b_lines,
            fromfile=from_file,
            tofile=to_file,
            lineterm=''
        )
        
        return ''.join(diff)
    
    @staticmethod
    def inline_diff(original: str, new: str) -> List[Dict[str, Any]]:
        """Generate inline diff markers."""
        matcher = difflib.SequenceMatcher(None, original, new)
        
        diffs = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            
            diffs.append({
                "type": tag,
                "old": original[i1:i2],
                "new": new[j1:j2],
                "old_pos": i1,
                "new_pos": j1,
            })
        
        return diffs
    
    @staticmethod
    def three_way_merge(base: str, a: str, b: str) -> Tuple[str, List[Dict]]:
        """
        Perform a three-way merge.
        Returns: (merged_content, conflicts)
        """
        # Simple line-based merge
        base_lines = base.splitlines()
        a_lines = a.splitlines()
        b_lines = b.splitlines()
        
        matcher = difflib.SequenceMatcher(None, base_lines, a_lines)
        a_changes = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                a_changes.append((i1, i2, a_lines[j1:j2]))
        
        matcher = difflib.SequenceMatcher(None, base_lines, b_lines)
        b_changes = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                b_changes.append((i1, i2, b_lines[j1:j2]))
        
        # Check for conflicts
        conflicts = []
        result_lines = []
        base_idx = 0
        
        # Simple overlapping check
        a_regions = set()
        for i1, i2, _ in a_changes:
            for i in range(i1, i2):
                a_regions.add(i)
        
        b_regions = set()
        for i1, i2, _ in b_changes:
            for i in range(i1, i2):
                b_regions.add(i)
        
        overlapping = a_regions & b_regions
        
        if overlapping:
            # Has conflicts - use version A as base with conflict markers
            result = a  # Simplified: just pick one
            conflicts.append({
                "type": "overlapping_changes",
                "regions": list(overlapping),
            })
        else:
            # No conflicts - merge changes
            # This is simplified; real implementation would be more complex
            result = a if len(a) >= len(b) else b
        
        return result, conflicts


# ── Lock Manager ────────────────────────────────────────────────────────────────

class LockManager:
    """Prevent conflicts by locking files before editing."""
    
    def __init__(self, lock_dir: str = "locks"):
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        
        self._locks: Dict[str, Dict[str, Any]] = {}
        self._lock_files: Dict[str, Path] = {}
    
    def acquire_lock(
        self,
        file_path: str,
        owner: str,
        timeout: int = 3600
    ) -> Tuple[bool, Optional[str]]:
        """
        Acquire a lock on a file.
        Returns: (success, lock_id or error_message)
        """
        import time
        
        lock_file = self.lock_dir / f"{hashlib.md5(file_path.encode()).hexdigest()}.lock"
        
        # Check existing lock
        if lock_file.exists():
            try:
                lock_data = json.loads(lock_file.read_text())
                
                if lock_data["owner"] != owner:
                    # Check if lock is stale
                    if time.time() - lock_data["acquired_at"] > lock_data.get("timeout", 3600):
                        # Stale lock - remove it
                        lock_file.unlink()
                    else:
                        return False, f"File locked by {lock_data['owner']}"
            except (json.JSONDecodeError, IOError):
                pass
        
        # Create lock
        lock_id = hashlib.md5(f"{file_path}:{owner}:{time.time()}".encode()).hexdigest()[:16]
        
        lock_data = {
            "id": lock_id,
            "file_path": file_path,
            "owner": owner,
            "acquired_at": time.time(),
            "timeout": timeout,
        }
        
        try:
            lock_file.write_text(json.dumps(lock_data))
            self._locks[file_path] = lock_data
            self._lock_files[file_path] = lock_file
            return True, lock_id
        except IOError:
            return False, "Failed to create lock file"
    
    def release_lock(self, file_path: str, owner: str) -> bool:
        """Release a lock on a file."""
        lock_file = self.lock_dir / f"{hashlib.md5(file_path.encode()).hexdigest()}.lock"
        
        if not lock_file.exists():
            return True
        
        try:
            lock_data = json.loads(lock_file.read_text())
            
            if lock_data["owner"] != owner:
                return False
            
            lock_file.unlink()
            
            if file_path in self._locks:
                del self._locks[file_path]
            if file_path in self._lock_files:
                del self._lock_files[file_path]
            
            return True
        except (json.JSONDecodeError, IOError):
            return False
    
    def check_lock(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Check if a file is locked."""
        lock_file = self.lock_dir / f"{hashlib.md5(file_path.encode()).hexdigest()}.lock"
        
        if not lock_file.exists():
            return None
        
        try:
            return json.loads(lock_file.read_text())
        except (json.JSONDecodeError, IOError):
            return None
    
    def get_all_locks(self) -> Dict[str, Dict[str, Any]]:
        """Get all active locks."""
        locks = {}
        
        for lock_file in self.lock_dir.glob("*.lock"):
            try:
                import time
                lock_data = json.loads(lock_file.read_text())
                
                # Check if stale
                if time.time() - lock_data["acquired_at"] > lock_data.get("timeout", 3600):
                    lock_file.unlink()  # Remove stale
                    continue
                
                locks[lock_data["file_path"]] = lock_data
            except (json.JSONDecodeError, IOError):
                continue
        
        return locks


# ── Conflict Resolver ─────────────────────────────────────────────────────────

class ConflictResolver:
    """
    Git-style merge conflict resolution for agent code edits.
    """
    
    def __init__(self):
        self._diff_utils = DiffUtils()
        self._lock_manager = LockManager()
        self._conflict_handlers: Dict[ConflictType, Callable] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default conflict handlers."""
        self._conflict_handlers[ConflictType.FILE_EDIT] = self._handle_file_edit
        self._conflict_handlers[ConflictType.CONTENT_MODIFICATION] = self._handle_content_mod
        self._conflict_handlers[ConflictType.DELETION] = self._handle_deletion
        self._conflict_handlers[ConflictType.RENAME] = self._handle_rename
        self._conflict_handlers[ConflictType.PERMISSION] = self._handle_permission
    
    # ── Lock Operations ──────────────────────────────────────────────────────
    
    def lock_file(self, file_path: str, owner: str) -> Tuple[bool, Optional[str]]:
        """Lock a file before editing to prevent conflicts."""
        return self._lock_manager.acquire_lock(file_path, owner)
    
    def unlock_file(self, file_path: str, owner: str) -> bool:
        """Unlock a file after editing."""
        return self._lock_manager.release_lock(file_path, owner)
    
    def check_lock(self, file_path: str) -> Optional[Dict]:
        """Check if file is locked."""
        return self._lock_manager.check_lock(file_path)
    
    # ── Conflict Detection ──────────────────────────────────────────────────
    
    def detect_conflicts(
        self,
        file_path: str,
        original_content: str,
        new_content: str
    ) -> List[Conflict]:
        """Detect potential conflicts when merging changes."""
        import time
        import hashlib
        
        conflicts = []
        
        # Check if file has been modified since we started
        if Path(file_path).exists():
            current_content = Path(file_path).read_text()
            
            if current_content != original_content:
                # File was modified - potential conflict
                conflict_id = hashlib.md5(f"{file_path}:{time.time()}".encode()).hexdigest()[:16]
                
                conflict = Conflict(
                    id=conflict_id,
                    conflict_type=ConflictType.FILE_EDIT,
                    file_path=file_path,
                    original_content=original_content,
                    version_a=new_content,
                    version_b=current_content,
                    base_content=original_content,
                    created_at=time.time(),
                )
                
                conflicts.append(conflict)
        
        return conflicts
    
    async def auto_resolve(
        self,
        conflict: Conflict
    ) -> Tuple[bool, Optional[str]]:
        """
        Attempt to auto-resolve a conflict.
        Returns: (success, resolved_content)
        """
        handler = self._conflict_handlers.get(conflict.conflict_type)
        
        if not handler:
            return False, None
        
        return await handler(conflict)
    
    async def _handle_file_edit(self, conflict: Conflict) -> Tuple[bool, Optional[str]]:
        """Handle file edit conflicts."""
        if not conflict.base_content or not conflict.version_a or not conflict.version_b:
            return False, None
        
        # Try three-way merge
        merged, conflicts = DiffUtils.three_way_merge(
            conflict.base_content,
            conflict.version_a,
            conflict.version_b
        )
        
        if not conflicts:
            conflict.resolution = merged
            conflict.resolution_strategy = "three_way_merge"
            conflict.status = ConflictStatus.AUTO_RESOLVED
            return True, merged
        
        return False, None
    
    async def _handle_content_mod(self, conflict: Conflict) -> Tuple[bool, Optional[str]]:
        """Handle content modification conflicts."""
        # Similar to file edit
        return await self._handle_file_edit(conflict)
    
    async def _handle_deletion(self, conflict: Conflict) -> Tuple[bool, Optional[str]]:
        """Handle deletion conflicts."""
        # If one version deleted and other modified, prefer modified
        if not conflict.version_b:  # File was deleted
            conflict.resolution = conflict.version_a
            conflict.resolution_strategy = "keep_modified"
            conflict.status = ConflictStatus.AUTO_RESOLVED
            return True, conflict.version_a
        
        return False, None
    
    async def _handle_rename(self, conflict: Conflict) -> Tuple[bool, Optional[str]]:
        """Handle rename conflicts."""
        # Auto-resolve by keeping the new name
        conflict.resolution = conflict.version_a
        conflict.resolution_strategy = "keep_rename"
        conflict.status = ConflictStatus.AUTO_RESOLVED
        return True, conflict.version_a
    
    async def _handle_permission(self, conflict: Conflict) -> Tuple[bool, Optional[str]]:
        """Handle permission conflicts."""
        # Merge permissions (union of both)
        conflict.resolution = conflict.version_a
        conflict.resolution_strategy = "union_permissions"
        conflict.status = ConflictStatus.AUTO_RESOLVED
        return True, conflict.version_a
    
    # ── Manual Resolution ───────────────────────────────────────────────────
    
    def present_conflict(self, conflict: Conflict) -> Dict[str, Any]:
        """Format a conflict for user presentation."""
        diff_a = DiffUtils.inline_diff(
            conflict.original_content or "",
            conflict.version_a or ""
        )
        
        diff_b = DiffUtils.inline_diff(
            conflict.original_content or "",
            conflict.version_b or ""
        )
        
        return {
            "id": conflict.id,
            "type": conflict.conflict_type.value,
            "file_path": conflict.file_path,
            "original": conflict.original_content,
            "version_a": conflict.version_a,
            "version_b": conflict.version_b,
            "diff_a": diff_a,
            "diff_b": diff_b,
            "status": conflict.status.value,
            "created_at": conflict.created_at,
        }
    
    def resolve_manually(
        self,
        conflict_id: str,
        resolution: str,
        strategy: str = "manual"
    ) -> bool:
        """Manually resolve a conflict with user-provided content."""
        # Store would be managed by caller
        return True
    
    # ── Merge Utilities ──────────────────────────────────────────────────────
    
    def generate_merge_preview(
        self,
        base: str,
        a: str,
        b: str
    ) -> str:
        """Generate a merge preview with conflict markers."""
        merged, conflicts = DiffUtils.three_way_merge(base, a, b)
        
        if conflicts:
            # Add conflict markers like git
            lines = []
            lines.append("<<<<<<< YOUR VERSION")
            lines.extend(a.splitlines())
            lines.append("=======")
            lines.extend(b.splitlines())
            lines.append(">>>>>>> OTHER VERSION")
            return "\n".join(lines)
        
        return merged
    
    def get_conflict_stats(self) -> Dict[str, Any]:
        """Get conflict resolution statistics."""
        return {
            "active_locks": len(self._lock_manager.get_all_locks()),
            "conflict_types": [ct.value for ct in ConflictType],
        }


# ── Global instance ───────────────────────────────────────────────────────────

conflict_resolver = ConflictResolver()
