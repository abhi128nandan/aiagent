from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Any, Dict

class TechStack(BaseModel):
    frontend: str = Field(description="Frontend framework: react, html_css_js, vue, angular, sap_ui5, or none")
    backend: str = Field(description="Backend framework: express, fastapi, flask, spring_boot, abap, or none")
    database: str = Field(description="Database: postgresql, mongodb, sqlite, mysql, sap_hana, or none")
    language: str = Field(description="Programming language: javascript, typescript, python, java, go, or abap")

class Environment(BaseModel):
    runtime: List[str] = Field(description="List of runtimes needed, e.g., ['node'], ['python3']")
    system_packages: List[str] = Field(default_factory=list, description="List of system packages")
    global_tools: List[str] = Field(default_factory=list, description="List of global npm/pip tools to install")

class Step(BaseModel):
    file: str = Field(description="File path")
    action: str = Field(description="Action to take, e.g., create, modify")
    description: str = Field(description="Detailed description of the changes to make")

class ApiContract(BaseModel):
    endpoint: str = Field(default="", description="API route or endpoint path")
    method: str = Field(default="GET", description="HTTP method")
    description: Optional[str] = Field(default="", description="Description of the endpoint")
    response_schema: Optional[Dict[str, Any]] = Field(default=None, description="JSON schema object of the response")
    route: Optional[str] = Field(default=None, description="Legacy field name for endpoint")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            target = data.get("endpoint") or data.get("route") or data.get("path") or ""
            data["endpoint"] = target
            data["route"] = target
        return data

class BootstrapPlan(BaseModel):
    project: str = Field(description="Project name")
    description: str = Field(description="One-line description of the project")
    tech_stack: TechStack
    environment: Environment
    template_selected: str = Field(description="Template to use, e.g., react-vite, or none for existing project")
    run_command: str = Field(description="Command to run the application")
    steps: List[Step] = Field(default_factory=list, description="Must be an empty array for bootstrap phase")

class DetailPlan(BootstrapPlan):
    api_contract: Optional[List[ApiContract]] = Field(default=None, description="API contracts if a backend is specified")
    steps: List[Step] = Field(description="Detailed file-level implementation steps")
