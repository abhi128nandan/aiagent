from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from enum import Enum
from datetime import datetime

class VerificationMode(str, Enum):
    Strict = "Strict"
    Permissive = "Permissive"
    Disabled = "Disabled"

class StageCheckpoint(BaseModel):
    stage_name: str
    verification_status: Literal['Pending', 'Pass', 'Fail', 'Skipped'] = 'Pending'
    verification_timestamp: Optional[str] = None
    verification_details: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    failure_reasons: List[str] = Field(default_factory=list)
    artifacts_validated: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)

    def initialize(self):
        self.verification_status = 'Pending'
        self.retry_count = 0
        self.failure_reasons = []
        self.artifacts_validated = []
        self.verification_timestamp = None
        self.metrics = {}

    def update_status(self, status: Literal['Pending', 'Pass', 'Fail', 'Skipped'], details: Optional[Dict[str, Any]] = None):
        self.verification_status = status
        self.verification_timestamp = datetime.utcnow().isoformat() + "Z"
        if details:
            self.verification_details.update(details)

    def increment_retry(self):
        self.retry_count += 1
        self.verification_timestamp = datetime.utcnow().isoformat() + "Z"

    def reset(self):
        self.retry_count = 0


class VerificationResult(BaseModel):
    passed: bool
    stage: str
    severity: Literal['Info', 'Warning', 'Error', 'Critical'] = 'Info'
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    suggestions: List[str] = Field(default_factory=list)
    checkpoint_data: Optional[StageCheckpoint] = None
    execution_time_ms: int = 0
