from typing import Dict, Any, List, Optional
from datetime import datetime
from agent.architectural_artifacts import ArchitectureDecisionRecord

class ADRManager:
    @staticmethod
    def create_adr(
        id: str,
        title: str,
        context: str,
        decision: str,
        consequences: str,
        alternatives: Optional[List[str]] = None,
        status: str = "Accepted",
        supersedes: Optional[str] = None
    ) -> ArchitectureDecisionRecord:
        """
        Creates an ArchitectureDecisionRecord object.
        """
        return ArchitectureDecisionRecord(
            id=id,
            title=title,
            status=status,
            context=context,
            decision=decision,
            consequences=consequences,
            alternatives=alternatives or [],
            created_at=datetime.utcnow().isoformat() + "Z",
            supersedes=supersedes
        )

    @staticmethod
    def generate_tech_stack_adr(tech_stack: Dict[str, Any]) -> ArchitectureDecisionRecord:
        """
        Generates ADR-001 for tech stack selection.
        """
        stack_str = ", ".join(f"{k}: {v}" for k, v in tech_stack.items())
        context = "We need to select a reliable and compatible technology stack for the project requirements."
        decision = f"We will use the following technology stack:\n{stack_str}"
        consequences = "Ensures structure and standard libraries are used. Requires setting up correct package.json or python virtual environments."
        alternatives = ["Vanilla HTML/CSS/JS", "Next.js", "Ruby on Rails"]
        
        return ADRManager.create_adr(
            id="ADR-001",
            title="Technology Stack Selection",
            context=context,
            decision=decision,
            consequences=consequences,
            alternatives=alternatives
        )

    @staticmethod
    def generate_deployment_adr(plan_data: Dict[str, Any]) -> ArchitectureDecisionRecord:
        """
        Generates ADR-002 for deployment architecture.
        """
        tech_stack = plan_data.get("tech_stack", {})
        has_fe = "react" in str(tech_stack).lower() or "vue" in str(tech_stack).lower()
        has_be = "fastapi" in str(tech_stack).lower() or "express" in str(tech_stack).lower() or "node" in str(tech_stack).lower()

        if has_fe and has_be:
            decision = "We will use a decoupled deployment architecture with front-end client calling the back-end API server."
            consequences = "Requires handling CORS, and deploying two separate services or containerized environments."
        else:
            decision = "We will use a single-tier server-side rendered or monolithic deployment."
            consequences = "Simplifies deployment, no CORS issues, single service to maintain."
            
        context = "Determine physical deployment architecture layout to map how client code interacts with host infrastructure."
        alternatives = ["Serverless Functions", "Static site hosting with Mock API"]
        
        return ADRManager.create_adr(
            id="ADR-002",
            title="Deployment Architecture Layout",
            context=context,
            decision=decision,
            consequences=consequences,
            alternatives=alternatives
        )

    @staticmethod
    def generate_data_persistence_adr(plan_data: Dict[str, Any]) -> ArchitectureDecisionRecord:
        """
        Generates ADR-003 for database persistence.
        """
        tech_stack = plan_data.get("tech_stack", {})
        db_type = "In-Memory"
        for db in ["postgresql", "postgres", "sqlite", "mongodb", "mysql", "redis"]:
            if db in str(tech_stack).lower() or db in str(plan_data.get("description", "")).lower():
                db_type = db.capitalize()
                break

        if db_type != "In-Memory":
            decision = f"We will use {db_type} for persistent storage."
            consequences = f"Requires setting up connection strings, schemas, and managing database connections safely."
        else:
            decision = "No external database database requested. We will use in-memory mock storage."
            consequences = "Zero database setup overhead, but data will not persist across service restarts."
            
        context = "Select database and storage backend to manage state persistence requirements."
        alternatives = ["PostgreSQL", "SQLite", "MongoDB", "In-Memory Data Structures"]

        return ADRManager.create_adr(
            id="ADR-003",
            title="Data Persistence Strategy",
            context=context,
            decision=decision,
            consequences=consequences,
            alternatives=alternatives
        )

    @staticmethod
    def format_adr_markdown(adr: ArchitectureDecisionRecord) -> str:
        """
        Formats an ADR as a clean Markdown string.
        """
        lines = [
            f"# {adr.id}: {adr.title}",
            f"**Status**: {adr.status} | **Created At**: {adr.created_at}",
            ""
        ]
        if adr.supersedes:
            lines.append(f"*Supersedes: {adr.supersedes}*")
        if adr.superseded_by:
            lines.append(f"*Superseded by: {adr.superseded_by}*")
            
        lines.extend([
            "## Context",
            adr.context,
            "",
            "## Decision",
            adr.decision,
            "",
            "## Consequences",
            adr.consequences,
            ""
        ])
        
        if adr.alternatives:
            lines.extend([
                "## Alternatives Considered",
                "\n".join(f"- {alt}" for alt in adr.alternatives),
                ""
            ])
            
        return "\n".join(lines)
