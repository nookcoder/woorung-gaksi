from fastapi import FastAPI
from pydantic import BaseModel
from src.modules.manager.state import AgentState
import uuid

app = FastAPI(title="PM Agent", description="The Brain of Woorung-Gaksi")

class HealthResponse(BaseModel):
    status: str
    service: str

class AskRequest(BaseModel):
    message: str
    user_id: str | None = None
    thread_id: str | None = None  # Added for Persistence

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
    print(f"Received from {req.user_id} (Thread: {req.thread_id}): {req.message}")
    
    # Determine Thread ID (Use provided or generate new for session)
    thread_id = req.thread_id or str(uuid.uuid4())
    
    # Create Config for Persistence
    config = {"configurable": {"thread_id": thread_id}}
    
    # Attempt to load existing state
    current_state = agent_app.get_state(config)
    
    # Define Input State
    # If state exists, we append the new message. If not, we initialize.
    if current_state.values:
        # Continuing conversation
        input_state = {
            "messages": [HumanMessage(content=req.message)]
        }
    else:
        # New conversation
        input_state = {
            "messages": [HumanMessage(content=req.message)],
            "user_id": req.user_id or "anonymous",
            "current_task_index": 0,
            "plan": None,
            "final_response": None
        }
    
    # Run the Graph
    try:
        # Pass config to invoke to enable checkpointing
        result = agent_app.invoke(input_state, config=config)
        final_response = result.get("final_response", "No response generated.")
        
        return {
            "reply": final_response,
            "thread_id": thread_id  # Return thread_id so client can continue conversation
        }
    except Exception as e:
        print(f"Error running agent: {e}")
        return {"reply": f"Error: {str(e)}. (Check logs)", "thread_id": thread_id}

@app.get("/")
async def root():
    return {"message": "Hello from PM Agent"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
