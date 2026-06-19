"""
memory/forgetting_curve.py - Spaced Repetition Memory v7.0
Important patterns remembered, trivial details fade, user corrections permanent.
"""

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Memory Types ───────────────────────────────────────────────────────────────

class MemoryType(Enum):
    IMPORTANT = "important"      # User corrections, key decisions
    PATTERN = "pattern"          # Recurring patterns
    TRIVIAL = "trivial"          # Minor details, temporary info
    CONTEXT = "context"          # Current working context


# ── Memory Item ────────────────────────────────────────────────────────────────

@dataclass
class MemoryItem:
    """A memory item with forgetting curve properties."""
    id: str
    content: str
    memory_type: MemoryType
    importance: float = 0.5  # 0-1 scale
    
    # Spaced repetition fields
    ease_factor: float = 2.5  # SM-2 algorithm ease factor
    interval: int = 1  # Days until next review
    repetitions: int = 0
    next_review: float = field(default_factory=time.time)
    last_review: float = field(default_factory=time.time)
    
    # Metadata
    source: str = "system"
    tags: List[str] = field(default_factory=list)
    access_count: int = 0
    correction_count: int = 0  # Times user corrected this
    
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # Permanence flags
    is_permanent: bool = False
    is_locked: bool = False  # Cannot be auto-deleted
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance,
            "ease_factor": self.ease_factor,
            "interval": self.interval,
            "repetitions": self.repetitions,
            "next_review": self.next_review,
            "last_review": self.last_review,
            "source": self.source,
            "tags": self.tags,
            "access_count": self.access_count,
            "correction_count": self.correction_count,
            "is_permanent": self.is_permanent,
            "is_locked": self.is_locked,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data.get("memory_type", "trivial")),
            importance=data.get("importance", 0.5),
            ease_factor=data.get("ease_factor", 2.5),
            interval=data.get("interval", 1),
            repetitions=data.get("repetitions", 0),
            next_review=data.get("next_review", time.time()),
            last_review=data.get("last_review", time.time()),
            source=data.get("source", "system"),
            tags=data.get("tags", []),
            access_count=data.get("access_count", 0),
            correction_count=data.get("correction_count", 0),
            is_permanent=data.get("is_permanent", False),
            is_locked=data.get("is_locked", False),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


# ── Spaced Repetition Engine ───────────────────────────────────────────────────

class SpacedRepetitionEngine:
    """
    SM-2 based spaced repetition algorithm.
    """
    
    @staticmethod
    def calculate_next_review(
        quality: int,  # 0-5 rating
        item: MemoryItem
    ) -> Tuple[int, float, int]:
        """
        Calculate next review parameters based on SM-2 algorithm.
        
        Quality ratings:
        0 - Complete blackout
        1 - Incorrect, but recognized correct answer
        2 - Incorrect, correct answer seemed easy
        3 - Correct with difficulty
        4 - Correct after hesitation
        5 - Perfect response
        
        Returns: (new_interval, new_ease_factor, new_repetitions)
        """
        if quality < 3:
            # Failed - reset
            return 1, max(1.3, item.ease_factor - 0.2), 0
        
        # Calculate new ease factor
        new_ease = item.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_ease = max(1.3, new_ease)
        
        # Calculate new interval
        if item.repetitions == 0:
            new_interval = 1
        elif item.repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(item.interval * new_ease)
        
        # Cap maximum interval at 365 days
        new_interval = min(365, new_interval)
        
        return new_interval, new_ease, item.repetitions + 1
    
    @staticmethod
    def get_retention_score(item: MemoryItem) -> float:
        """
        Calculate current retention score (0-1) based on time since last review.
        """
        if item.repetitions == 0:
            return 1.0
        
        days_elapsed = (time.time() - item.last_review) / 86400
        
        # Simplified forgetting curve
        # R = e^(-t/S) where S is stability
        stability = item.interval * item.ease_factor
        retention = math.exp(-days_elapsed / max(stability, 1))
        
        return max(0, min(1, retention))


# ── Forgetting Curve Manager ───────────────────────────────────────────────────

class ForgettingCurveManager:
    """
    Memory system implementing spaced repetition and forgetting curves.
    """
    
    def __init__(self, storage_file: str = "memory/forgetting_curve.json"):
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._memories: Dict[str, MemoryItem] = {}
        self._tags: Dict[str, set] = defaultdict(set)  # tag -> memory_ids
        self._sr_engine = SpacedRepetitionEngine()
        
        self._load()
    
    def _load(self):
        """Load memories from storage."""
        if self.storage_file.exists():
            try:
                data = json.loads(self.storage_file.read_text())
                
                for mem_data in data.get("memories", []):
                    item = MemoryItem.from_dict(mem_data)
                    self._memories[item.id] = item
                    
                    for tag in item.tags:
                        self._tags[tag].add(item.id)
                        
            except (json.JSONDecodeError, IOError, KeyError):
                self._memories = {}
                self._tags = defaultdict(set)
    
    def _save(self):
        """Persist memories to storage."""
        data = {
            "memories": [
                item.to_dict() for item in self._memories.values()
            ]
        }
        
        try:
            self.storage_file.write_text(json.dumps(data, indent=2))
        except IOError:
            pass
    
    # ── Memory Operations ─────────────────────────────────────────────────────
    
    def add_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.TRIVIAL,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        source: str = "system",
        is_permanent: bool = False
    ) -> str:
        """Add a new memory."""
        import hashlib
        
        memory_id = hashlib.md5(content.encode()).hexdigest()[:16]
        
        item = MemoryItem(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags or [],
            source=source,
            is_permanent=is_permanent or memory_type == MemoryType.IMPORTANT,
        )
        
        # Set initial review based on importance
        if item.is_permanent:
            item.interval = 365  # Review yearly
            item.next_review = time.time() + 365 * 86400
        
        self._memories[memory_id] = item
        
        for tag in item.tags:
            self._tags[tag].add(memory_id)
        
        self._save()
        return memory_id
    
    def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        memory_type: Optional[MemoryType] = None
    ) -> bool:
        """Update a memory item."""
        if memory_id not in self._memories:
            return False
        
        item = self._memories[memory_id]
        
        if content:
            item.content = content
        if tags:
            # Update tag index
            for tag in item.tags:
                self._tags[tag].discard(memory_id)
            item.tags = tags
            for tag in tags:
                self._tags[tag].add(memory_id)
        if memory_type:
            item.memory_type = memory_type
            
            # Auto-lock important memories
            if memory_type == MemoryType.IMPORTANT:
                item.is_permanent = True
                item.is_locked = True
        
        item.updated_at = time.time()
        self._save()
        return True
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory."""
        if memory_id not in self._memories:
            return False
        
        item = self._memories[memory_id]
        
        for tag in item.tags:
            self._tags[tag].discard(memory_id)
        
        del self._memories[memory_id]
        self._save()
        return True
    
    # ── User Corrections ─────────────────────────────────────────────────────
    
    def record_correction(
        self,
        memory_id: str,
        corrected_content: str
    ) -> bool:
        """
        Record a user correction - permanently stores the correction.
        """
        if memory_id not in self._memories:
            return False
        
        item = self._memories[memory_id]
        
        # Apply correction
        item.content = corrected_content
        item.correction_count += 1
        item.importance = min(1.0, item.importance + 0.2)  # Boost importance
        
        # Make permanently important
        item.is_permanent = True
        item.is_locked = True
        item.memory_type = MemoryType.IMPORTANT
        
        # Extend review interval (user knows this)
        item.interval = min(365, item.interval * 2)
        
        item.updated_at = time.time()
        self._save()
        
        return True
    
    # ── Spaced Repetition ───────────────────────────────────────────────────
    
    def review_memory(
        self,
        memory_id: str,
        quality: int  # 0-5 rating
    ) -> Optional[Dict[str, Any]]:
        """
        Review a memory item and update its schedule.
        """
        if memory_id not in self._memories:
            return None
        
        item = self._memories[memory_id]
        
        old_interval = item.interval
        new_interval, new_ease, new_reps = self._sr_engine.calculate_next_review(
            quality, item
        )
        
        item.interval = new_interval
        item.ease_factor = new_ease
        item.repetitions = new_reps
        item.last_review = time.time()
        item.next_review = time.time() + new_interval * 86400
        
        item.updated_at = time.time()
        self._save()
        
        return {
            "memory_id": memory_id,
            "old_interval": old_interval,
            "new_interval": new_interval,
            "next_review_days": new_interval,
            "retention_score": self._sr_engine.get_retention_score(item),
        }
    
    # ── Retrieval ───────────────────────────────────────────────────────────
    
    def get_due_memories(self, limit: int = 20) -> List[MemoryItem]:
        """Get memories due for review."""
        now = time.time()
        
        due = [
            item for item in self._memories.values()
            if item.next_review <= now and not item.is_locked
        ]
        
        # Sort by importance and due date
        due.sort(key=lambda x: (x.importance, x.next_review))
        
        return due[:limit]
    
    def get_permanent_memories(self) -> List[MemoryItem]:
        """Get all permanent (locked) memories."""
        return [
            item for item in self._memories.values()
            if item.is_permanent
        ]
    
    def get_memories_by_tag(self, tag: str) -> List[MemoryItem]:
        """Get all memories with a specific tag."""
        memory_ids = self._tags.get(tag, set())
        return [
            self._memories[mid] for mid in memory_ids
            if mid in self._memories
        ]
    
    def get_memories_by_type(self, memory_type: MemoryType) -> List[MemoryItem]:
        """Get all memories of a specific type."""
        return [
            item for item in self._memories.values()
            if item.memory_type == memory_type
        ]
    
    def search_memories(
        self,
        query: str,
        limit: int = 10
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Search memories by content similarity.
        """
        query_lower = query.lower()
        results = []
        
        for item in self._memories.values():
            # Simple keyword matching with scoring
            content_lower = item.content.lower()
            
            if query_lower in content_lower:
                # Direct match
                score = item.importance * (1 + item.access_count * 0.1)
                results.append((item, score))
            else:
                # Partial match
                words = query_lower.split()
                matches = sum(1 for w in words if w in content_lower)
                if matches > 0:
                    score = (matches / len(words)) * item.importance
                    results.append((item, score))
        
        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        
        return [(item, score) for item, score in results[:limit]]
    
    # ── Cleanup ─────────────────────────────────────────────────────────────
    
    def cleanup_faded_memories(self, max_age_days: int = 30) -> int:
        """
        Remove trivial memories that haven't been accessed and are past their decay.
        Locked and permanent memories are protected.
        """
        cutoff = time.time() - (max_age_days * 86400)
        removed = 0
        
        to_remove = []
        
        for item in self._memories.values():
            if item.is_locked or item.is_permanent:
                continue
            
            if item.memory_type == MemoryType.TRIVIAL:
                retention = self._sr_engine.get_retention_score(item)
                
                # Remove if very low retention and old
                if retention < 0.1 and item.last_review < cutoff:
                    to_remove.append(item.id)
        
        for memory_id in to_remove:
            self.delete_memory(memory_id)
            removed += 1
        
        return removed
    
    def compress_memories(self, max_items: int = 1000) -> int:
        """
        Compress memories by summarizing old ones when limit is reached.
        """
        if len(self._memories) <= max_items:
            return 0
        
        # Get non-permanent memories sorted by importance
        compressible = [
            item for item in self._memories.values()
            if not item.is_permanent and not item.is_locked
        ]
        compressible.sort(key=lambda x: (x.importance, x.last_review))
        
        # Compress oldest/least important
        removed = 0
        while len(self._memories) > max_items and compressible:
            item = compressible.pop(0)
            
            # Summarize content
            item.content = self._summarize(item.content)
            item.importance *= 0.8  # Reduce importance
            removed += 1
        
        if removed > 0:
            self._save()
        
        return removed
    
    def _summarize(self, content: str, max_length: int = 200) -> str:
        """Simple summarization."""
        if len(content) <= max_length:
            return content
        
        # Take first part
        summary = content[:max_length]
        
        # Try to end at a sentence boundary
        last_period = summary.rfind('.')
        if last_period > max_length * 0.7:
            summary = summary[:last_period + 1]
        
        return summary + " [summarized]"
    
    # ── Statistics ───────────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        memories = list(self._memories.values())
        
        return {
            "total_memories": len(memories),
            "permanent_memories": sum(1 for m in memories if m.is_permanent),
            "locked_memories": sum(1 for m in memories if m.is_locked),
            "due_for_review": len(self.get_due_memories(limit=1000)),
            "by_type": {
                mt.value: sum(1 for m in memories if m.memory_type == mt)
                for mt in MemoryType
            },
            "average_importance": sum(m.importance for m in memories) / len(memories) if memories else 0,
            "total_corrections": sum(m.correction_count for m in memories),
            "retention_stats": {
                "high": sum(1 for m in memories if self._sr_engine.get_retention_score(m) > 0.8),
                "medium": sum(1 for m in memories if 0.3 < self._sr_engine.get_retention_score(m) <= 0.8),
                "low": sum(1 for m in memories if self._sr_engine.get_retention_score(m) <= 0.3),
            }
        }
    
    def export_memories(self) -> Dict[str, Any]:
        """Export all memories."""
        return {
            "exported_at": time.time(),
            "stats": self.get_stats(),
            "memories": [item.to_dict() for item in self._memories.values()],
        }
    
    def import_memories(self, data: Dict[str, Any]) -> int:
        """Import memories from export."""
        imported = 0
        
        for mem_data in data.get("memories", []):
            item = MemoryItem.from_dict(mem_data)
            
            # Skip if already exists
            if item.id not in self._memories:
                self._memories[item.id] = item
                
                for tag in item.tags:
                    self._tags[tag].add(item.id)
                
                imported += 1
        
        if imported > 0:
            self._save()
        
        return imported


# ── Global instance ───────────────────────────────────────────────────────────

forgetting_curve = ForgettingCurveManager()
