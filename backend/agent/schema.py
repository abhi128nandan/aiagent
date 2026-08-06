from pydantic import BaseModel, Field
from typing import Literal, Union, Optional

class BaseAction(BaseModel):
    type: str

class CmdRunAction(BaseAction):
    type: Literal['run'] = 'run'
    command: str
    is_hidden: bool = False

class FileWriteAction(BaseAction):
    type: Literal['write'] = 'write'
    path: str
    content: str

class FileReplaceAction(BaseAction):
    type: Literal['replace'] = 'replace'
    path: str
    target_content: str
    replacement_content: str

class FileReadAction(BaseAction):
    type: Literal['read'] = 'read'
    path: str

class FinishAction(BaseAction):
    type: Literal['finish'] = 'finish'
    message: str

class BrowserAction(BaseAction):
    type: Literal['browse'] = 'browse'
    command: str  # e.g., 'goto', 'click', 'scroll', 'screenshot'
    target: str = "" # URL or selector

class WebSearchAction(BaseAction):
    type: Literal['search'] = 'search'
    query: str

class UnknownAction(BaseAction):
    type: Literal['unknown'] = 'unknown'
    content: str

# Union type for all possible actions
ActionType = Union[CmdRunAction, FileWriteAction, FileReplaceAction, FileReadAction, FinishAction, BrowserAction, WebSearchAction, UnknownAction]


class BaseObservation(BaseModel):
    type: str
    exit_code: int = 0
    output: str = ""

class CmdOutputObservation(BaseObservation):
    type: Literal['cmd_output'] = 'cmd_output'

class FileWriteObservation(BaseObservation):
    type: Literal['file_write'] = 'file_write'
    path: str

class BrowserObservation(BaseObservation):
    type: Literal['browser'] = 'browser'
    content: str = "" # markdown content or error

class ErrorObservation(BaseObservation):
    type: Literal['error'] = 'error'

class ValidatedObservation(BaseObservation):
    type: Literal['validated'] = 'validated'
    app_started: bool = False

ObservationType = Union[CmdOutputObservation, FileWriteObservation, BrowserObservation, ErrorObservation, ValidatedObservation]
