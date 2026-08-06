import os
import ast
import sys
from collections import defaultdict

backend_dir = "/media/aashikant/GAME Volume/aicode/myaiagent/backend"

imports = defaultdict(set)

for root, dirs, files in os.walk(backend_dir):
    if "venv" in root or ".git" in root or "__pycache__" in root:
        continue
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=filepath)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports[alias.name.split('.')[0]].add(filepath)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports[node.module.split('.')[0]].add(filepath)
            except Exception as e:
                print(f"Error parsing {filepath}: {e}")

print("Extracted top-level imports:")
for imp, files in sorted(imports.items()):
    # Get relative paths for clean display
    rel_files = [os.path.relpath(f, backend_dir) for f in files]
    print(f"- {imp}: used in {len(rel_files)} files (e.g. {rel_files[:3]})")
