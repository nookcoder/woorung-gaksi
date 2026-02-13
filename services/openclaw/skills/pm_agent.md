# PM Agent (Project Manager)

This skill allows the agent to handle general tasks, project management, and complex planning using the Woorung-Gaksi PM Agent.

## Tools

### ask_pm_agent

Send a message to the PM Agent for general assistance, planning, or complex task execution.

**Parameters:**

- `message` (required, string): The user's query or instruction.
- `user_id` (optional, string): The ID of the user.
- `thread_id` (optional, string): Persistence key to continue a conversation.

**Command:**

```bash
curl -X POST "http://pm-agent:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"message": {{message}}, "user_id": {{user_id or "anonymous"}}, "thread_id": {{thread_id or ""}}}'
```
