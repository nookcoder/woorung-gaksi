import subprocess
import os
import json
from langchain_core.tools import tool

@tool
def run_alpha_k(ticker: str) -> str:
    """
    Run the Alpha-K trading analysis system for a specific stock ticker.
    Returns the analysis result (JSON or text summary).
    Example ticker: '005930' (Samsung Electronics), 'AAPL' (Apple).
    """
    try:
        # Resolve path to alpha-k main.py
        # pm-agent is at services/pm-agent
        # alpha-k is at services/alpha-k
        # Assuming we are running from project root or pm-agent root.
        # Let's find project root relationally.
        
        # Current file: services/pm-agent/src/tools/alpha_k.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
        script_path = os.path.join(project_root, "services/alpha-k/src/main.py")
        
        if not os.path.exists(script_path):
            return f"Error: Alpha-K script not found at {script_path}"

        # Execute using python
        # We assume the environment has dependencies or we use the specific venv python if needed.
        # For simplicity, using 'python' from current path.
        command = ["python", script_path, "--ticker", ticker]
        
        result = subprocess.run(command, capture_output=True, text=True, cwd=project_root)
        
        if result.returncode != 0:
            return f"Error executing Alpha-K:\nInternal StdErr: {result.stderr}\nExternal StdOut: {result.stdout}"
            
        return f"Alpha-K Analysis for {ticker}:\n{result.stdout}"

    except Exception as e:
        return f"failed to execute alpha-k: {str(e)}"
