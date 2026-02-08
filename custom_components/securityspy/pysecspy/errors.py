"""Define package errors."""


class SecuritySpyError(Exception):
    """Define a base error."""


class InvalidCredentials(SecuritySpyError):
    """Define an error related to invalid or missing Credentials."""


class RequestError(SecuritySpyError):
    """Define an error related to invalid requests."""


class ResultError(SecuritySpyError):
    """Define an error related to the result returned from a request."""
