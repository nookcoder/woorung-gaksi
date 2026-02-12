# Agent Skills (Tools)

This directory contains the tools (skills) available to the AI agents.
Each tool is a function decorated with `@tool` or a class inheriting from `BaseTool`.

## 1. Directory Structure

```
src/tools/
├── __init__.py       # Export all tools
├── web_search.py     # Example: Web Search Tool
├── file_ops.py       # Example: File Operations
└── README.md         # This file
```

## 2. Implementing a New Skill

1.  **Create a new file** (e.g., `my_skill.py`).
2.  **Define the tool** using `@tool` decorator.
3.  **Add Docstring**: Crucial! The LLM uses this to understand *when* and *how* to use the tool.
4.  **Add Type Hints**: Use Pydantic models for complex inputs.

### Example

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(description="The search query to execute")

@tool("web_search", args_schema=SearchInput)
def web_search(query: str) -> str:
    """
    Search the web for information about a topic.
    Use this when you need current events or documentation.
    """
    # Implementation here...
    return f"Results for {query}"
```

## 3. Registering the Skill

Add the tool to the agent's graph in `src/modules/manager/graph.py`:

```python
from src.tools.web_search import web_search

tools = [web_search]
llm_with_tools = llm.bind_tools(tools)
```
