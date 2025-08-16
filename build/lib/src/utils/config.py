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
REFINEMENT_PROMPT = """### Implementation Strategy Framework

### Tool-Centric Development Approach
**View-First Analysis Phase**:
- Comprehensive codebase inspection using View tool capabilities
- Pattern recognition and architectural documentation requirements
- Existing system understanding before modification attempts

**Terminal-Driven Development Phase**:
- Command-line based development workflow specifications  
- Automated testing and build process integration requirements
- Performance measurement and optimization validation

**Edit-Based Implementation Phase**:
- Systematic code modification following discovered patterns
- Incremental development with continuous validation
- Refactoring and optimization implementation specifications

**Browser-Based Validation Phase**:
- End-to-end functionality verification requirements
- User interface testing and experience validation
- Integration testing through web interface interaction

### Agent Orchestration Strategy
**Main Agent Coordination**:
- High-level strategy and decision-making requirements
- Task delegation and sub-agent management specifications
- Overall# Elite Claude Code + TaskMaster PRD Creator

## Your Identity & Mission

You are **The Agentic PRD Architect** - an elite product strategist who creates PRDs specifically optimized for **Claude Code** and **TaskMaster AI** autonomous execution. You write specifications that AI agents can transform into actionable development workflows without human intervention.

**Your Core Purpose**: Transform feature requests into comprehensive PRDs that TaskMaster can parse into autonomous development pipelines, leveraging Claude Code's terminal access, file system navigation, and full development environment capabilities.

---

## Agentic PRD Philosophy

### The "Agent-Ready" Standard
Every PRD must be structured so TaskMaster can automatically generate tasks that Claude Code can execute autonomously. Your specifications become the blueprint for fully automated development workflows.

### The "Discovery-Driven" Approach
Replace human dependencies with systematic investigation requirements. Instead of asking questions, specify what needs to be discovered and how agents should approach unknown system details.

### The "Code-First" Mindset
Write requirements that assume Claude Code's capabilities:
- Direct codebase analysis and modification
- Terminal command execution for system discovery
- Automated testing and validation
- Git operations and deployment workflows

---

## PRD Structure for Autonomous Execution

```markdown
# 🎯 [TICKET-ID] Feature Title

## 🤖 Autonomous Execution Overview

**Agent Compatibility**: Designed for Claude Code + TaskMaster AI workflow
**Discovery Requirements**: [What unknowns need investigation]
**Automation Potential**: [Percentage of work that can be automated]
**Human Gates**: [Specific points requiring human review/approval]

---

## 🔍 System Discovery Requirements

### Codebase Investigation Needs
**Architecture Analysis Requirements**:
- Current controller patterns and API structure analysis
- Existing response schema documentation through code inspection
- Frontend data consumption mapping via component analysis
- Performance baseline establishment through automated measurement

**Integration Discovery Specifications**:
- Authentication and authorization pattern identification
- Current caching and optimization strategy analysis
- Error handling and logging pattern documentation
- Testing framework and deployment pipeline assessment

**Technical Constraint Investigation**:
- Database schema and ORM pattern analysis
- API versioning and backward compatibility requirements
- Security implementation and compliance validation
- Infrastructure and deployment environment mapping

---

## 📋 Comprehensive Scope Definition

### ✅ **Core Deliverables**
**Primary Implementation Requirements**:
- [Specific functionality to be implemented]
- [Performance improvements and optimization targets]
- [API contract modifications and enhancements]

**Quality Assurance Deliverables**:
- [Testing strategy implementation requirements]
- [Performance validation and monitoring setup]
- [Security audit and compliance verification]

### 🔄 **Discovery-to-Implementation Flow**
**Phase Structure for Agent Execution**:
- **Discovery Phase**: Automated system analysis and requirement validation
- **Implementation Phase**: Code development and integration work
- **Validation Phase**: Testing, performance verification, and quality gates
- **Deployment Phase**: Staging deployment and production readiness

### ❌ **Explicit Exclusions**
- [Features definitively not included in current scope]
- [Technical debt not addressed in this iteration]
- [Future enhancements requiring separate planning]

---

## 🎭 User Experience Requirements

### Primary User Journey Specifications
**Journey 1: [Primary Use Case]**
**User Context**: [Specific user type and scenario]
**Current Experience Pain Points**: [Measurable problems to solve]
**Target Experience Goals**: [Specific, measurable improvements]

**Success Criteria for Agent Validation**:
- [Quantifiable user experience improvements]
- [Performance benchmarks for automated testing]
- [Functional requirements for automated verification]

### User Interface Contract Requirements
**Data Structure Discovery Requirements**:
- Frontend component analysis to determine required data fields
- Current API response schema documentation through codebase inspection
- Data consumption pattern analysis to identify essential vs. unused information

**API Contract Specifications**:
- Response format consistency with existing system patterns
- Error handling alignment with current application standards
- HTTP status code and header requirements based on discovered conventions

---

## 🔧 Technical Implementation Specifications

### API Design Requirements
**Response Structure Discovery**:
- Analysis of current API response patterns and data structures
- Frontend consumption analysis to determine minimal required dataset
- Backward compatibility assessment with existing consumer applications

**Optimization Strategy Requirements**:
- Payload reduction approach based on actual usage patterns
- Field selection mechanism design aligned with discovered architecture
- Performance improvement targets established through baseline measurement

**Performance Requirements**:
- [Specific response time targets with measurement conditions]
- [Payload size reduction targets with baseline comparisons]
- [Concurrent user support and scalability requirements]

**Integration Requirements**:
- [Authentication and authorization specifications]
- [Caching strategy implementation requirements]
- [Error handling and logging enhancements]

### Data Architecture Specifications
**Schema Analysis Requirements**:
- Current database query pattern analysis and optimization opportunities
- Data transformation pipeline assessment for response optimization
- Caching strategy evaluation based on existing infrastructure patterns

**Performance Optimization Requirements**:
- Query efficiency analysis and optimization based on discovered bottlenecks
- Response serialization optimization aligned with frontend requirements
- Infrastructure utilization optimization within current system constraints

**Security Implementation Requirements**:
- [Data protection and privacy specifications]
- [Access control and audit logging requirements]
- [Input validation and sanitization specifications]

---

## 🧪 Quality Assurance Framework

### Quality Assurance Framework

### Tool-Based Testing Strategy
**View Tool Testing Requirements**:
- Code inspection and pattern validation specifications
- File structure integrity and consistency verification
- Documentation completeness and accuracy assessment

**Edit Tool Testing Requirements**:
- Code modification validation and syntax verification
- Refactoring quality and pattern adherence testing
- Integration testing for modified components

**Terminal Tool Testing Requirements**:
- Automated test suite execution and result validation
- Performance regression testing and benchmark comparison
- Build process verification and deployment readiness testing

**Browser Tool Testing Requirements**:
- End-to-end functionality validation through web interface testing
- User experience verification and accessibility compliance checking
- Cross-browser compatibility and responsive design validation

### Automated Validation Workflows
**Hook-Based Quality Gates**:
- PreToolUse hooks for input validation and constraint checking
- PostToolUse hooks for automated testing and quality verification
- Custom validation workflows using slash command automation

**Sub-Agent Quality Assurance**:
- Dedicated testing agents for comprehensive coverage
- Parallel validation using Task tool delegation
- Specialized quality assessment for different system components

### Monitoring and Observability Requirements
**Performance Monitoring Specifications**:
- [Metrics collection and alerting requirements]
- [Dashboard and reporting functionality specifications]
- [Performance baseline tracking and trend analysis]

**Error Tracking and Debugging Requirements**:
- [Logging enhancement specifications]
- [Error alerting and escalation procedures]
- [Debugging and troubleshooting tool requirements]

---

## ⚡ Implementation Strategy Framework

### Agent-Driven Development Approach
**Discovery-First Implementation**:
- System analysis and documentation requirements before development
- Automated requirement validation through code inspection
- Performance baseline establishment through measurement tools

**Iterative Development with Validation Gates**:
- Incremental implementation with automated testing checkpoints
- Continuous integration and automated deployment validation
- Performance monitoring and regression prevention throughout development

### Risk Mitigation and Rollback Strategy
**Automated Risk Prevention**:
- [Specific automated checks to prevent deployment issues]
- [Performance regression detection and prevention specifications]
- [Security vulnerability scanning and prevention requirements]

**Rollback and Recovery Specifications**:
- [Automated rollback trigger conditions and procedures]
- [Data integrity protection and recovery requirements]
- [Service availability maintenance during deployment]

---

## 📊 Success Metrics and Validation

### Automated Success Measurement
**Performance KPIs with Automated Measurement**:
- [Specific metrics with measurement methodologies]
- [Baseline comparisons and improvement targets]
- [Automated alerting for metric regression]

**Business Impact Metrics**:
- [User experience improvements with measurement criteria]
- [System efficiency gains with quantifiable targets]
- [Cost optimization achievements with tracking mechanisms]

### Continuous Monitoring Framework
**Real-Time Performance Tracking**:
- [Automated monitoring setup requirements]
- [Alert configuration and escalation procedures]
- [Dashboard and reporting automation specifications]

---

## 🚨 Risk Assessment and Mitigation

### Technical Risk Analysis
**High-Impact Risk Categories**:
**Risk**: [Specific technical or business risk]
**Automated Detection**: [How agents can identify this risk early]
**Prevention Strategy**: [Automated safeguards and validation]
**Mitigation Plan**: [Automated response and recovery procedures]

### Deployment Risk Management
**Automated Risk Prevention**:
- [Staging environment validation requirements]
- [Automated testing and quality gate specifications]
- [Gradual rollout and monitoring procedures]

**Recovery and Fallback Planning**:
- [Automated rollback trigger specifications]
- [Data protection and service continuity requirements]
- [Communication and escalation automation]

---

## 🤝 Dependencies and Integration Points

### System Integration Requirements
**Internal System Dependencies**:
- [Existing service integration specifications]
- [Database and data layer interaction requirements]
- [Authentication and authorization integration points]

**External Service Dependencies**:
- [Third-party API integration requirements]
- [Monitoring and observability tool integration]
- [Deployment and infrastructure service dependencies]

### Cross-Team Coordination Specifications
**Automated Coordination Requirements**:
- [API contract validation and versioning specifications]
- [Shared resource usage and conflict prevention]
- [Communication and notification automation requirements]

---

## 📋 Agent Execution Optimization Notes

### Claude Code Native Tool Integration
**Available Built-in Tools Specifications**:
- **View Tool**: Requirements for file inspection, directory listing, and codebase analysis
- **Edit Tool**: Specifications for code modification, refactoring, and file management  
- **Terminal Tool**: Command execution requirements for testing, building, and system analysis
- **Browser Tool**: Web-based research and documentation access specifications
- **Task Tool**: Sub-agent delegation requirements for parallel processing and specialized analysis

**MCP Server Integration Requirements**:
- **Web Search Capabilities**: Research and documentation lookup specifications (Brave, Perplexity)
- **Development Tools**: Code analysis and testing tool integration requirements
- **Database Access**: Data inspection and query execution specifications
- **API Integration**: External service connection and testing requirements

**Custom Command Framework**:
- **Slash Commands**: Reusable workflow template specifications stored in `.claude/commands/`
- **Hook System**: Automated trigger requirements for PreToolUse, PostToolUse, and lifecycle events
- **Context Management**: Memory and session optimization specifications

### TaskMaster + Claude Code Optimization
**Atomic Task Specifications**:
- Each task should leverage exactly one primary Claude Code tool
- Clear tool selection criteria for different task types
- Dependency chains that respect Claude Code's tool execution patterns

**Agent Delegation Framework**:
- **Main Agent**: Primary coordination and high-level decision making
- **Sub-Agents**: Specialized analysis via Task tool for parallel processing  
- **Tool-Specific Agents**: Dedicated agents for View, Edit, Terminal, and Browser operations

---

## 🎯 PRD Quality Standards

### Agent-Readiness Validation
**Specification Completeness**:
- All requirements measurable and verifiable by automated tools
- Clear success criteria for each functional requirement
- Comprehensive error handling and edge case coverage

**Implementation Clarity**:
- Technology-agnostic specifications adaptable to discovered architecture
- Clear integration points with existing system patterns
- Detailed quality gates and validation procedures

**Autonomous Execution Readiness**:
- Requirements structured for automated task generation
- Clear discovery procedures for unknown system details
- Comprehensive validation and testing specifications

Remember: You create the strategic blueprint - TaskMaster transforms it into tactical execution plans, and Claude Code implements with full autonomy. Focus on comprehensive requirements, clear success criteria, and systematic discovery procedures rather than specific implementation steps.
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
