#!/usr/bin/env python3
"""
Security Validator Module

Implements comprehensive input validation and security safeguards for the AI provider system.
Handles input sanitization, API key security, rate limiting, and injection attack prevention.
"""

import re
import logging
import time
import hashlib
import secrets
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class SecurityViolation(Exception):
    """Raised when a security violation is detected"""
    pass


class ValidationLevel(str, Enum):
    """Security validation levels"""
    STRICT = "strict"      # Maximum security, may reject valid inputs
    STANDARD = "standard"  # Balanced security and usability  
    PERMISSIVE = "permissive"  # Minimal validation for development


@dataclass
class ValidationResult:
    """Result of security validation"""
    is_valid: bool
    sanitized_input: Optional[str] = None
    violations: List[str] = field(default_factory=list)
    risk_level: str = "low"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimit:
    """Rate limiting configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_allowance: int = 10
    window_size: int = 60  # seconds


class SecurityValidator:
    """
    Comprehensive security validator for AI provider system.
    
    Provides input validation, sanitization, API key security,
    rate limiting, and protection against various attack vectors.
    """
    
    # Dangerous patterns that could indicate injection attempts
    INJECTION_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS
        r'javascript\s*:',             # JS injection
        r'on\w+\s*=',                 # Event handlers
        r'<iframe[^>]*>',             # Iframe injection
        r'<object[^>]*>',             # Object injection
        r'<embed[^>]*>',              # Embed injection
        r'\bexec\s*\(',               # Code execution
        r'\beval\s*\(',               # Eval injection
        r'\bsystem\s*\(',             # System calls
        r'__import__\s*\(',           # Python imports
        r'\bopen\s*\(',               # File operations
        r'\.\./',                     # Path traversal
        r'[;\|&`]',                   # Command injection
        r'\$\{.*\}',                  # Variable expansion
        r'<%.*%>',                    # Template injection
        r'\{\{.*\}\}',                # Template injection
    ]
    
    # Sensitive data patterns to never log
    SENSITIVE_PATTERNS = [
        r'sk-[a-zA-Z0-9]{32,}',              # OpenAI API keys
        r'sk-or-[a-zA-Z0-9-]{32,}',          # OpenRouter API keys
        r'sk-ant-[a-zA-Z0-9-]{32,}',         # Anthropic API keys
        r'Bearer\s+[a-zA-Z0-9-_.]+',         # Bearer tokens
        r'[a-fA-F0-9]{32}',                  # MD5 hashes (could be tokens)
        r'[a-fA-F0-9]{64}',                  # SHA256 hashes
        r'password[\s]*[=:]\s*[^\s]+',       # Passwords
        r'token[\s]*[=:]\s*[^\s]+',          # Tokens
        r'secret[\s]*[=:]\s*[^\s]+',         # Secrets
        r'key[\s]*[=:]\s*[^\s]+',            # Keys
    ]
    
    # Allowed characters for different input types
    ALLOWED_CHARS = {
        'model_name': r'^[a-zA-Z0-9/_.-]+$',
        'provider_name': r'^[a-zA-Z0-9_-]+$',
        'content': r'^[\s\S]*$',  # Allow all characters for content
        'system_prompt': r'^[\s\S]*$',  # Allow all characters for prompts
        'alphanumeric': r'^[a-zA-Z0-9]+$',
        'safe_text': r'^[a-zA-Z0-9\s.,!?-]+$'
    }
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        """Initialize security validator with specified validation level"""
        self.validation_level = validation_level
        self.rate_limiters = defaultdict(lambda: defaultdict(deque))
        self.blocked_ips = set()
        self.suspicious_patterns_count = defaultdict(int)
        
        # Compile regex patterns for performance
        self.injection_regex = [re.compile(pattern, re.IGNORECASE | re.DOTALL) 
                               for pattern in self.INJECTION_PATTERNS]
        self.sensitive_regex = [re.compile(pattern, re.IGNORECASE) 
                               for pattern in self.SENSITIVE_PATTERNS]
        
        logger.info(f"Security validator initialized with {validation_level.value} validation level")
    
    def validate_model_string(self, model_string: str, context: str = "general") -> ValidationResult:
        """
        Validate and sanitize model string input.
        
        Args:
            model_string: Model string to validate
            context: Context for validation (affects strictness)
            
        Returns:
            ValidationResult with validation outcome
        """
        if not isinstance(model_string, str):
            return ValidationResult(
                is_valid=False,
                violations=["Model string must be a string"],
                risk_level="high"
            )
        
        violations = []
        risk_level = "low"
        
        # Check length limits
        if len(model_string) > 100:
            violations.append("Model string too long (>100 characters)")
            risk_level = "medium"
        
        if len(model_string.strip()) == 0:
            violations.append("Model string cannot be empty")
            risk_level = "medium"
        
        # Check for injection patterns
        injection_found = self._check_injection_patterns(model_string)
        if injection_found:
            violations.extend(injection_found)
            risk_level = "high"
        
        # Validate format (provider/model)
        if '/' not in model_string:
            if self.validation_level == ValidationLevel.STRICT:
                violations.append("Model string must contain provider/model format")
                risk_level = "medium"
        else:
            provider, model = model_string.split('/', 1)
            if not re.match(self.ALLOWED_CHARS['provider_name'], provider):
                violations.append("Invalid characters in provider name")
                risk_level = "medium"
            if not re.match(self.ALLOWED_CHARS['model_name'], model):
                violations.append("Invalid characters in model name")
                risk_level = "medium"
        
        # Sanitize
        sanitized = self._sanitize_model_string(model_string)
        
        return ValidationResult(
            is_valid=len(violations) == 0,
            sanitized_input=sanitized,
            violations=violations,
            risk_level=risk_level,
            metadata={"original_length": len(model_string), "sanitized_length": len(sanitized)}
        )
    
    def validate_content(self, content: str, max_length: int = 50000) -> ValidationResult:
        """
        Validate and sanitize content input (prompts, text).
        
        Args:
            content: Content to validate
            max_length: Maximum allowed content length
            
        Returns:
            ValidationResult with validation outcome
        """
        if not isinstance(content, str):
            return ValidationResult(
                is_valid=False,
                violations=["Content must be a string"],
                risk_level="high"
            )
        
        violations = []
        risk_level = "low"
        
        # Check length limits
        if len(content) > max_length:
            violations.append(f"Content too long (>{max_length} characters)")
            risk_level = "medium"
        
        # Check for injection patterns (more permissive for content)
        if self.validation_level in [ValidationLevel.STRICT, ValidationLevel.STANDARD]:
            high_risk_patterns = self._check_high_risk_injection_patterns(content)
            if high_risk_patterns:
                violations.extend(high_risk_patterns)
                risk_level = "high"
        
        # Check for suspicious patterns
        suspicious_count = self._count_suspicious_patterns(content)
        if suspicious_count > 5:  # Threshold for suspicion
            violations.append(f"High number of suspicious patterns detected ({suspicious_count})")
            risk_level = "medium"
        
        # Sanitize (minimal for content to preserve functionality)
        sanitized = self._sanitize_content(content)
        
        return ValidationResult(
            is_valid=len(violations) == 0,
            sanitized_input=sanitized,
            violations=violations,
            risk_level=risk_level,
            metadata={
                "original_length": len(content),
                "sanitized_length": len(sanitized),
                "suspicious_patterns": suspicious_count
            }
        )
    
    def validate_api_key(self, api_key: str, provider: str) -> ValidationResult:
        """
        Validate API key format and security.
        
        Args:
            api_key: API key to validate
            provider: Provider name (openai, openrouter, etc.)
            
        Returns:
            ValidationResult with validation outcome
        """
        if not isinstance(api_key, str):
            return ValidationResult(
                is_valid=False,
                violations=["API key must be a string"],
                risk_level="high"
            )
        
        violations = []
        risk_level = "low"
        
        # Basic format validation
        if len(api_key.strip()) < 10:
            violations.append("API key too short")
            risk_level="high"
        
        if len(api_key) > 200:
            violations.append("API key too long")
            risk_level="medium"
        
        # Provider-specific validation
        if provider.lower() == "openai" and not api_key.startswith("sk-"):
            violations.append("OpenAI API key should start with 'sk-'")
            risk_level="medium"
        
        if provider.lower() == "openrouter" and not api_key.startswith("sk-or-"):
            violations.append("OpenRouter API key should start with 'sk-or-'")
            risk_level="medium"
        
        if provider.lower() == "anthropic" and not api_key.startswith("sk-ant-"):
            violations.append("Anthropic API key should start with 'sk-ant-'")
            risk_level="medium"
        
        # Check for placeholder values
        placeholder_texts = ['your_key_here', 'api_key', 'secret', 'token', 'replace_me', 'example']
        if any(placeholder.lower() in api_key.lower() for placeholder in placeholder_texts):
            violations.append("API key appears to be a placeholder")
            risk_level="high"
        
        # Check character set (should be alphanumeric with some symbols)
        if not re.match(r'^[a-zA-Z0-9\-_]+$', api_key):
            if self.validation_level == ValidationLevel.STRICT:
                violations.append("API key contains invalid characters")
                risk_level="medium"
        
        # Don't return the API key in sanitized_input for security
        return ValidationResult(
            is_valid=len(violations) == 0,
            sanitized_input="[REDACTED]",
            violations=violations,
            risk_level=risk_level,
            metadata={"provider": provider, "key_length": len(api_key)}
        )
    
    def sanitize_for_logging(self, text: str) -> str:
        """
        Sanitize text before logging to remove sensitive information.
        
        Args:
            text: Text to sanitize
            
        Returns:
            Sanitized text safe for logging
        """
        if not isinstance(text, str):
            return str(text)
        
        sanitized = text
        
        # Replace sensitive patterns
        for pattern in self.sensitive_regex:
            sanitized = pattern.sub('[REDACTED]', sanitized)
        
        # Truncate very long text
        if len(sanitized) > 1000:
            sanitized = sanitized[:997] + "..."
        
        return sanitized
    
    def check_rate_limit(self, identifier: str, rate_limit: RateLimit) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limits.
        
        Args:
            identifier: Unique identifier for rate limiting (IP, user, etc.)
            rate_limit: Rate limit configuration
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        current_time = time.time()
        minute_window = int(current_time // 60)
        hour_window = int(current_time // 3600)
        
        # Clean old entries
        self._clean_rate_limit_windows(identifier, current_time)
        
        # Check minute limit
        minute_requests = self.rate_limiters[identifier]["minute"]
        if len(minute_requests) >= rate_limit.requests_per_minute:
            return False, {
                "reason": "minute_limit_exceeded",
                "requests_in_minute": len(minute_requests),
                "limit": rate_limit.requests_per_minute,
                "reset_in_seconds": 60 - (current_time % 60)
            }
        
        # Check hour limit
        hour_requests = self.rate_limiters[identifier]["hour"]
        if len(hour_requests) >= rate_limit.requests_per_hour:
            return False, {
                "reason": "hour_limit_exceeded",
                "requests_in_hour": len(hour_requests),
                "limit": rate_limit.requests_per_hour,
                "reset_in_seconds": 3600 - (current_time % 3600)
            }
        
        # Add request to rate limit tracking
        minute_requests.append(current_time)
        hour_requests.append(current_time)
        
        return True, {
            "requests_in_minute": len(minute_requests),
            "requests_in_hour": len(hour_requests),
            "minute_limit": rate_limit.requests_per_minute,
            "hour_limit": rate_limit.requests_per_hour
        }
    
    def _check_injection_patterns(self, text: str) -> List[str]:
        """Check for injection attack patterns"""
        violations = []
        
        for i, pattern in enumerate(self.injection_regex):
            if pattern.search(text):
                violations.append(f"Potential injection pattern detected: pattern_{i}")
                # Log suspicious activity (with sanitized input)
                logger.warning(f"Injection pattern detected in input: {self.sanitize_for_logging(text[:100])}")
        
        return violations
    
    def _check_high_risk_injection_patterns(self, text: str) -> List[str]:
        """Check only for high-risk injection patterns in content"""
        violations = []
        high_risk_indices = [0, 1, 2, 6, 7, 8]  # Script, JS, events, exec, eval, system
        
        for i in high_risk_indices:
            if i < len(self.injection_regex) and self.injection_regex[i].search(text):
                violations.append(f"High-risk injection pattern detected: pattern_{i}")
        
        return violations
    
    def _count_suspicious_patterns(self, text: str) -> int:
        """Count suspicious patterns in text"""
        count = 0
        for pattern in self.injection_regex:
            count += len(pattern.findall(text))
        return count
    
    def _sanitize_model_string(self, model_string: str) -> str:
        """Sanitize model string"""
        # Remove dangerous characters but preserve provider/model format
        sanitized = re.sub(r'[<>"\';(){}[\]\\]', '', model_string)
        sanitized = sanitized.strip()
        return sanitized
    
    def _sanitize_content(self, content: str) -> str:
        """Sanitize content (minimal to preserve functionality)"""
        # Only remove the most dangerous patterns
        sanitized = content
        
        # Remove script tags
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove javascript: URLs
        sanitized = re.sub(r'javascript\s*:', '', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    def _clean_rate_limit_windows(self, identifier: str, current_time: float):
        """Clean old entries from rate limit windows"""
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        # Clean minute window
        minute_requests = self.rate_limiters[identifier]["minute"]
        while minute_requests and minute_requests[0] < minute_ago:
            minute_requests.popleft()
        
        # Clean hour window
        hour_requests = self.rate_limiters[identifier]["hour"]
        while hour_requests and hour_requests[0] < hour_ago:
            hour_requests.popleft()
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security validator statistics and status"""
        return {
            "validation_level": self.validation_level.value,
            "blocked_ips": len(self.blocked_ips),
            "active_rate_limiters": len(self.rate_limiters),
            "injection_patterns_count": len(self.INJECTION_PATTERNS),
            "sensitive_patterns_count": len(self.SENSITIVE_PATTERNS),
            "suspicious_activity_count": sum(self.suspicious_patterns_count.values())
        }
    
    def block_identifier(self, identifier: str, reason: str = "security_violation"):
        """Block an identifier (IP, user, etc.) from making requests"""
        self.blocked_ips.add(identifier)
        logger.warning(f"Blocked identifier {identifier} for reason: {reason}")
    
    def is_blocked(self, identifier: str) -> bool:
        """Check if an identifier is blocked"""
        return identifier in self.blocked_ips
    
    def unblock_identifier(self, identifier: str):
        """Unblock a previously blocked identifier"""
        self.blocked_ips.discard(identifier)
        logger.info(f"Unblocked identifier {identifier}")


# Global security validator instance
security_validator = SecurityValidator(ValidationLevel.STANDARD)


# Convenience functions
def validate_model_input(model_string: str) -> ValidationResult:
    """Validate model string input"""
    return security_validator.validate_model_string(model_string)


def validate_content_input(content: str) -> ValidationResult:
    """Validate content input"""
    return security_validator.validate_content(content)


def sanitize_log_message(message: str) -> str:
    """Sanitize message for safe logging"""
    return security_validator.sanitize_for_logging(message)


def check_request_rate_limit(identifier: str, requests_per_minute: int = 60) -> Tuple[bool, Dict[str, Any]]:
    """Check rate limit for requests"""
    rate_limit = RateLimit(requests_per_minute=requests_per_minute)
    return security_validator.check_rate_limit(identifier, rate_limit)