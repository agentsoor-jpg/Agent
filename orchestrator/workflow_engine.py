"""Simple workflow engine that runs tasks sequentially using Router and PubSub."""
from loguru import logger
from planning.dependency_resolver import resolve_dependencies, check_completeness


class WorkflowEngine:
    def __init__(self, router=None, pubsub=None):
        self.router = router
        self.pubsub = pubsub

    def run_workflow(self, workflow: dict):
        tasks = workflow.get("tasks", [])
        if not tasks:
            # No tasks defined — create a default task from the prompt
            prompt = workflow.get("prompt", workflow.get("goal", ""))
            if prompt:
                tasks = [{
                    "id": "t1",
                    "agent": "openhands",
                    "agent_id": "openhands",
                    "action": "execute",
                    "input": {"prompt": prompt},
                    "dependencies": [],
                }]

        dep_result = resolve_dependencies(tasks)
        ordered = dep_result.get("order", [])
        results = {}

        for task_id in ordered:
            task = next((t for t in tasks if t["id"] == task_id), None)
            if task is None:
                continue
            agent = task.get("agent") or task.get("agent_id")
            payload = task.get("input", task.get("payload", {}))
            logger.info(f"Dispatching task {task.get('id')} to agent {agent}")

            if self.pubsub:
                topic = f"agent:{agent}:in"
                self.pubsub.publish(topic, payload if isinstance(payload, str) else str(payload))
                results[task.get("id")] = {"status": "published"}
            else:
                results[task.get("id")] = {"status": "no_pubsub"}

        ok = check_completeness(tasks)
        return {
            "results": results,
            "complete": ok.get("complete", False),
            "has_cycle": dep_result.get("has_cycle", False),
            "order": ordered,
        }
