"""
memory/context_window_manager.py - Context Window Manager v7.0
Smart context allocation, never exceed limits, prioritize relevant context.
"""

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ── Context Limits ─────────────────────────────────────────────────────────────

class ContextLimit(Enum):
    GPT4_TURBO = 128000
    GPT4 = 8192
    GPT35_TURBO = 16385
    CLAUDE_3_OPUS = 200000
    CLAUDE_3_SONNET = 200000
    CLAUDE_3_HAiku = 200000
    GEMINI_PRO = 32000
    LOCAL_LLAMA = 4096


# ── Context Priority ───────────────────────────────────────────────────────────

class ContextPriority(Enum):
    CRITICAL = 4  # System instructions, critical requirements
    HIGH = 3      # Relevant files, current task
    MEDIUM = 2    # Recent context, patterns
    LOW = 1       # Historical info, general knowledge
    IGNORED = 0   # Can be dropped


@dataclass
class ContextItem:
    """Represents an item in context."""
    id: str
    content: str
    priority: ContextPriority
    source: str  # "file", "memory", "agent", "system"
    tokens: int
    relevance_score: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    
    def access(self):
        """Record access to this context item."""
        self.last_accessed = time.time()
        self.access_count += 1


# ── Context Trimmer ───────────────────────────────────────────────────────────

class ContextTrimmer:
    """Trim context to fit within limits."""
    
    def __init__(self):
        self._trim_strategies: List[Callable] = [
            self._drop_low_priority,
            self._compress_less_used,
            self._drop_old_items,
            self._summarize_long_items,
        ]
    
    def trim(
        self,
        items: List[ContextItem],
        target_tokens: int
    ) -> List[ContextItem]:
        """Trim items to fit target token budget."""
        if sum(i.tokens for i in items) <= target_tokens:
            return items
        
        result = list(items)
        
        for strategy in self._trim_strategies:
            if sum(i.tokens for i in result) <= target_tokens:
                break
            result = strategy(result, target_tokens)
        
        return result
    
    def _drop_low_priority(
        self,
        items: List[ContextItem],
        target: int
    ) -> List[ContextItem]:
        """Drop lowest priority items first."""
        sorted_items = sorted(items, key=lambda x: (x.priority.value, -x.access_count))
        
        result = []
        total = 0
        
        for item in sorted_items:
            if total + item.tokens <= target or item.priority == ContextPriority.CRITICAL:
                result.append(item)
                total += item.tokens
        
        return result
    
    def _compress_less_used(
        self,
        items: List[ContextItem],
        target: int
    ) -> List[ContextItem]:
        """Compress or drop less frequently accessed items."""
        sorted_items = sorted(items, key=lambda x: (x.access_count, -x.tokens))
        
        result = []
        total = 0
        
        for item in sorted_items:
            if total + (item.tokens // 2) <= target or item.priority == ContextPriority.CRITICAL:
                # Compress by summarizing
                item.content = self._summarize(item.content)
                item.tokens = item.tokens // 2
                result.append(item)
                total += item.tokens
            elif total + item.tokens <= target:
                result.append(item)
                total += item.tokens
        
        return result
    
    def _drop_old_items(
        self,
        items: List[ContextItem],
        target: int
    ) -> List[ContextItem]:
        """Drop oldest items if needed."""
        sorted_items = sorted(
            items,
            key=lambda x: (x.priority.value, x.last_accessed)
        )
        
        result = []
        total = 0
        
        for item in sorted_items:
            if total + item.tokens <= target or item.priority == ContextPriority.CRITICAL:
                result.append(item)
                total += item.tokens
        
        return result
    
    def _summarize_long_items(
        self,
        items: List[ContextItem],
        target: int
    ) -> List[ContextItem]:
        """Summarize long items to fit budget."""
        result = []
        total = 0
        
        for item in sorted(items, key=lambda x: -x.tokens):
            if total + item.tokens <= target:
                result.append(item)
                total += item.tokens
            elif item.tokens > 500 and item.priority != ContextPriority.CRITICAL:
                # Summarize long items
                item.content = self._summarize(item.content, max_length=item.tokens // 2)
                if total + item.tokens <= target:
                    result.append(item)
                    total += item.tokens
        
        return result
    
    def _summarize(self, text: str, max_length: int = 500) -> str:
        """Simple summarization by keeping first and last sentences."""
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        
        if len(sentences) <= 3:
            return text[:max_length]
        
        first = sentences[0]
        last = sentences[-1]
        
        if len(first) + len(last) > max_length:
            return (first + last)[:max_length]
        
        return f"{first}. ... {last}."


# ── Context Window Manager ─────────────────────────────────────────────────────

class ContextWindowManager:
    """
    Smart context window allocation that never exceeds model limits.
    """
    
    def __init__(
        self,
        model: str = "gpt-4-turbo",
        max_tokens: int = 128000,
        reserved_tokens: int = 2000  # Reserve for response
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.reserved_tokens = reserved_tokens
        self.available_tokens = max_tokens - reserved_tokens
        
        self._context: Dict[str, ContextItem] = {}
        self._sources: Set[str] = set()
        self._trimmer = ContextTrimmer()
        
        # Priority weights for automatic prioritization
        self._priority_weights = {
            ContextPriority.CRITICAL: 1.0,
            ContextPriority.HIGH: 0.8,
            ContextPriority.MEDIUM: 0.5,
            ContextPriority.LOW: 0.2,
            ContextPriority.IGNORED: 0.0,
        }
    
    def add_context(
        self,
        content: str,
        source: str,
        priority: ContextPriority = ContextPriority.MEDIUM,
        token_estimate: Optional[int] = None,
        id: Optional[str] = None
    ) -> str:
        """Add context to the window."""
        import hashlib
        
        context_id = id or hashlib.md5(f"{source}:{content[:100]}".encode()).hexdigest()[:16]
        
        tokens = token_estimate or self._estimate_tokens(content)
        
        item = ContextItem(
            id=context_id,
            content=content,
            priority=priority,
            source=source,
            tokens=tokens
        )
        
        self._context[context_id] = item
        self._sources.add(source)
        
        return context_id
    
    def remove_context(self, context_id: str) -> bool:
        """Remove context from the window."""
        if context_id in self._context:
            del self._context[context_id]
            return True
        return False
    
    def update_priority(
        self,
        context_id: str,
        priority: ContextPriority
    ) -> bool:
        """Update the priority of a context item."""
        if context_id in self._context:
            self._context[context_id].priority = priority
            return True
        return False
    
    def get_context(self, context_id: str) -> Optional[ContextItem]:
        """Get a specific context item."""
        item = self._context.get(context_id)
        if item:
            item.access()
        return item
    
    def get_all_context(self) -> List[ContextItem]:
        """Get all context items sorted by priority."""
        return sorted(
            self._context.values(),
            key=lambda x: (
                x.priority.value,
                -x.access_count,
                -x.relevance_score
            ),
            reverse=True
        )
    
    def get_compiled_context(
        self,
        additional_content: Optional[str] = None,
        system_message: Optional[str] = None
    ) -> Tuple[List[ContextItem], str]:
        """
        Get compiled context that fits within token limit.
        
        Returns: (items_included, full_context_string)
        """
        items = self.get_all_context()
        
        # Add additional content if provided
        if additional_content:
            tokens = self._estimate_tokens(additional_content)
            additional_item = ContextItem(
                id="additional",
                content=additional_content,
                priority=ContextPriority.HIGH,
                source="request",
                tokens=tokens
            )
            items.insert(0, additional_item)
        
        # Trim to fit budget
        trimmed = self._trimmer.trim(items, self.available_tokens)
        
        # Compile to string
        context_parts = []
        for item in trimmed:
            prefix = f"[{item.source.upper()}]"
            context_parts.append(f"{prefix}\n{item.content}")
        
        full_context = "\n\n".join(context_parts)
        
        # Add system message prefix if provided
        if system_message:
            full_context = f"{system_message}\n\n{full_context}"
        
        return trimmed, full_context
    
    def fit_within_limit(
        self,
        new_content: str,
        priority: ContextPriority = ContextPriority.MEDIUM
    ) -> bool:
        """Check if new content can fit within the context window."""
        current_tokens = sum(i.tokens for i in self._context.values())
        new_tokens = self._estimate_tokens(new_content)
        
        return current_tokens + new_tokens <= self.available_tokens
    
    def auto_trim(self):
        """Automatically trim context to fit."""
        current_tokens = sum(i.tokens for i in self._context.values())
        
        if current_tokens > self.available_tokens:
            items = self.get_all_context()
            trimmed = self._trimmer.trim(items, self.available_tokens)
            
            # Remove items not in trimmed list
            trimmed_ids = {i.id for i in trimmed}
            for item_id in list(self._context.keys()):
                if item_id not in trimmed_ids:
                    del self._context[item_id]
    
    def clear(self, source: Optional[str] = None):
        """Clear context, optionally only for a specific source."""
        if source:
            to_remove = [
                i for i in self._context.values()
                if i.source == source
            ]
            for item in to_remove:
                del self._context[item.id]
        else:
            self._context.clear()
            self._sources.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        items = list(self._context.values())
        
        return {
            "total_items": len(items),
            "total_tokens": sum(i.tokens for i in items),
            "available_tokens": self.available_tokens,
            "usage_percent": round(
                sum(i.tokens for i in items) / self.available_tokens * 100,
                1
            ),
            "by_source": {
                source: sum(
                    i.tokens for i in items if i.source == source
                )
                for source in self._sources
            },
            "by_priority": {
                p.name: sum(
                    i.tokens for i in items if i.priority == p
                )
                for p in ContextPriority
            },
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation)."""
        # Rough estimate: ~4 chars per token for English
        return len(text) // 4
    
    def export_context(self) -> Dict[str, Any]:
        """Export context for persistence."""
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "context": [
                {
                    "id": i.id,
                    "content": i.content,
                    "priority": i.priority.name,
                    "source": i.source,
                    "tokens": i.tokens,
                    "created_at": i.created_at,
                }
                for i in self._context.values()
            ],
        }
    
    def import_context(self, data: Dict[str, Any]):
        """Import context from persistence."""
        self._context.clear()
        
        for item_data in data.get("context", []):
            priority = ContextPriority[item_data["priority"]]
            item = ContextItem(
                id=item_data["id"],
                content=item_data["content"],
                priority=priority,
                source=item_data["source"],
                tokens=item_data["tokens"],
                created_at=item_data.get("created_at", time.time())
            )
            self._context[item.id] = item
            self._sources.add(item.source)


# ── Global instance ───────────────────────────────────────────────────────────

context_manager = ContextWindowManager()
