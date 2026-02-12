from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from src.shared.config import config
from pydantic import SecretStr

@tool
def code_gen(task_description: str) -> str:
    """
    Generate code based on a description.
    Use this to write functions, classes, or scripts.
    """
    api_key = SecretStr(config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None
    
    llm = ChatOpenAI(
        model=config.MODEL_NAME,
        temperature=0,
        api_key=api_key,
        base_url=config.OPENAI_BASE_URL
    )
    
    from langchain_core.prompts import ChatPromptTemplate
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert software engineer. Write clean, efficient, and well-documented code based on the user's request. Output ONLY the code, or code inside markdown blocks."),
        ("user", "{description}")
    ])
    
    chain = prompt | llm
    
    try:
        result = chain.invoke({"description": task_description})
        return result.content
    except Exception as e:
        return f"Error generating code: {str(e)}"
