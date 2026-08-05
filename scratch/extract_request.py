import json

with open("/home/aashikant/.gemini/antigravity/brain/5336c0dc-47aa-462f-b6f4-03e22cedaa0f/.system_generated/logs/overview.txt", "r") as f:
    line = f.readline()
    data = json.loads(line)
    
with open("/media/aashikant/GAME Volume/aicode/myaiagent/scratch/request_content.txt", "w") as out:
    out.write(data["content"])
