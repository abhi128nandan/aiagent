import os

# Fix CmdRunAction is uninitialized
with open("agent/nodes.py", "r") as f:
    content = f.read()

# Add missing import for CmdRunAction if needed or fix its initialization
if "CmdRunAction" in content and "from agent.schema import" not in content.split("CmdRunAction")[0]:
    # It might just be an import issue inside the function. Let's see how it's used.
    # Actually, we can just import CmdRunAction locally.
    content = content.replace("action = CmdRunAction(", "from agent.schema import CmdRunAction\n                        action = CmdRunAction(")

# Fix int | None for port
content = content.replace("runtime.health_check(port=app_port)", "runtime.health_check(port=app_port or 3000)")

# Fix datetime.utcnow
content = content.replace("datetime.utcnow()", "datetime.now(timezone.utc)")
if "from datetime import timezone" not in content:
    content = content.replace("from datetime import datetime", "from datetime import datetime, timezone")

with open("agent/nodes.py", "w") as f:
    f.write(content)


with open("agent/architecture_planner_node.py", "r") as f:
    content = f.read()

content = content.replace("extract_plan_json(raw_text)", "extract_plan_json(str(raw_text))")
content = content.replace("datetime.utcnow()", "datetime.now(timezone.utc)")
if "from datetime import timezone" not in content:
    content = content.replace("from datetime import datetime", "from datetime import datetime, timezone")
    
with open("agent/architecture_planner_node.py", "w") as f:
    f.write(content)

print("Remaining fixed")
