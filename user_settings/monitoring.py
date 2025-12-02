"""
Sentry monitoring utilities for user settings module.
Provides decorators and helpers for tracking performance and errors.
"""

import functools
import time
from typing import Any, Callable, Optional, Dict
import logging

from django.http import JsonResponse

# Try to import sentry_sdk with fallback
try:
    import sentry_sdk
    from sentry_sdk import start_transaction, start_span, capture_message, capture_exception
    SENTRY_AVAILABLE = True
except ImportError:  # pragma: no cover - tested via subprocess isolation
    # Defensive fallback when sentry_sdk is not installed
    # Covered by: test_monitoring_import.py (subprocess test)
    SENTRY_AVAILABLE = False
    sentry_sdk = None
    start_transaction = None
    start_span = None
    capture_message = None
    capture_exception = None

logger = logging.getLogger(__name__)

# Performance thresholds (in seconds)
SLOW_OPERATION_THRESHOLD = 2.0  # Log warning if operation takes longer
CRITICAL_OPERATION_THRESHOLD = 5.0  # Log critical if operation takes too long

# Log Sentry availability on module load
if SENTRY_AVAILABLE:
    logger.info("✅ Sentry SDK is available for user_settings monitoring")
else:  # pragma: no cover - tested via subprocess isolation
    logger.warning("⚠️ Sentry SDK not available - monitoring will be disabled")


class UserSettingsSentryMonitor:
    """Custom Sentry monitoring for user settings operations."""
    
    MODULE = "user_settings"
    COMPONENT_VIEW = "view"
    COMPONENT_SERVICE = "service"
    COMPONENT_VALIDATION = "validation"
    
    @staticmethod
    def set_operation_context(operation: str, username: str, additional_data: Optional[Dict] = None):
        """Set context for the current user settings operation."""
        if not SENTRY_AVAILABLE:
            return
            
        context = {"operation": operation, "username": username, "module": UserSettingsSentryMonitor.MODULE, 
                   "timestamp": time.time(), **(additional_data or {})}
        tags = {"module": UserSettingsSentryMonitor.MODULE, "operation": operation, "username": username}
        
        sentry_sdk.set_context("operation_context", context)
        for key, value in tags.items():
            sentry_sdk.set_tag(key, value)
    
    @staticmethod
    def add_breadcrumb(message: str, category: str = "user_settings", level: str = "info", data: Optional[Dict] = None):
        """Add a breadcrumb to track execution flow."""
        if SENTRY_AVAILABLE:
            sentry_sdk.add_breadcrumb(category=category, message=message, level=level, data=data or {})
    
    @staticmethod
    def _set_context_and_tags(context_name: str, context: Dict, tags: Dict):
        """Set Sentry context and tags."""
        if not SENTRY_AVAILABLE:
            return
        
        sentry_sdk.set_context(context_name, context)
        for key, value in tags.items():
            sentry_sdk.set_tag(key, value)
    
    @staticmethod
    def _get_log_level_for_execution_time(execution_time: float) -> str:
        """Determine log level based on execution time."""
        if execution_time > CRITICAL_OPERATION_THRESHOLD:
            return "error"
        elif execution_time > SLOW_OPERATION_THRESHOLD:
            return "warning"
        else:
            return "info"
    
    @staticmethod
    def _log_local_operation_result(operation: str, username: str, success: bool, execution_time: float, error_message: Optional[str]):
        """Log operation result locally with performance warnings."""
        if success:
            if execution_time > CRITICAL_OPERATION_THRESHOLD:
                logger.error(f"🚨 CRITICAL: User settings {operation} took {execution_time:.3f}s for {username}")
            elif execution_time > SLOW_OPERATION_THRESHOLD:
                logger.warning(f"⚠️ SLOW: User settings {operation} took {execution_time:.3f}s for {username}")
            else:
                logger.info(f"✅ User settings {operation} completed in {execution_time:.3f}s for {username}")
        else:
            logger.error(f"❌ User settings {operation} failed for {username}: {error_message or 'Unknown error'}")
    
    @staticmethod
    def track_operation_result(operation: str, username: str, success: bool, execution_time: float, 
                              status_code: int = 200, error_message: Optional[str] = None):
        """Track the result of a user settings operation."""
        # Set Sentry metrics
        if SENTRY_AVAILABLE:
            sentry_sdk.set_measurement("execution_time", execution_time)
            sentry_sdk.set_measurement("status_code", status_code)
            sentry_sdk.set_tag("operation_success", str(success))
            sentry_sdk.set_tag("http_status", status_code)
            
            context = {"operation": operation, "username": username, "success": success, 
                      "execution_time": execution_time, "status_code": status_code, "timestamp": time.time()}
            if error_message:
                context["error_message"] = error_message
            sentry_sdk.set_context("operation_result", context)
            
            # Determine log level and capture message
            log_level = UserSettingsSentryMonitor._get_log_level_for_execution_time(execution_time)
            success_msg = f"User settings {operation} completed in {execution_time:.3f}s for user {username}"
            failure_msg = f"User settings {operation} failed for user {username}: {error_message or 'Unknown error'}"
            capture_message(success_msg if success else failure_msg, level=log_level)
        
        # Local logging with performance warnings
        UserSettingsSentryMonitor._log_local_operation_result(operation, username, success, execution_time, error_message)


def _track_span_completion(span, execution_time: float, status: str, operation_name: str, 
                          component: str, exception: Optional[Exception] = None):
    """Helper to track span completion with consistent error/success handling."""
    if not SENTRY_AVAILABLE or not span:
        return
    
    span.set_data("execution_time", execution_time)
    span.set_data("status", status)
    
    if status == "success":
        UserSettingsSentryMonitor.add_breadcrumb(
            f"Completed {operation_name} in {execution_time:.3f}s",
            category=f"user_settings.{component}", level="info"
        )
    else:
        error_type = type(exception).__name__ if exception else "Unknown"
        error_msg = str(exception) if exception else "Unknown error"
        
        span.set_data("error_type", error_type)
        sentry_sdk.set_context("error_context", {
            "operation": operation_name, "component": component,
            "execution_time": execution_time, "error_message": error_msg
        })
        UserSettingsSentryMonitor.add_breadcrumb(
            f"Error in {operation_name}: {error_msg}",
            category=f"user_settings.{component}", level="error"
        )
        if exception:
            capture_exception(exception)


def _execute_without_sentry(operation_name: str, username: str, func, args, kwargs):
    """Execute function with basic logging when Sentry is unavailable."""
    logger.debug(f"⏱️ Starting {operation_name} for user: {username}")
    start_time = time.time()
    
    try:
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        status_code = result.status_code if isinstance(result, JsonResponse) else 200
        is_success = 200 <= status_code < 300
        
        logger.info(f"{'✅' if is_success else '❌'} {operation_name} completed in {execution_time:.3f}s "
                   f"[user={username}, status={status_code}]")
        return result
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"❌ {operation_name} failed after {execution_time:.3f}s "
                    f"[user={username}, error={type(e).__name__}: {str(e)}]")
        raise


def _execute_with_sentry(operation_name: str, username: str, func, args, kwargs, request, transaction):
    """Execute function with full Sentry monitoring."""
    start_time = time.time()
    
    # Set transaction context
    transaction.set_tag("operation", operation_name)
    transaction.set_tag("username", username)
    transaction.set_tag("module", UserSettingsSentryMonitor.MODULE)
    transaction.set_context("request_info", {
        "method": request.method if request else "unknown",
        "path": request.path if request and hasattr(request, 'path') else "unknown",
    })
    
    logger.info(f"📊 Transaction started for user: {username}, operation: {operation_name}")
    
    try:
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        status_code = result.status_code if isinstance(result, JsonResponse) else 200
        is_success = 200 <= status_code < 300
        
        transaction.set_status("ok" if is_success else "error")
        UserSettingsSentryMonitor.track_operation_result(
            operation=operation_name, username=username, success=is_success,
            execution_time=execution_time, status_code=status_code
        )
        sentry_sdk.flush(timeout=2.0)
        logger.info(f"📤 Flushed transaction to Sentry for: {operation_name}")
        return result
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"❌ Exception in {operation_name}: {type(e).__name__}: {str(e)}")
        
        capture_exception(e)
        transaction.set_status("internal_error")
        UserSettingsSentryMonitor.track_operation_result(
            operation=operation_name, username=username, success=False,
            execution_time=execution_time, status_code=500,
            error_message=f"{type(e).__name__}: {str(e)}"
        )
        sentry_sdk.flush(timeout=2.0)
        raise


def track_user_settings_transaction(operation_name: str):
    """
    Decorator to track user settings operations with Sentry.
    
    Monitors:
    - Function execution time
    - Success/failure status
    - Custom tags for operation context
    - Automatic error capture
    - Performance warnings for slow operations
    
    Args:
        operation_name: Name of the operation (e.g., "change_password", "delete_account")
    
    Usage:
        @track_user_settings_transaction("change_password")
        def change_password(request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = args[0] if args else None
            username = request.session.get('username', 'unknown') if request and hasattr(request, 'session') else 'unknown'
            
            # Execute with basic logging if Sentry is not available
            if not SENTRY_AVAILABLE:
                return _execute_without_sentry(operation_name, username, func, args, kwargs)
            
            # Execute with full Sentry monitoring
            logger.info(f"🔍 Starting Sentry transaction for: {operation_name}")
            UserSettingsSentryMonitor.set_operation_context(operation_name, username)
            UserSettingsSentryMonitor.add_breadcrumb(
                f"Starting {operation_name}",
                category=f"user_settings.{UserSettingsSentryMonitor.COMPONENT_VIEW}",
                level="info", data={"function": func.__name__, "username": username}
            )
            
            with start_transaction(op="user_settings", name=f"user_settings.{operation_name}") as transaction:
                return _execute_with_sentry(operation_name, username, func, args, kwargs, request, transaction)
        return wrapper
    return decorator

def track_service_operation(operation_name: str):
    """
    Decorator to track service layer operations with Sentry spans.
    
    Creates a child span within the parent transaction to measure
    service-level performance separately from view logic.
    
    Args:
        operation_name: Name of the service operation
    
    Usage:
        @track_service_operation("password_change")
        def change_password(self, user, new_password):
            ...       
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # If Sentry is not available, execute with basic logging
            if not SENTRY_AVAILABLE:
                logger.debug(f"⏱️ Starting service operation: {operation_name}")
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    is_success = getattr(result, 'success', True)
                    
                    logger.info(
                        f"{'✅' if is_success else '❌'} Service {operation_name} completed in {execution_time:.3f}s"
                    )
                    
                    return result
                except Exception as e:
                    execution_time = time.time() - start_time
                    logger.error(
                        f"❌ Service {operation_name} failed after {execution_time:.3f}s "
                        f"[error={type(e).__name__}: {str(e)}]"
                    )
                    raise
            
            # Sentry is available - add breadcrumb
            UserSettingsSentryMonitor.add_breadcrumb(
                f"Starting service operation: {operation_name}",
                category=f"user_settings.{UserSettingsSentryMonitor.COMPONENT_SERVICE}",
                level="info",
                data={"function": func.__name__}
            )
                
            # Create a span for this service operation
            with start_span(
                op="service.user_settings",
                description=f"service.{operation_name}"
            ) as span:
                start_time = time.time()
                
                # Set initial span tags
                span.set_tag("operation", operation_name)
                span.set_tag("component", UserSettingsSentryMonitor.COMPONENT_SERVICE)
                
                try:
                    # Execute the service method
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # Determine success from result object
                    is_success = getattr(result, 'success', True)
                    
                    # Track completion
                    _track_span_completion(
                        span, 
                        execution_time, 
                        "success" if is_success else "error",
                        operation_name, 
                        UserSettingsSentryMonitor.COMPONENT_SERVICE
                    )
                    
                    logger.debug(
                        f"{'✅' if is_success else '⚠️'} Service operation '{operation_name}' completed in {execution_time:.3f}s"
                    )
                    
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    
                    # Track error completion
                    _track_span_completion(
                        span,
                        execution_time,
                        "error",
                        operation_name,
                        UserSettingsSentryMonitor.COMPONENT_SERVICE,
                        e
                    )
                    
                    logger.error(
                        f"❌ Service operation '{operation_name}' failed after {execution_time:.3f}s "
                        f"[error={type(e).__name__}: {str(e)}]"
                    )
                    
                    # Re-raise to maintain original error handling
                    raise
                    
        return wrapper
    return decorator


def monitor_user_settings_function(operation_name: str, component: str = UserSettingsSentryMonitor.COMPONENT_VIEW):
    """
    Decorator to monitor individual user settings functions with detailed tracking.
    
    Usage:
        @monitor_user_settings_function("validate_password", "validation")
        def validate_password(password):
            # function code
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Basic logging when Sentry is not available
            if not SENTRY_AVAILABLE:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    logger.debug(f"✅ {operation_name} completed in {execution_time:.3f}s")
                    return result
                except Exception as e:
                    execution_time = time.time() - start_time
                    logger.error(f"❌ {operation_name} failed after {execution_time:.3f}s: {str(e)}")
                    raise
            
            # Add breadcrumb
            UserSettingsSentryMonitor.add_breadcrumb(
                f"Starting {operation_name}",
                category=f"user_settings.{component}",
                level="info",
                data={"function": func.__name__, "args_count": len(args)}
            )
            
            # Start performance tracking
            with start_span(op=f"user_settings.{component}", description=operation_name) as span:
                # Add tags
                span.set_tag("module", UserSettingsSentryMonitor.MODULE)
                span.set_tag("component", component)
                span.set_tag("operation", operation_name)
                
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # Track success
                    _track_span_completion(span, execution_time, "success", operation_name, component)
                    
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    
                    # Track error
                    _track_span_completion(span, execution_time, "error", operation_name, component, e)
                    
                    # Re-raise
                    raise
        
        return wrapper
    return decorator


def capture_user_event(event_name: str, user_data: dict, extra_data: dict = None):
    """
    Helper function to capture custom user events in Sentry.
    
    Args:
        event_name: Name of the event (e.g., "password_changed", "account_deleted")
        user_data: Dictionary containing user information
        extra_data: Optional additional context data
    """
    if not SENTRY_AVAILABLE:
        logger.debug(f"📊 Event: {event_name} for user {user_data.get('username', 'unknown')}")
        return
    
    # Set user context
    sentry_sdk.set_context("user_event", {
        "event": event_name,
        "timestamp": time.time(),
        **user_data,
        **(extra_data or {})
    })
    
    # Add breadcrumb
    sentry_sdk.add_breadcrumb(
        category="user_event",
        message=event_name,
        level="info",
        data={
            **user_data,
            **(extra_data or {})
        }
    )
    
    logger.info(f"📊 Captured user event in Sentry: {event_name} for user {user_data.get('username', 'unknown')}")


class UserSettingsOperationMonitor:
    """Monitor individual user settings operations with progress and state tracking."""
    
    def __init__(self, operation_id: str, operation_type: str, username: str):
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.username = username
        self.start_time = time.time()
        
        if SENTRY_AVAILABLE:
            # Set operation context and tags
            tags = {
                "operation_id": operation_id,
                "operation_type": operation_type,
                "username": username
            }
            context = {
                "operation_id": operation_id,
                "operation_type": operation_type,
                "username": username,
                "started_at": self.start_time,
                "module": UserSettingsSentryMonitor.MODULE
            }
            UserSettingsSentryMonitor._set_context_and_tags("operation_monitor", context, tags)
        
        UserSettingsSentryMonitor.add_breadcrumb(
            f"Operation started: {operation_id}",
            category="operation",
            level="info",
            data={"operation_type": operation_type, "username": username}
        )
        
        logger.info(f"🎬 Started monitoring operation: {operation_type} (ID: {operation_id}) for user: {username}")
    
    def record_step(self, step_name: str, step_data: Optional[Dict] = None):
        """Record a step in the operation."""
        elapsed_time = time.time() - self.start_time
        
        if SENTRY_AVAILABLE:
            sentry_sdk.set_measurement(f"step_{step_name}_time", elapsed_time)
        
        UserSettingsSentryMonitor.add_breadcrumb(
            f"Operation step: {step_name}",
            category="operation.step",
            level="info",
            data={
                "step": step_name,
                "elapsed_time": elapsed_time,
                **(step_data or {})
            }
        )
        
        logger.debug(f"📝 Step '{step_name}' completed at {elapsed_time:.3f}s for operation {self.operation_id}")
    
    def complete(self, success: bool = True, result_data: Optional[Dict] = None, error_message: Optional[str] = None):
        """Mark operation as completed."""
        execution_time = time.time() - self.start_time
        
        if SENTRY_AVAILABLE:
            sentry_sdk.set_measurement("operation_duration", execution_time)
            sentry_sdk.set_tag("operation_status", "success" if success else "failed")
        
        level = "info" if success else "error"
        status = "success" if success else "failed"
        
        UserSettingsSentryMonitor.add_breadcrumb(
            f"Operation completed: {self.operation_id} ({status})",
            category="operation",
            level=level,
            data={
                "execution_time": execution_time,
                "result": result_data or {},
                "error_message": error_message
            }
        )
        
        # Track the final result
        UserSettingsSentryMonitor.track_operation_result(
            operation=self.operation_type,
            username=self.username,
            success=success,
            execution_time=execution_time,
            status_code=200 if success else 500,
            error_message=error_message
        )
        
        if success:
            logger.info(
                f"✅ Operation '{self.operation_type}' (ID: {self.operation_id}) completed successfully "
                f"in {execution_time:.3f}s for user: {self.username}"
            )
        else:
            logger.error(
                f"❌ Operation '{self.operation_type}' (ID: {self.operation_id}) failed "
                f"after {execution_time:.3f}s for user: {self.username}. Error: {error_message}"
            )
        
        if SENTRY_AVAILABLE:
            capture_message(
                f"User settings operation {self.operation_id} completed in {execution_time:.3f}s",
                level=level
            )

