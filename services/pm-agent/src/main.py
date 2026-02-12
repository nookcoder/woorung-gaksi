from fastapi import FastAPI
from pydantic import BaseModel
from src.modules.manager.state import AgentState

app = FastAPI(title="PM Agent", description="The Brain of Woorung-Gaksi")

class HealthResponse(BaseModel):
    status: str
    service: str

class AskRequest(BaseModel):
    message: str
    user_id: str | None = None

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "ok",
        "service": "PM Agent (Python)"
    }

from langchain_core.messages import HumanMessage
from src.modules.manager.graph import app as agent_app

@app.post("/ask")
async def ask_agent(req: AskRequest):
    print(f"Received from {req.user_id}: {req.message}")
    
    # Create Initial State
    initial_state: AgentState = {
        "messages": [HumanMessage(content=req.message)],
        "user_id": req.user_id or "anonymous",
        "current_task_index": 0,
        "plan": None,
        "final_response": None
    }
    
    # Run the Graph
    try:
        result = agent_app.invoke(initial_state)
        final_response = result.get("final_response", "No response generated.")
        return {"reply": final_response}
    except Exception as e:
        print(f"Error running agent: {e}")
        return {"reply": f"Error: {str(e)}. (Check your API Key in services/pm-agent/.env)"}

@app.get("/")
async def root():
    return {"message": "Hello from PM Agent"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
