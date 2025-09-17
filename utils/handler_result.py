from typing import Any, Dict, Optional


class HandlerResult:
    def __init__(
        self,
        content: Any,
        success: bool,
        log: Optional[Dict] = None,
        error: Optional[str] = None,
    ):
        self.content = content
        self.success = success
        self.log = {} if log is None else log
        self.error = error

    def __repr__(self):
        return f"HandlerResult(success={self.success}, content={self.content}, log={self.log}, error={self.error})"
