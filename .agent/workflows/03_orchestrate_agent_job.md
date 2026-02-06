---
description: Orchestrate a complex user request via PM Agent logic
---

# Orchestrate Agent Job (PM Loop)

This workflow describes how the **PM Agent** (Manager) processes a high-level request and distributes it to workers.

## 1. Input Analysis

**User Request**: Received via Telegram/API.
**Goal**: Identify the _Intent_ and required _Capabilities_.

Example: "Find 3 AI news items and make a video."

- Intent: Content Creation.
- Capabilities: Research (News) + Media (Video).

## 2. Task Breakdown (Brain)

The PM creates a `Job` in the Core API (Go) with sub-tasks.

```json
{
  "job_type": "content_pipeline",
  "steps": [
    {
      "worker": "research_agent",
      "task": "crawl_tech_news",
      "params": { "count": 3 }
    },
    {
      "worker": "media_agent",
      "task": "generate_shorts",
      "depends_on": "step_1"
    },
    { "worker": "dev_agent", "task": "post_blog", "depends_on": "step_1" }
  ]
}
```

## 3. Dispatch & Monitor

1.  **Dispatch**: PM sends `step_1` to `Redis Queue (Topic: research)`.
2.  **Monitor**: Core API (Go) listens for task completion events.
3.  **Next Step**: Upon `step_1` success, PM/Core triggers `step_2` and `step_3`.

## 4. Final Report

Once all steps are `COMPLETED`:

1.  PM compiles a defined summary.
2.  Sends notification to User via Telegram.
    - "✅ Blog Posted: [Link]"
    - "✅ Video Ready: [Link]"
