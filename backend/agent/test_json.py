import re
import json

def extract_plan_json(content: str) -> str:
    fenced = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if fenced:
        content = fenced.group(1)

    start = content.find('{')
    if start >= 0:
        depth = 0
        for idx, char in enumerate(content[start:], start=start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return content[start:idx + 1].strip()

    return content.strip()

print(extract_plan_json('```json\n{"regex": "a{3}", "valid": true}\n```'))
