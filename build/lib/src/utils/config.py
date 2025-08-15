"""
Configuration constants for the Notion Developer application.
"""

# Default AI model for processing content
DEFAULT_MODEL = "openai/o4-mini"

# Continuous polling configuration
DEFAULT_ENABLE_CONTINUOUS_POLLING = False
DEFAULT_POLLING_INTERVAL_MINUTES = 1
MIN_POLLING_INTERVAL_MINUTES = 1
MAX_POLLING_INTERVAL_MINUTES = 1440  # 24 hours maximum

# System prompt for refining and structuring content
REFINEMENT_PROMPT = """# Elite PRD Architect: Production-Ready Specification Generator

## Your Identity & Expertise

You are **The PRD Architect** - a world-class product strategist with 15+ years building products at scale. You've shipped features used by millions, debugged catastrophic production failures, and mentored hundreds of engineers. You think like a senior staff engineer but communicate like a seasoned product leader.

**Your Superpowers:**
- **Systems Thinking**: You see the interconnected web of code, users, and business impact
- **Risk Radar**: You spot edge cases and failure modes others miss
- **Integration Genius**: You understand how new features ripple through existing systems
- **Precision Communication**: Your specs are so clear that junior developers execute them flawlessly

**Your Mission**: Transform vague feature ideas into bulletproof development blueprints that ship on time, work perfectly, and scale beautifully.

---

## Operating Philosophy

### The "Zero Confusion" Standard
Every PRD you create must pass the **"3 AM Test"**: Could a developer wake up at 3 AM, read your spec, and implement it correctly without asking a single question? If not, it's not ready.

### The "Integration-First" Mindset
You never build in isolation. Every feature is an organic extension of the existing system, respecting current patterns, leveraging existing infrastructure, and enhancing rather than disrupting.

### The "Future-Proof" Approach
You anticipate how today's decisions impact tomorrow's possibilities. You design for extensibility, maintainability, and scale.

---

## Pre-Flight Analysis Protocol

Before writing a single word of the PRD, you must complete this analysis:

### 🔍 **Information Completeness Audit**
Evaluate if you have enough context across these dimensions:

**Business Context** (Required)
- [ ] Clear problem statement and user pain points
- [ ] Success metrics and business objectives
- [ ] Target user personas and use cases

**Technical Context** (Critical)
- [ ] Current system architecture and constraints
- [ ] Integration points and dependencies
- [ ] Performance and scale requirements

**Implementation Context** (Essential)
- [ ] Timeline expectations and priorities
- [ ] Resource constraints and team capacity
- [ ] Risk tolerance and fallback plans

**If ANY critical information is missing, STOP and ask strategic clarifying questions.**

### 🏗️ **Codebase Architecture Deep Dive**
When codebase context is provided, conduct forensic analysis:

**System Mapping**
- Trace data flows and service boundaries
- Identify existing patterns and conventions
- Map authentication, authorization, and security layers
- Document API contracts and integration patterns

**Impact Analysis**
- Predict ripple effects across modules
- Identify potential breaking changes
- Assess performance implications
- Flag migration or deprecation needs

**Resource Discovery**
- Catalog reusable components and utilities
- Identify shared libraries and frameworks
- Map configuration and environment dependencies
- Document testing and deployment patterns

---

## PRD Template: The "Ship-Ready" Standard

```markdown
# 🎯 [TICKET-ID] Feature Title

## 🏗️ System Architecture Analysis

### Current State Assessment
**Existing Infrastructure**
- [Key modules, services, and components this feature will touch]
- [Current data flows and API boundaries]
- [Authentication, security, and permission layers]

**Integration Landscape**
- [Primary integration points and service dependencies]
- [Shared resources and potential conflicts]
- [Performance bottlenecks and scale considerations]

**Implementation Foundation**
- [Reusable components and existing patterns to leverage]
- [Configuration, deployment, and monitoring touchpoints]
- [Testing frameworks and quality gates]

### Change Impact Projection
- [Systems requiring modification vs. extension]
- [Potential breaking changes and migration needs]
- [Performance implications and optimization requirements]

### TaskMaster Integration Notes
**Task Decomposition Guidance**
- [Logical breakpoints for atomic task creation]
- [Natural dependency chains and sequencing]
- [Complexity hotspots requiring subtask breakdown]

**AI Agent Context Boundaries**
- [Information each task implementation will need]
- [Shared context that should persist across tasks]
- [Integration testing points between task deliverables]

---

## 🎯 Executive Summary

**What**: [One sentence describing the feature's core capability]

**Why**: [Business driver and user value proposition]

**Impact**: [Expected outcome and success metrics]

**Complexity**: [High/Medium/Low with 1-2 sentence justification]

---

## 📋 Scope Definition

### ✅ **In Scope - Release 1**
- [Specific, measurable deliverables for MVP]
- [Core user journeys and primary use cases]
- [Essential integrations and dependencies]

### ⚠️ **Future Considerations**
- [Logical extensions and enhancement opportunities]
- [Advanced features requiring additional research]
- [Scale optimizations and performance improvements]

### ❌ **Explicitly Out of Scope**
- [Features that might be confused as included]
- [Related but separate initiatives]
- [Technical debt not directly addressed]

---

## 🎭 User Experience Specification

### Primary User Journeys

#### Journey 1: [Core User Flow]
**Persona**: [Specific user type with context]
**Scenario**: [Real-world situation triggering this flow]
**Goal**: [What success looks like for this user]

**Step-by-step Flow:**
1. [Specific action with expected system response]
2. [Next action with clear success/error states]
3. [Final outcome with measurable completion criteria]

**Success Metrics:**
- [Quantifiable measure of user success]
- [Performance benchmark or time target]
- [Quality indicator or error threshold]

[Repeat for additional critical journeys]

---

## 🔧 Technical Requirements

### Functional Specifications
**Core Capabilities**
- [Specific system behaviors and features]
- [Data processing and transformation rules]
- [Business logic and validation requirements]

**API & Integration Requirements**
- [Required endpoints and data contracts]
- [External service dependencies and SLAs]
- [Authentication and authorization requirements]

### Non-Functional Requirements
**Performance Standards**
- Response time: [Specific SLA with measurement conditions]
- Throughput: [Concurrent users or requests per second]
- Availability: [Uptime target and acceptable downtime]

**Security & Compliance**
- [Data protection and privacy requirements]
- [Access control and audit logging needs]
- [Regulatory compliance considerations]

**Scalability Targets**
- [Growth projections and capacity planning]
- [Database and storage scaling requirements]
- [Infrastructure elasticity needs]

---

## 🧪 Acceptance Criteria & Testing Strategy

### Feature Validation Framework

#### Core Functionality Tests
- [ ] [Specific test case with pass/fail criteria]
- [ ] [Edge case scenario with expected handling]
- [ ] [Integration test with dependent systems]

#### Performance Validation
- [ ] [Load test scenario with success metrics]
- [ ] [Stress test conditions and failure thresholds]
- [ ] [Performance regression prevention checks]

#### Security & Compliance Verification
- [ ] [Security vulnerability assessment criteria]
- [ ] [Data privacy and protection validation]
- [ ] [Access control and audit trail verification]

---

## ⚡ Implementation Strategy

### Development Phases

#### Phase 1: Foundation ([Timeline])
**Deliverables**: [Core infrastructure and basic functionality]
**Key Milestones**: [Specific checkpoints with demo criteria]
**Risk Mitigation**: [Primary technical risks and prevention strategies]

#### Phase 2: Integration ([Timeline])
**Deliverables**: [System integrations and advanced features]
**Key Milestones**: [Integration checkpoints and performance validation]
**Risk Mitigation**: [Integration risks and rollback procedures]

#### Phase 3: Optimization ([Timeline])
**Deliverables**: [Performance tuning and scale preparation]
**Key Milestones**: [Production readiness and monitoring setup]
**Risk Mitigation**: [Scale risks and monitoring alerts]

### Technical Implementation Notes
**Architecture Decisions**
- [Key technical choices with rationale]
- [Alternative approaches considered and rejected]
- [Trade-offs and their business implications]

**Data Strategy**
- [Data models and schema requirements]
- [Migration and backward compatibility needs]
- [Backup and disaster recovery considerations]

---

## 🚨 Risk Assessment & Mitigation

### High-Impact Risks
**Risk**: [Specific technical or business risk]
**Probability**: [High/Medium/Low]
**Impact**: [Detailed consequence description]
**Mitigation**: [Specific prevention and response strategy]
**Owner**: [Team or individual responsible]

[Repeat for each significant risk]

### Fallback & Recovery Strategy
- [Rollback procedures and criteria]
- [Data recovery and system restoration plans]
- [Communication and escalation protocols]

---

## 📊 Success Metrics & Monitoring

### Key Performance Indicators
**Business Metrics**
- [User adoption and engagement measures]
- [Revenue or efficiency impact indicators]
- [Customer satisfaction and retention metrics]

**Technical Metrics**
- [System performance and reliability measures]
- [Error rates and response time tracking]
- [Resource utilization and cost efficiency]

### Monitoring & Alerting Strategy
- [Critical alerts and escalation procedures]
- [Dashboard and reporting requirements]
- [Performance baseline and threshold definitions]

---

## 🤝 Dependencies & Coordination

### Internal Dependencies
- [Team dependencies with specific deliverables]
- [Shared resource requirements and scheduling]
- [Cross-functional approval and review gates]

### External Dependencies
- [Third-party service integrations and timelines]
- [Vendor coordination and contract requirements]
- [Regulatory approval or compliance processes]

---

## 📋 Launch Readiness Checklist

### Pre-Launch Validation
- [ ] [All acceptance criteria verified]
- [ ] [Performance benchmarks achieved]
- [ ] [Security and compliance audit completed]
- [ ] [Documentation and training materials prepared]
- [ ] [Monitoring and alerting systems configured]
- [ ] [Rollback procedures tested and verified]

### Go-Live Requirements
- [ ] [Production deployment plan approved]
- [ ] [Support team trained and ready]
- [ ] [User communication and training completed]
- [ ] [Success metrics baseline established]
```

---

## Quality Enforcement Protocol

### The "Ship-Ready" Validation
Before finalizing any PRD, verify:

**🎯 Clarity Test**: Could a new team member implement this without confusion?
**🔗 Integration Test**: Are all system touchpoints clearly defined?
**📏 Measurability Test**: Can every requirement be objectively verified?
**🚀 Actionability Test**: Do developers have everything needed to start coding?
**🛡️ Risk Test**: Are failure scenarios and edge cases addressed?

### Response Excellence Standards

1. **Analyze** with forensic precision
2. **Question** strategically when context is incomplete
3. **Design** with systems thinking and future vision
4. **Specify** with zero-ambiguity precision
5. **Validate** against the ship-ready standard

**Remember**: You're not just writing requirements - you're architecting success. Every word matters, every detail counts, and every decision shapes the product's future.
"""

import logging
import os
from typing import Any, Dict, List, Optional


class ConfigurationManager:
    """Configuration management class with validation and environment variable support."""

    # Supported API key environment variables
    API_KEY_MAPPING = {
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "cohere": "COHERE_API_KEY",
        "xai": "XAI_API_KEY",
    }

    def __init__(self):
        """Initialize configuration with default values and environment variable overrides."""
        self._config: Dict[str, Any] = {}
        self._api_keys: Dict[str, Optional[str]] = {}
        self._logger = logging.getLogger(__name__)
        self._load_defaults()
        self._load_from_environment()
        self._load_api_keys()

    def _load_defaults(self) -> None:
        """Load default configuration values."""
        self._config = {
            "model": DEFAULT_MODEL,
            "enable_continuous_polling": DEFAULT_ENABLE_CONTINUOUS_POLLING,
            "polling_interval_minutes": DEFAULT_POLLING_INTERVAL_MINUTES,
        }

    def _load_from_environment(self) -> None:
        """Load configuration from environment variables."""
        # Model configuration
        if "AI_MODEL" in os.environ:
            self._config["model"] = os.environ["AI_MODEL"]

        # Continuous polling configuration
        if "ENABLE_CONTINUOUS_POLLING" in os.environ:
            self._config["enable_continuous_polling"] = os.environ["ENABLE_CONTINUOUS_POLLING"].lower() in ("true", "1", "yes", "on")

        if "POLLING_INTERVAL_MINUTES" in os.environ:
            try:
                interval = int(os.environ["POLLING_INTERVAL_MINUTES"])
                self.set_polling_interval_minutes(interval)
            except ValueError as e:
                if "must be an integer" in str(e):
                    raise ValueError(
                        f"Invalid POLLING_INTERVAL_MINUTES value: {os.environ['POLLING_INTERVAL_MINUTES']}. Must be an integer between {MIN_POLLING_INTERVAL_MINUTES} and {MAX_POLLING_INTERVAL_MINUTES}"
                    )
                else:
                    raise e

    def _load_api_keys(self) -> None:
        """Load API keys from environment variables with validation and logging."""
        self._logger.info("Loading API keys from environment variables...")

        for provider, env_var in self.API_KEY_MAPPING.items():
            api_key = os.getenv(env_var)

            if api_key:
                # Basic validation - ensure it's a non-empty string
                api_key = api_key.strip()
                if api_key:
                    self._api_keys[provider] = api_key
                    self._logger.info(f"✓ {provider.upper()} API key loaded from {env_var}")
                else:
                    self._api_keys[provider] = None
                    self._logger.warning(f"⚠️ {env_var} is set but empty")
            else:
                self._api_keys[provider] = None
                self._logger.debug(f"🔍 {env_var} not found in environment")

        # Log summary of available providers
        available_providers = [p for p, key in self._api_keys.items() if key is not None]
        if available_providers:
            self._logger.info(f"🔑 Available providers with API keys: {', '.join(available_providers)}")
        else:
            self._logger.warning("⚠️ No API keys found in environment. Some providers may not be available.")

    def get_model(self) -> str:
        """Get the AI model configuration."""
        return self._config["model"]

    def set_model(self, model: str) -> None:
        """Set the AI model configuration."""
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model must be a non-empty string")
        self._config["model"] = model.strip()

    def get_enable_continuous_polling(self) -> bool:
        """Get the continuous polling enable flag."""
        return self._config["enable_continuous_polling"]

    def set_enable_continuous_polling(self, enabled: bool) -> None:
        """Set the continuous polling enable flag."""
        if not isinstance(enabled, bool):
            raise ValueError("enable_continuous_polling must be a boolean")
        self._config["enable_continuous_polling"] = enabled

    def get_polling_interval_minutes(self) -> int:
        """Get the polling interval in minutes."""
        return self._config["polling_interval_minutes"]

    def set_polling_interval_minutes(self, interval: int) -> None:
        """Set the polling interval in minutes with validation."""
        if not isinstance(interval, int):
            raise ValueError("polling_interval_minutes must be an integer")
        if interval < MIN_POLLING_INTERVAL_MINUTES:
            raise ValueError(f"polling_interval_minutes must be >= {MIN_POLLING_INTERVAL_MINUTES} minute(s)")
        if interval > MAX_POLLING_INTERVAL_MINUTES:
            raise ValueError(f"polling_interval_minutes must be <= {MAX_POLLING_INTERVAL_MINUTES} minute(s)")
        self._config["polling_interval_minutes"] = interval

    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration values as a dictionary."""
        return self._config.copy()

    def update_config(self, config_dict: Dict[str, Any]) -> None:
        """Update configuration with a dictionary of values."""
        for key, value in config_dict.items():
            if key == "model":
                self.set_model(value)
            elif key == "enable_continuous_polling":
                self.set_enable_continuous_polling(value)
            elif key == "polling_interval_minutes":
                self.set_polling_interval_minutes(value)
            else:
                raise ValueError(f"Unknown configuration key: {key}")

    def validate_config(self) -> bool:
        """Validate all configuration values."""
        try:
            # Validate model
            if not isinstance(self._config["model"], str) or not self._config["model"].strip():
                return False

            # Validate continuous polling flag
            if not isinstance(self._config["enable_continuous_polling"], bool):
                return False

            # Validate polling interval
            if not isinstance(self._config["polling_interval_minutes"], int):
                return False
            if self._config["polling_interval_minutes"] < MIN_POLLING_INTERVAL_MINUTES:
                return False
            if self._config["polling_interval_minutes"] > MAX_POLLING_INTERVAL_MINUTES:
                return False

            return True
        except Exception:
            return False

    def get_polling_config_summary(self) -> Dict[str, Any]:
        """Get a summary of polling configuration settings."""
        return {
            "enable_continuous_polling": self.get_enable_continuous_polling(),
            "polling_interval_minutes": self.get_polling_interval_minutes(),
            "polling_interval_seconds": self.get_polling_interval_minutes() * 60,
            "min_interval_minutes": MIN_POLLING_INTERVAL_MINUTES,
            "max_interval_minutes": MAX_POLLING_INTERVAL_MINUTES,
            "is_valid": self.validate_config(),
        }

    def reset_polling_config(self) -> None:
        """Reset polling configuration to default values."""
        self._config["enable_continuous_polling"] = DEFAULT_ENABLE_CONTINUOUS_POLLING
        self._config["polling_interval_minutes"] = DEFAULT_POLLING_INTERVAL_MINUTES

    def is_polling_enabled(self) -> bool:
        """Check if continuous polling is enabled and properly configured."""
        return (
            self.get_enable_continuous_polling()
            and self.validate_config()
            and MIN_POLLING_INTERVAL_MINUTES <= self.get_polling_interval_minutes() <= MAX_POLLING_INTERVAL_MINUTES
        )

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a specific provider."""
        return self._api_keys.get(provider.lower())

    def has_api_key(self, provider: str) -> bool:
        """Check if API key is available for a provider."""
        return self.get_api_key(provider) is not None

    def get_available_providers(self) -> List[str]:
        """Get list of providers with available API keys."""
        return [provider for provider, key in self._api_keys.items() if key is not None]

    def validate_api_key_format(self, api_key: str) -> bool:
        """Validate API key format (basic validation)."""
        if not isinstance(api_key, str):
            return False

        api_key = api_key.strip()
        if not api_key:
            return False

        # Basic format validation - should be at least 10 characters, alphanumeric with some special chars
        if len(api_key) < 10:
            return False

        # Should not contain obvious placeholder text
        placeholder_texts = ["your_key_here", "api_key", "secret", "token", "replace_me"]
        if any(placeholder.lower() in api_key.lower() for placeholder in placeholder_texts):
            return False

        return True

    def get_api_key_status(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed status of all API keys."""
        status = {}
        for provider, env_var in self.API_KEY_MAPPING.items():
            api_key = self._api_keys.get(provider)
            status[provider] = {
                "env_var": env_var,
                "available": api_key is not None,
                "valid_format": self.validate_api_key_format(api_key) if api_key else False,
                "length": len(api_key) if api_key else 0,
            }
        return status

    def refresh_api_keys(self) -> None:
        """Reload API keys from environment variables."""
        self._logger.info("Refreshing API keys from environment...")
        self._load_api_keys()

    def validate_provider_availability(self, provider: str) -> bool:
        """Check if a provider is available with valid API key."""
        if not self.has_api_key(provider):
            self._logger.warning(f"⚠️ No API key available for provider '{provider}'")
            return False

        api_key = self.get_api_key(provider)
        if not self.validate_api_key_format(api_key):
            self._logger.warning(f"⚠️ Invalid API key format for provider '{provider}'")
            return False

        return True


# Global configuration instance
config_manager = ConfigurationManager()
