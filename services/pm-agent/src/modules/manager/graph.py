from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.modules.manager.state import AgentState, Plan

from src.shared.config import config

# Initialize Model (OpenAI or DeepSeek)
llm = ChatOpenAI(
    api_key=config.OPENAI_API_KEY, 
    base_url=config.OPENAI_BASE_URL,
    model=config.MODEL_NAME,
    temperature=0
)

# Planner Prompts
planner_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Project Manager (PM) of the 'Woorung-Gaksi' system, a multi-agent AI factory.
Your goal is to analyze the user's request and create a detailed execution plan.

Available Sub-Agents:
1. RESEARCH: Search the web, analyze data, summarize trends.
2. CODING: Write code, debug, refactor, generate software.
3. MEDIA: Create images, edit videos, generate shorts.
4. REVIEW: Review the final output or answer simple questions directly.

Instructions:
- Break down the request into sequential tasks.
- Assign each task to the most appropriate agent.
- Keep descriptions clear and actionable.
- If the request is simple (e.g., "Hello"), assign it to REVIEW agent to answer directly.
"""),
    ("user", "{input}")
])

# Create Structured Planner
planner = planner_prompt | llm.with_structured_output(Plan)

def planner_node(state: AgentState):
    """
    Analyzes the user request and generates a structured Plan.
    """
    messages = state['messages']
    last_message = messages[-1].content
    
    # Generate Plan using LLM
    try:
        plan = planner.invoke({"input": last_message})
        
        # Format the plan into a readable response for now (Mock Execution)
        plan_text = f"**Plan Generated:**\nGoal: {plan.final_goal}\n"
        for task in plan.tasks:
            plan_text += f"- [{task.agent}] {task.name}: {task.description}\n"
            
        return {
            "plan": plan, 
            "final_response": plan_text,
            "current_task_index": 0
        }
    except Exception as e:
        return {"final_response": f"Planning Failed: {str(e)}"}

# Define Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("planner", planner_node)

# Set Entry Point
workflow.set_entry_point("planner")

# Add Edges
workflow.add_edge("planner", END)

# Compile
app = workflow.compile()
