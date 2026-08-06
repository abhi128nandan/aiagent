import os

with open("agent/state.py", "r") as f:
    content = f.read()

# Replace typing import for TypedDict
content = content.replace("from typing import TypedDict", "from typing import Literal, Annotated, Dict, Any, Optional, NotRequired, List, Union\nfrom typing_extensions import TypedDict")
with open("agent/state.py", "w") as f:
    f.write(content)


with open("agent/graph.py", "r") as f:
    content = f.read()

# Fix last_error_analysis slicing
content = content.replace("last_error_analysis[:500]", "str(last_error_analysis)[:500]")

# We need to import typing.cast in graph.py
if "from typing import" in content and "cast" not in content:
    content = content.replace("from typing import", "from typing import cast,")

# For the status assignments, we will just use cast
content = content.replace("new_state[\"status\"] = node_to_status.get", "new_state[\"status\"] = cast(Any, node_to_status.get")

with open("agent/graph.py", "w") as f:
    f.write(content)

print("Graph and state fixed")
