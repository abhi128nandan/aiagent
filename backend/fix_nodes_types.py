import os

path = "agent/nodes.py"
with open(path, "r") as f:
    content = f.read()

# Fix 1: plan_files: list[str] = None -> plan_files: list[str] | None = None
content = content.replace("plan_files: list[str] = None", "plan_files: list[str] | None = None")

# Fix 2: extract_plan_json(raw_text) -> extract_plan_json(str(raw_text)) where raw_text is response.content
content = content.replace("extract_plan_json(raw_text)", "extract_plan_json(str(raw_text))")

# Fix 3: parsed_error may be uninitialized
old_parsed_error = "if 'parsed_error' in locals() and parsed_error:\n                    error_file = parsed_error.file"
new_parsed_error = "parsed_error = locals().get('parsed_error')\n                if parsed_error:\n                    error_file = getattr(parsed_error, 'file', None)"
content = content.replace(old_parsed_error, new_parsed_error)

# Fix 4: DockerRuntime | None is not assignable to DockerRuntime
#     runtime = DockerRuntime.get(session_id) if session_id else None
old_runtime = "runtime = DockerRuntime.get(session_id) if session_id else None"
new_runtime = "runtime = DockerRuntime.get(session_id) if session_id else None\n    if not runtime:\n        return state"
content = content.replace(old_runtime, new_runtime)

# Fix 5: += is not supported between Literal[''] and list[...]
old_concat = "concat_text += chunk.content"
new_concat = "concat_text += str(chunk.content)"
content = content.replace(old_concat, new_concat)

# Fix 6: _re may be uninitialized
old_re = "fenced = _re.search"
new_re = "import re as _re\n                fenced = _re.search"
content = content.replace(old_re, new_re)

# Fix 7: StreamingMessageParser.feed type
old_feed = "self.parser.feed(concat_text)"
new_feed = "self.parser.feed(str(concat_text))"
content = content.replace(old_feed, new_feed)

with open(path, "w") as f:
    f.write(content)

print("Nodes.py fixed")
