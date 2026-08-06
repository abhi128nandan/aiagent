import json

def structural_plan_check(plan_str):
    issues = []
    auto_reject = False
    
    try:
        plan = json.loads(plan_str)
    except (json.JSONDecodeError, TypeError):
        return {'issues': ['Plan JSON is unparseable'], 'auto_reject': True}
    
    if not plan:
        return {'issues': ['Plan is empty'], 'auto_reject': True}
    
    # Extract tasks/steps
    tasks = plan.get('tasks', plan.get('steps', []))
    if not tasks:
        issues.append('Plan has no tasks or steps — the execution graph will be empty')
    else:
        for i, task in enumerate(tasks):
            if isinstance(task, dict):
                desc = task.get('description', task.get('content', ''))
                if not desc or len(desc) < 5:
                    issues.append(f'Task {i+1} has no meaningful description or content')
                
                # Support old 'files' array and new 'file_path' / 'file' string
                task_files = task.get('files', [])
                if not task_files:
                    f = task.get('file_path', task.get('file', ''))
                    if f:
                        task_files.append(f)
                
                if not task_files and not task.get('command') and not task.get('action'):
                    issues.append(f'Task {i+1} has no files, command, or action associated')

    # Extract all files
    files = plan.get('files', [])
    if not files:
        for t in tasks:
            if isinstance(t, dict):
                f = t.get('file_path', t.get('file', ''))
                if f:
                    files.append(f)
                for tf in t.get('files', []):
                    files.append(tf)

    if not files and tasks:
        issues.append('Plan has no files list — the agent won\'t know what to create')
    
    # Check for Docker binding issues
    plan_text = plan_str.lower()
    if 'localhost' in plan_text and '0.0.0.0' not in plan_text:
        issues.append(
            'Plan references localhost but not 0.0.0.0 — '
            'servers inside Docker MUST bind to 0.0.0.0'
        )
    
    # Check for background server commands
    commands = []
    # Check top-level run_command
    run_cmd = plan.get('run_command', '')
    if run_cmd:
        commands.append(run_cmd)
        
    for task in tasks:
        if isinstance(task, dict):
            cmd = task.get('command', '') or ''
            if cmd:
                commands.append(cmd)
    
    server_keywords = ['npm start', 'npm run dev', 'node server', 'python -m',
                       'uvicorn', 'gunicorn', 'flask run', 'python app',
                       'python main', 'python manage.py runserver']
    for cmd in commands:
        cmd_lower = cmd.lower()
        for kw in server_keywords:
            if kw in cmd_lower and '&' not in cmd and 'nohup' not in cmd_lower:
                issues.append(
                    f'Server command "{cmd[:60]}" does not run in background '
                    '(missing "&" or "nohup")'
                )
                break
    
    # Check tech_stack sanity
    tech = plan.get('tech_stack', {})
    if isinstance(tech, dict):
        frontend = tech.get('frontend', '').lower()
        backend = tech.get('backend', '').lower()
        language = tech.get('language', '').lower()
        
        # Detect contradictions and framework mismatches
        if frontend in ('react', 'vue', 'angular', 'svelte') and language == 'python':
            issues.append(
                f'Tech stack contradiction: frontend is {frontend} '
                f'but language is {language}. Frontend needs JavaScript/TypeScript.'
            )
            
        # Detect React/backend hallucination in Vanilla JS project
        if frontend == 'html_css_js' or frontend == 'none':
            for f in files:
                if isinstance(f, str) and (
                    'package.json' in f or 'vite.config' in f or 
                    'src/components' in f or '.jsx' in f or '.tsx' in f
                ):
                    issues.append(f'Framework mismatch: Vanilla JS project cannot contain {f}')
                    auto_reject = True
    
    return {
        'issues': issues,
        'auto_reject': auto_reject
    }

plan_str = """
{
  "project": "To-Do List Web Application",
  "description": "A simple and user-friendly To-Do List Web Application using HTML, CSS, and JavaScript.",
  "tech_stack": {
    "frontend": "html_css_js",
    "backend": "none",
    "database": "none",
    "language": "javascript"
  },
  "api_contract": [],
  "steps": [
    {
      "file_path": "src/services/taskService.js",
      "action": "create",
      "content": "const tasks = [];"
    },
    {
      "file_path": "src/components/TaskList.js",
      "action": "create",
      "content": "import React from 'react';"
    }
  ]
}
"""

print(structural_plan_check(plan_str))
