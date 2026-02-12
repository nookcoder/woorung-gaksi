from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.modules.manager.state import AgentState, Plan, Task
from typing import Literal
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

from src.shared.config import config
from pydantic import SecretStr

# Import Tools
from src.tools.web_search import web_search
from src.tools.code_gen import code_gen
from src.tools.file_ops import read_file, write_file, list_dir

# Initialize Model (OpenAI or DeepSeek)
api_key = SecretStr(config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None

llm = ChatOpenAI(
    api_key=api_key, 
    base_url=config.OPENAI_BASE_URL,
    model=config.MODEL_NAME,
    temperature=0
)

# Set up Parser
parser = PydanticOutputParser(pydantic_object=Plan)

# Planner Prompts
planner_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Project Manager (PM) of the 'Woorung-Gaksi' system, a multi-agent AI factory.
Your goal is to analyze the user's request and create a detailed execution plan.

Available Sub-Agents:
1. RESEARCH: Search the web, analyze data, summarize trends.
2. CODING: Read, Write, and Edit files in the project directory. Use this agent for ANY file modification or code generation task.
3. MEDIA: Create images, edit videos, generate shorts.
4. REVIEW: Review the final output or answer simple questions directly.

Instructions:
- Break down the request into sequential tasks.
- Assign each task to the most appropriate agent.
- Keep descriptions clear and actionable.
- If the request is simple (e.g., "Hello"), assign it to REVIEW agent to answer directly.

RESPONSE FORMAT:
{format_instructions}
"""),
    ("user", "{input}")
])

# Create Chain: Prompt -> LLM -> Parser
planner = planner_prompt | llm | parser

def planner_node(state: AgentState):
    """
    Analyzes the user request and generates a structured Plan.
    """
    messages = state['messages']
    last_message = messages[-1].content
    
    # Generate Plan using LLM
    try:
        plan = planner.invoke({
            "input": last_message,
            "format_instructions": parser.get_format_instructions()
        })
        
        # Format the plan into a readable response for now
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

# --- Router & Agents ---

def router_node(state: AgentState) -> Literal["research", "coding", "media", "review", "__end__"]:
    plan = state.get('plan')
    idx = state.get('current_task_index', 0)
    
    # If no plan or all tasks done, end
    if not plan or idx >= len(plan.tasks):
        return "__end__"
        
    task = plan.tasks[idx]
    agent = task.agent.upper()
    
    if agent == "RESEARCH": return "research"
    if agent == "CODING": return "coding"
    if agent == "MEDIA": return "media"
    return "review"

def research_node(state: AgentState):
    plan = state.get('plan')
    idx = state.get('current_task_index', 0)
    if not plan:
        return {"final_response": "Error: Plan missing."}
        
    task = plan.tasks[idx]
    
    # 1. Generate Search Query from Task Description
    try:
        query_prompt = ChatPromptTemplate.from_messages([
            ("system", "Generate a concise search query for the following task. Output ONLY the query as plain text."),
            ("user", f"Task: {task.name}\nDescription: {task.description}")
        ])
        query_chain = query_prompt | llm
        query_res = query_chain.invoke({})
        search_query = query_res.content.strip().replace('"', '')
        
        # 2. Execute Search Tool
        search_result = web_search.invoke({"query": search_query})
        
        result = f"\n\n[RESEARCH] Task {task.id}: {task.name}\n> Query: {search_query}\n> Result:\n{search_result}"
    except Exception as e:
        result = f"\n\n[RESEARCH] Task {task.id} Failed: {str(e)}"
    
    return {
        "final_response": (state.get("final_response") or "") + result,
        "current_task_index": idx + 1
    }

def coding_node(state: AgentState):
    """
    Executes coding tasks using File Ops tools.
    Supports tool calling loop (ReAct pattern).
    """
    plan = state.get('plan')
    idx = state.get('current_task_index', 0)
    if not plan:
        return {"final_response": "Error: Plan missing."}
    
    task = plan.tasks[idx]
    
    # Bind coding tools
    coding_tools = [read_file, write_file, list_dir, code_gen]
    llm_with_tools = llm.bind_tools(coding_tools)
    
    tool_map = {t.name: t for t in coding_tools}
    
    # Initial Prompt
    prompt = f"""Task: {task.name}
Description: {task.description}

You are an expert Software Engineer. You assume the project root is the base directory.
Use the providing tools to read files, list directories, and write code.
Usually, you should:
1. List files to understand structure (if needed).
2. Read relevant files.
3. Write or Modify code using 'write_file'.

Execute the task now.
"""
    messages = [HumanMessage(content=prompt)]
    history_log = ""
    
    # Limited Tool Loop (Prevent infinite)
    MAX_STEPS = 5
    for step in range(MAX_STEPS):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        
        if not response.tool_calls:
            # Done
            history_log += f"\n> {response.content}"
            break
            
        # Execute Tool Calls
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            history_log += f"\n> Tool Call: {tool_name}({tool_args})"
            
            if tool_name in tool_map:
                try:
                    tool_output = tool_map[tool_name].invoke(tool_args)
                except Exception as e:
                    tool_output = f"Error: {str(e)}"
            else:
                tool_output = "Error: Tool not found."
                
            history_log += f"\n  Result: {str(tool_output)[:200]}..." # Truncate log for display
            
            messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_id))

    result = f"\n\n[CODING] Task {task.id}: {task.name}\nExecution Log:\n{history_log}"
    
    return {
        "final_response": (state.get("final_response") or "") + result,
        "current_task_index": idx + 1
    }

def media_node(state: AgentState):
    plan = state.get('plan')
    idx = state.get('current_task_index', 0)
    if not plan:
        return {"final_response": "Error: Plan missing."}
        
    task = plan.tasks[idx]
    # Mock for now (Skipped by user request)
    result = f"\n\n[MEDIA] Task {task.id}: {task.name}\n> Skipped (Mock)."
    return {
        "final_response": (state.get("final_response") or "") + result,
        "current_task_index": idx + 1
    }

def review_node(state: AgentState):
    plan = state.get('plan')
    idx = state.get('current_task_index', 0)
    if not plan:
        return {"final_response": "Error: Plan missing."}
        
    task = plan.tasks[idx]
    
    accumulated_response = state.get("final_response", "")
    
    try:
        review_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Reviewer. Summarize the work done so far and answer the user's original request based on the results."),
            ("user", "Here is the execution log:\n{log}\n\nPlease provide a final summary answer.")
        ])
        review_chain = review_prompt | llm
        review_res = review_chain.invoke({"log": accumulated_response})
        review_text = review_res.content
        
        result = f"\n\n[REVIEW] Task {task.id}: {task.name}\n> Summary:\n{review_text}"
    except Exception as e:
        result = f"\n\n[REVIEW] Task {task.id} Failed: {str(e)}"
    
    return {
        "final_response": accumulated_response + result,
        "current_task_index": idx + 1
    }

# Define Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("planner", planner_node)
workflow.add_node("research", research_node)
workflow.add_node("coding", coding_node)
workflow.add_node("media", media_node)
workflow.add_node("review", review_node)

# Set Entry Point
workflow.set_entry_point("planner")

# Add Edges
# Planner -> Router
workflow.add_conditional_edges(
    "planner",
    router_node,
    {
        "research": "research",
        "coding": "coding",
        "media": "media",
        "review": "review",
        "__end__": END
    }
)

# Agents -> Router (Loop back)
workflow.add_conditional_edges(
    "research",
    router_node,
    {
        "research": "research",
        "coding": "coding",
        "media": "media",
        "review": "review",
        "__end__": END
    }
)
workflow.add_conditional_edges(
    "coding",
    router_node,
    {
        "research": "research",
        "coding": "coding",
        "media": "media",
        "review": "review",
        "__end__": END
    }
)
workflow.add_conditional_edges(
    "media",
    router_node,
    {
        "research": "research",
        "coding": "coding",
        "media": "media",
        "review": "review",
        "__end__": END
    }
)
workflow.add_conditional_edges(
    "review",
    router_node,
    {
        "research": "research",
        "coding": "coding",
        "media": "media",
        "review": "review",
        "__end__": END
    }
)

# Persistence Setup
# Using SQLite for local persistence without external DB
conn = sqlite3.connect("db/checkpoints.sqlite", check_same_thread=False)
checkpointer = SqliteSaver(conn)

# Compile with Checkpointer
app = workflow.compile(checkpointer=checkpointer)
