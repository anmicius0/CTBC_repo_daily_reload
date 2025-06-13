import logging
import sys
from typing import Callable, TypeVar, Any, Optional
from functools import wraps
import requests
from github import (
    GithubException,
    RateLimitExceededException,
    BadCredentialsException,
    UnknownObjectException,
)

F = TypeVar("F", bound=Callable[..., Any])
logger = logging.getLogger(__name__)


class ErrorCategories:
    """Error category definitions for better classification."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    VALIDATION = "validation"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    GITHUB_API = "github_api"
    IQ_SERVER = "iq_server"


class ErrorDetails:
    """Container for detailed error information."""

    def __init__(
        self,
        category: str,
        message: str,
        is_retryable: bool = False,
        suggestion: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        self.category = category
        self.message = message
        self.is_retryable = is_retryable
        self.suggestion = suggestion
        self.error_code = error_code


class ErrorHandler:
    """Enhanced error handler with nuanced error detection and categorization."""

    @staticmethod
    def _categorize_github_error(e: Exception) -> ErrorDetails:
        """Categorize GitHub API errors with specific details."""
        if isinstance(e, BadCredentialsException):
            return ErrorDetails(
                category=ErrorCategories.AUTHENTICATION,
                message="GitHub authentication failed",
                suggestion="Check GITHUB_TOKEN environment variable",
                error_code="GITHUB_AUTH_FAILED",
            )
        elif isinstance(e, RateLimitExceededException):
            return ErrorDetails(
                category=ErrorCategories.RATE_LIMIT,
                message="GitHub API rate limit exceeded",
                is_retryable=True,
                suggestion="Wait for rate limit reset or use authenticated requests",
                error_code="GITHUB_RATE_LIMIT",
            )
        elif isinstance(e, UnknownObjectException):
            return ErrorDetails(
                category=ErrorCategories.NOT_FOUND,
                message=f"GitHub resource not found: {str(e)}",
                suggestion="Check repository name and permissions",
                error_code="GITHUB_NOT_FOUND",
            )
        elif isinstance(e, GithubException):
            status = getattr(e, "status", None)
            if status == 403:
                return ErrorDetails(
                    category=ErrorCategories.AUTHORIZATION,
                    message="GitHub access forbidden",
                    suggestion="Check repository permissions and token scope",
                    error_code="GITHUB_FORBIDDEN",
                )
            elif status == 422:
                return ErrorDetails(
                    category=ErrorCategories.VALIDATION,
                    message=f"GitHub validation error: {e.data.get('message', str(e)) if hasattr(e, 'data') else str(e)}",
                    suggestion="Check request parameters and data format",
                    error_code="GITHUB_VALIDATION",
                )
            else:
                return ErrorDetails(
                    category=ErrorCategories.GITHUB_API,
                    message=f"GitHub API error (status {status}): {str(e)}",
                    is_retryable=status >= 500 if status else False,
                    error_code=f"GITHUB_API_{status}"
                    if status
                    else "GITHUB_API_UNKNOWN",
                )
        else:
            return ErrorDetails(
                category=ErrorCategories.GITHUB_API,
                message=f"GitHub API error: {str(e)}",
                error_code="GITHUB_UNKNOWN",
            )

    @staticmethod
    def _categorize_http_error(
        e: requests.exceptions.HTTPError, operation_context: str = ""
    ) -> ErrorDetails:
        """Categorize HTTP errors with enhanced context."""
        status_code = getattr(e.response, "status_code", None) if e.response else None
        response_text = ""

        if e.response:
            try:
                response_data = e.response.json()
                if isinstance(response_data, dict):
                    response_text = response_data.get(
                        "message", response_data.get("error", str(response_data))
                    )
                else:
                    response_text = str(response_data)
            except (ValueError, TypeError):
                response_text = e.response.text[:200]  # Limit response text length

        if status_code == 401:
            return ErrorDetails(
                category=ErrorCategories.AUTHENTICATION,
                message=f"Authentication failed: {response_text}",
                suggestion="Check credentials and authentication tokens",
                error_code="HTTP_401_UNAUTHORIZED",
            )
        elif status_code == 403:
            return ErrorDetails(
                category=ErrorCategories.AUTHORIZATION,
                message=f"Access forbidden: {response_text}",
                suggestion="Check user permissions and access rights",
                error_code="HTTP_403_FORBIDDEN",
            )
        elif status_code == 404:
            return ErrorDetails(
                category=ErrorCategories.NOT_FOUND,
                message=f"Resource not found: {response_text}",
                suggestion="Verify resource exists and URL is correct",
                error_code="HTTP_404_NOT_FOUND",
            )
        elif status_code == 409:
            return ErrorDetails(
                category=ErrorCategories.CONFLICT,
                message=f"Resource conflict: {response_text}",
                suggestion="Resource may already exist or be in conflicting state",
                error_code="HTTP_409_CONFLICT",
            )
        elif status_code == 422:
            return ErrorDetails(
                category=ErrorCategories.VALIDATION,
                message=f"Validation error: {response_text}",
                suggestion="Check request data format and required fields",
                error_code="HTTP_422_VALIDATION",
            )
        elif status_code == 429:
            return ErrorDetails(
                category=ErrorCategories.RATE_LIMIT,
                message=f"Rate limit exceeded: {response_text}",
                is_retryable=True,
                suggestion="Wait before retrying or reduce request frequency",
                error_code="HTTP_429_RATE_LIMIT",
            )
        elif status_code and 500 <= status_code < 600:
            return ErrorDetails(
                category=ErrorCategories.SERVER_ERROR,
                message=f"Server error ({status_code}): {response_text}",
                is_retryable=True,
                suggestion="Server issue - retry may help",
                error_code=f"HTTP_{status_code}_SERVER_ERROR",
            )
        else:
            return ErrorDetails(
                category=ErrorCategories.NETWORK,
                message=f"HTTP error ({status_code}): {response_text}",
                is_retryable=status_code >= 500 if status_code else False,
                error_code=f"HTTP_{status_code}_ERROR"
                if status_code
                else "HTTP_UNKNOWN_ERROR",
            )

    @staticmethod
    def _categorize_network_error(e: Exception) -> ErrorDetails:
        """Categorize network-related errors."""
        if isinstance(e, requests.exceptions.ConnectionError):
            return ErrorDetails(
                category=ErrorCategories.NETWORK,
                message="Connection failed",
                is_retryable=True,
                suggestion="Check network connectivity and server availability",
                error_code="NETWORK_CONNECTION_ERROR",
            )
        elif isinstance(e, requests.exceptions.Timeout):
            return ErrorDetails(
                category=ErrorCategories.TIMEOUT,
                message="Request timeout",
                is_retryable=True,
                suggestion="Server may be slow - try increasing timeout or retry",
                error_code="NETWORK_TIMEOUT",
            )
        elif isinstance(e, requests.exceptions.RequestException):
            return ErrorDetails(
                category=ErrorCategories.NETWORK,
                message=f"Network error: {str(e)}",
                is_retryable=True,
                error_code="NETWORK_REQUEST_ERROR",
            )
        else:
            return ErrorDetails(
                category=ErrorCategories.NETWORK,
                message=f"Unknown network error: {str(e)}",
                error_code="NETWORK_UNKNOWN_ERROR",
            )

    @staticmethod
    def _format_error_message(error_details: ErrorDetails, operation_type: str) -> str:
        """Format error message with enhanced details."""
        emoji_map = {
            ErrorCategories.AUTHENTICATION: "🔐",
            ErrorCategories.AUTHORIZATION: "🚫",
            ErrorCategories.RATE_LIMIT: "⏰",
            ErrorCategories.NETWORK: "🌐",
            ErrorCategories.NOT_FOUND: "🔍",
            ErrorCategories.CONFLICT: "⚡",
            ErrorCategories.VALIDATION: "✏️",
            ErrorCategories.SERVER_ERROR: "🔥",
            ErrorCategories.TIMEOUT: "⏱️",
            ErrorCategories.GITHUB_API: "🐙",
            ErrorCategories.IQ_SERVER: "🛡️",
        }

        emoji = emoji_map.get(error_details.category, "❌")
        retry_info = " (retryable)" if error_details.is_retryable else ""

        message = (
            f"{emoji} {operation_type} failed: {error_details.message}{retry_info}"
        )
        if error_details.suggestion:
            message += f"\n  💡 Suggestion: {error_details.suggestion}"
        if error_details.error_code:
            message += f"\n  🏷️ Error Code: {error_details.error_code}"

        return message

    @staticmethod
    def handle_operation(
        operation_type: str = "operation", return_none_on_error: bool = False
    ):
        """Enhanced decorator for API operation error handling with nuanced detection."""

        def decorator(func: F) -> F:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return func(*args, **kwargs)
                except (
                    BadCredentialsException,
                    RateLimitExceededException,
                    UnknownObjectException,
                    GithubException,
                ) as e:
                    error_details = ErrorHandler._categorize_github_error(e)
                    logger.error(
                        f"{operation_type} failed: {error_details.message} ({error_details.error_code})"
                    )
                    print(
                        ErrorHandler._format_error_message(
                            error_details, operation_type
                        ),
                        file=sys.stderr,
                    )
                    return None if return_none_on_error else False
                except requests.exceptions.HTTPError as e:
                    error_details = ErrorHandler._categorize_http_error(
                        e, operation_type
                    )
                    logger.error(
                        f"{operation_type} failed: {error_details.message} ({error_details.error_code})"
                    )
                    print(
                        ErrorHandler._format_error_message(
                            error_details, operation_type
                        ),
                        file=sys.stderr,
                    )
                    return None if return_none_on_error else False
                except (
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.RequestException,
                ) as e:
                    error_details = ErrorHandler._categorize_network_error(e)
                    logger.error(
                        f"{operation_type} failed: {error_details.message} ({error_details.error_code})"
                    )
                    print(
                        ErrorHandler._format_error_message(
                            error_details, operation_type
                        ),
                        file=sys.stderr,
                    )
                    return None if return_none_on_error else False
                except (ValueError, RuntimeError, KeyError, FileNotFoundError) as e:
                    error_details = ErrorDetails(
                        category=ErrorCategories.VALIDATION,
                        message=str(e),
                        suggestion="Check configuration and input data",
                        error_code=f"{type(e).__name__}_ERROR",
                    )
                    logger.error(
                        f"{operation_type} failed: {error_details.message} ({error_details.error_code})"
                    )
                    print(
                        ErrorHandler._format_error_message(
                            error_details, operation_type
                        ),
                        file=sys.stderr,
                    )
                    return None if return_none_on_error else False
                except Exception as e:
                    error_details = ErrorDetails(
                        category="unknown",
                        message=f"{type(e).__name__}: {str(e)}",
                        error_code="UNKNOWN_ERROR",
                    )
                    logger.error(
                        f"Unexpected error during {operation_type}: {error_details.message}"
                    )
                    print(
                        ErrorHandler._format_error_message(
                            error_details, operation_type
                        ),
                        file=sys.stderr,
                    )
                    return None if return_none_on_error else False

            return wrapper  # type: ignore[return-value]

        return decorator

    @staticmethod
    def handle_config_error(func: F) -> F:
        """Decorator for config error handling."""

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except (ValueError, FileNotFoundError, KeyError) as e:
                logger.error(f"Configuration error: {e}")
                print(f"❌ Configuration Error: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                logger.error(f"Unexpected configuration error: {e}")
                print(f"❌ Unexpected Configuration Error: {e}", file=sys.stderr)
                sys.exit(1)

        return wrapper  # type: ignore[return-value]

    @staticmethod
    def handle_main_execution(func: F) -> F:
        """Decorator for main execution error handling."""

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                logger.info("Operation cancelled by user")
                print("\n⏹️ Operation cancelled by user.", file=sys.stderr)
                sys.exit(130)
            except (
                ValueError,
                RuntimeError,
                ConnectionError,
                requests.exceptions.HTTPError,
            ) as e:
                logger.error(f"Operation failed: {e}")
                print(f"❌ Error: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                logger.error(f"Unexpected error: {type(e).__name__} - {e}")
                print(f"❌ Unexpected Error: {type(e).__name__} - {e}", file=sys.stderr)
                sys.exit(1)

        return wrapper  # type: ignore[return-value]


class OperationError(Exception):
    """Base exception for project operations."""

    pass
