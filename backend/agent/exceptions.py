class AgentException(Exception):
    pass

class TemplateNotFoundError(AgentException):
    def __init__(self, template_name: str, resolved_path: str):
        self.template_name = template_name
        self.resolved_path = resolved_path
        super().__init__(f"TemplateNotFoundError: '{template_name}' not found at {resolved_path}")
