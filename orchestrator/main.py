"""
المنسق الرئيسي - واجهة API فقط
خفيف، لا يراقب، لا يشفي، لا يحفظ حالة
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

from orchestrator.dispatcher import Dispatcher


# ============================================================
# التطبيق
# ============================================================
app = FastAPI(
    title="AI Engineering OS",
    description="نظام تشغيل هجين للهندسة البرمجية بالذكاء الاصطناعي",
    version="1.0.0"
)

# الموزع - النخاع الشوكي
dispatcher = Dispatcher()


# ============================================================
# نماذج البيانات
# ============================================================
class WorkflowRequest(BaseModel):
    requirements: str
    stack: Optional[str] = None
    features: Optional[List[str]] = None


class TaskRequest(BaseModel):
    type: str
    payload: dict


# ============================================================
# نقاط API
# ============================================================

@app.get("/health")
async def health_check():
    """
    فحص صحة النظام
    """
    return {
        "status": "healthy",
        "service": "orchestrator",
        "active_workflows": len(dispatcher.active_workflows)
    }


@app.get("/")
async def root():
    """
    الصفحة الرئيسية
    """
    return {
        "name": "AI Engineering OS",
        "version": "1.0.0",
        "agents": ["openhands", "aider", "bolt", "replit"],
        "workflows": list(dispatcher.workflow_policy.get("workflows", {}).keys()),
        "endpoints": [
            "POST /workflows/full-app-generation",
            "POST /workflows/refactoring",
            "POST /workflows/bug-fixing",
            "POST /workflows/prototyping",
            "GET /workflows/{id}/status",
            "GET /workflows",
            "GET /health"
        ]
    }


# ============================================================
# سير العمل
# ============================================================

@app.post("/workflows/{workflow_type}")
async def execute_workflow(workflow_type: str, request: WorkflowRequest):
    """
    تنفيذ سير عمل
    """
    # التحقق من صحة نوع سير العمل
    valid_workflows = dispatcher.workflow_policy.get("workflows", {})
    if workflow_type not in valid_workflows:
        raise HTTPException(
            status_code=404,
            detail=f"سير العمل غير معروف. المتاح: {list(valid_workflows.keys())}"
        )
    
    # توزيع المهمة
    result = await dispatcher.dispatch_workflow(
        workflow_type,
        request.model_dump()
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.get("/workflows/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """
    حالة سير عمل
    """
    status = await dispatcher.get_workflow_status(workflow_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="سير العمل غير موجود")
    
    return status


@app.get("/workflows")
async def list_workflows():
    """
    جميع سير العمل النشطة
    """
    return {
        "active_workflows": dispatcher.get_all_workflows(),
        "total": len(dispatcher.active_workflows)
    }


# ============================================================
# توجيه المهام
# ============================================================

@app.post("/tasks/route")
async def route_task(request: TaskRequest):
    """
    تحديد الوكيل المناسب لمهمة
    """
    agent = await dispatcher.route_task(request.type)
    
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"لا يوجد وكيل لنوع المهمة: {request.type}"
        )
    
    return {
        "task_type": request.type,
        "assigned_agent": agent,
        "fallback": await dispatcher.get_fallback(agent)
    }


# ============================================================
# التشغيل
# ============================================================

if __name__ == "__main__":
    print("""
    🧠 AI Engineering OS
    ├── المنسق: جاهز (FastAPI)
    ├── الموزع: نشط (Dispatcher)
    ├── الوكلاء: OpenHands, Aider, Bolt, Replit
    └── المنفذ: 8080
    """)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
