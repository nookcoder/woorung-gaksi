from fastapi import FastAPI
from contextlib import asynccontextmanager
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
import uuid
import uvicorn

# Imports from project
from src.modules.manager.state import AgentState
from src.modules.manager.graph import agent_workflow
from src.infrastructure.database import get_postgres_checkpointer

# Global variable for the compiled agent application
agent_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to handle database connection and agent compilation.
    Checks and creates tables on startup.
    """
    print("Starting up PM Agent with PostgreSQL Persistence...")
    async with get_postgres_checkpointer() as checkpointer:
        global agent_app
        # Compile workflow with the initialized async (Postgres) checkpointer
        agent_app = agent_workflow.compile(checkpointer=checkpointer)
        print("PM Agent compiled successfully.")
        yield
    print("Shutting down PM Agent...")

app = FastAPI(title="PM Agent", description="The Brain of Woorung-Gaksi", lifespan=lifespan)

class HealthResponse(BaseModel):
    status: str
    service: str

class AskRequest(BaseModel):
    message: str
    user_id: str | None = None
    thread_id: str | None = None  # Persistence Key

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "ok",
        "service": "PM Agent (Python)"
    }

@app.post("/ask")
async def ask_agent(req: AskRequest):
    global agent_app
    print(f"Received from {req.user_id} (Thread: {req.thread_id}): {req.message}")
    
    if agent_app is None:
        return {"reply": "Error: Agent not initialized properly (DB issue?).", "thread_id": req.thread_id}

    # Determine Thread ID (Use provided or generate new for session)
    thread_id = req.thread_id or str(uuid.uuid4())
    
    # Create Config for Persistence
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Attempt to load existing state using async method
        current_state = await agent_app.aget_state(config)
        
        # Define Input State
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
        
        # Run the Graph asynchronously
        # Use ainvoke for async execution
        result = await agent_app.ainvoke(input_state, config=config)
        final_response = result.get("final_response", "No response generated.")
        
        return {
            "reply": final_response,
            "thread_id": thread_id  # Return thread_id so client can continue conversation
        }
    except Exception as e:
        print(f"Error running agent: {e}")
        # import traceback
        # traceback.print_exc()
        return {"reply": f"Error: {str(e)}. (Check logs)", "thread_id": thread_id}

@app.get("/")
async def root():
    return {"message": "Hello from PM Agent (PostgreSQL Backed)"}

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
