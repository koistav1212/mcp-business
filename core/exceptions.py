class AgentException(Exception):
    """Base exception for all agent framework errors."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PlannerException(AgentException):
    """Raised when there is an error during planning or execution plan generation."""
    pass


class ToolExecutionException(AgentException):
    """Raised when an error occurs during tool selection or tool execution."""
    pass


class MemoryException(AgentException):
    """Raised when storing, retrieving, or searching memory fails."""
    pass


class VerificationException(AgentException):
    """Raised when validation/verification of execution steps or final outputs fail."""
    pass


class ConfigurationException(AgentException):
    """Raised when configuration variables or credentials are invalid or missing."""
    pass
