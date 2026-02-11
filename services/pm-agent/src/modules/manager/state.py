from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
import operator

class Task(BaseModel):
    id: int = Field(description="Task ID (1, 2, 3...)")
    name: str = Field(description="Task Name")
    agent: str = Field(description="Responsible Agent (RESEARCH, CODING, MEDIA, REVIEW)")
    description: str = Field(description="Detailed description of what to do")
    status: str = Field(default="TODO", description="TODO, IN_PROGRESS, DONE")

class Plan(BaseModel):
    tasks: List[Task] = Field(description="List of tasks to execute")
    final_goal: str = Field(description="The ultimate goal of this plan")

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_id: str
    plan: Optional[Plan]
    current_task_index: int
    final_response: str | None
