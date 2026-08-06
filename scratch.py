import re
import time

prompt_marker = '[PROMPT_END]# '
ansi_escape = re.compile(r'(?:\x1B[@-Z\\-_]|\x1B\[[0-?]*[ -/]*[@-~])')

action_command = "npx -y vite@latest simple-ecommerce-website --template react"
chunks = [
    "npx -y vite@latest simp\r\n",
    "le-ecommerce-website --template react\r\n",
    "\x1b[36m\x1b[1m\nScaffolding project in /workspace/simple-ecommerce-website...\x1b[22m\x1b[39m\n\n\x1b[32mDone. Now run:\x1b[39m\n\n  \x1b[32mcd\x1b[39m simple-ecommerce-website\n  \x1b[32mnpm\x1b[39m install\n  \x1b[32mnpm\x1b[39m run dev\n\n[PROMPT_END]# "
]

first_line_skipped = False
accumulated_output = []

for chunk in chunks:
    clean_chunk = ansi_escape.sub('', chunk)

    if not first_line_skipped:
        lines = clean_chunk.split('\n', 1)
        print("Checking first line:", repr(lines[0]))
        if action_command.strip() in lines[0]:
            clean_chunk = lines[1] if len(lines) > 1 else ''
        first_line_skipped = True

    display_chunk = chunk.replace(prompt_marker, '')

    if display_chunk.strip():
        accumulated_output.append(clean_chunk)
        print("Broadcast:", repr(display_chunk))

print("Recent:", repr(''.join(accumulated_output[-3:])))
