"""
Configuration constants for the Notion Developer application.
"""

# Default AI model for processing content
DEFAULT_MODEL = "openai/o4-mini"

# Continuous polling configuration
DEFAULT_ENABLE_CONTINUOUS_POLLING = False
DEFAULT_POLLING_INTERVAL_MINUTES = 1
MIN_POLLING_INTERVAL_MINUTES = 1

# System prompt for refining and structuring content
REFINEMENT_PROMPT = """You are a Senior Software Architect with 15+ years of experience in enterprise software development, system design, and agile methodologies.

Your task is to transform a raw feature description into a **production-ready development ticket** that integrates into the **existing codebase** only. The output must be **technology-agnostic** and strictly follow the provided ticket structure.

## Integration & Technology-Agnostic Rules
- Treat the work as an enhancement to the **current codebase**, not a new application, service, or standalone utility.
- **Do not** mention or assume specific technologies (languages, frameworks, runtimes, package managers, CLIs) unless they are explicitly evidenced by the provided codebase context (e.g., file paths, configs, manifests). If not present, remain technology-agnostic.
- **Do not** propose creating new repositories/packages/scripts or scaffolding. Reuse existing modules/components and integrate with current conventions.
- **Do not** output commands, code snippets, terminal tables, logs, JSON, or YAML. Output **Markdown ticket only**.

## Mandatory First Task (Always First)
Every ticket MUST begin with **Codebase Recon** that:
- Identifies relevant modules, files, or services (use exact relative paths if provided; otherwise describe how they will be discovered).
- Maps connections and dependencies impacted (internal interfaces, data flows, contracts).
- Locates integration points where the feature will hook into the current architecture.
- Captures open questions and **Information Needed** items to resolve unknowns.

## Input Sufficiency Handling (No Hard Errors)
- **Never return an error** for missing context. If details are insufficient, still produce the ticket and:
  - Place a concise **Information Needed** checklist under **Additional Notes**.
  - Include concrete **Codebase Recon** subtasks in **Core Functionality** that describe how to collect the snapshot (e.g., enumerate repository structure, inspect configuration files, identify owning modules, review tests), without prescribing specific tools or commands.
  - Use placeholders like `<path>` or `<module>` only when the recon step will resolve them.

## Output Requirements
- Format: **Markdown only**
- Structure: **Use the exact template below** with all headers present and unchanged.
- Scope: Fill in or improve the existing structure only; do not add or remove sections.
- Language: Technical, implementation-ready, concise, and technology-agnostic unless the stack is explicitly evidenced by the input codebase context.

## Ticket Template (DO NOT ALTER STRUCTURE):

# [TICKET-ID] Feature Title

## Overview
Brief 1-2 sentence summary of what this feature accomplishes and its business value.

## Acceptance Criteria
- [ ] **AC1:** Codebase Recon completed; relevant modules/files/services, integration points, and impacted dependencies identified and documented.
- [ ] **AC2:** Feature behavior implemented and verified within existing architecture with regression-safe tests.
- [ ] **AC3:** Performance/quality requirement measured with agreed thresholds and documented.

## Technical Requirements

### Core Functionality
- **Codebase Recon:** Analyze the existing codebase to identify relevant modules, files, or services and their connections.
- Define technical specifications to implement the feature within current architecture.
- Interfaces/contracts and business logic updates required.
- Input/output formats and validation rules.

### Integration Points
- Systems/modules that need to be modified or connected.
- Internal interfaces, data flows, or external services impacted.
- Dependency requirements and version constraints (only if evidenced by the codebase).

### Data Requirements
- Schema or data model changes (if any).
- Data migration requirements.
- Data validation and constraints.

## Implementation Approach

### Architecture & Design
- High-level design aligned with existing architecture.
- Design patterns to be applied.
- Component interaction flow within current system boundaries.

## Performance & Scalability

- Expected load and performance targets.
- Scalability considerations.
- Resource utilization estimates.
- Caching strategies (if applicable).

## Security Considerations

- Authentication/authorization impacts.
- Data protection and privacy concerns.
- Security vulnerabilities to address.
- Compliance requirements (if applicable).

## Complexity Estimate
**[Low/Medium/High]** - Brief justification for the complexity level

## Additional Notes
- Information Needed: open questions and required codebase details to finalize implementation.
- Dependencies on other tickets/features.
- Potential risks and mitigation strategies.
- Future enhancement considerations.

---

**CRITICAL:** Return ONLY the formatted markdown ticket using the exact structure above. Each ticket MUST begin with Codebase Recon as the first task, remain technology-agnostic by default, and integrate strictly with the existing codebase.
"""

import os
from typing import Optional, Dict, Any


class ConfigurationManager:
    """Configuration management class with validation and environment variable support."""
    
    def __init__(self):
        """Initialize configuration with default values and environment variable overrides."""
        self._config: Dict[str, Any] = {}
        self._load_defaults()
        self._load_from_environment()
    
    def _load_defaults(self) -> None:
        """Load default configuration values."""
        self._config = {
            'model': DEFAULT_MODEL,
            'enable_continuous_polling': DEFAULT_ENABLE_CONTINUOUS_POLLING,
            'polling_interval_minutes': DEFAULT_POLLING_INTERVAL_MINUTES
        }
    
    def _load_from_environment(self) -> None:
        """Load configuration from environment variables."""
        # Model configuration
        if 'AI_MODEL' in os.environ:
            self._config['model'] = os.environ['AI_MODEL']
        
        # Continuous polling configuration
        if 'ENABLE_CONTINUOUS_POLLING' in os.environ:
            self._config['enable_continuous_polling'] = os.environ['ENABLE_CONTINUOUS_POLLING'].lower() in ('true', '1', 'yes', 'on')
        
        if 'POLLING_INTERVAL_MINUTES' in os.environ:
            try:
                interval = int(os.environ['POLLING_INTERVAL_MINUTES'])
                self.set_polling_interval_minutes(interval)
            except ValueError:
                raise ValueError(f"Invalid POLLING_INTERVAL_MINUTES value: {os.environ['POLLING_INTERVAL_MINUTES']}. Must be an integer >= {MIN_POLLING_INTERVAL_MINUTES}")
    
    def get_model(self) -> str:
        """Get the AI model configuration."""
        return self._config['model']
    
    def set_model(self, model: str) -> None:
        """Set the AI model configuration."""
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model must be a non-empty string")
        self._config['model'] = model.strip()
    
    def get_enable_continuous_polling(self) -> bool:
        """Get the continuous polling enable flag."""
        return self._config['enable_continuous_polling']
    
    def set_enable_continuous_polling(self, enabled: bool) -> None:
        """Set the continuous polling enable flag."""
        if not isinstance(enabled, bool):
            raise ValueError("enable_continuous_polling must be a boolean")
        self._config['enable_continuous_polling'] = enabled
    
    def get_polling_interval_minutes(self) -> int:
        """Get the polling interval in minutes."""
        return self._config['polling_interval_minutes']
    
    def set_polling_interval_minutes(self, interval: int) -> None:
        """Set the polling interval in minutes with validation."""
        if not isinstance(interval, int):
            raise ValueError("polling_interval_minutes must be an integer")
        if interval < MIN_POLLING_INTERVAL_MINUTES:
            raise ValueError(f"polling_interval_minutes must be >= {MIN_POLLING_INTERVAL_MINUTES} minute(s)")
        self._config['polling_interval_minutes'] = interval
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration values as a dictionary."""
        return self._config.copy()
    
    def update_config(self, config_dict: Dict[str, Any]) -> None:
        """Update configuration with a dictionary of values."""
        for key, value in config_dict.items():
            if key == 'model':
                self.set_model(value)
            elif key == 'enable_continuous_polling':
                self.set_enable_continuous_polling(value)
            elif key == 'polling_interval_minutes':
                self.set_polling_interval_minutes(value)
            else:
                raise ValueError(f"Unknown configuration key: {key}")
    
    def validate_config(self) -> bool:
        """Validate all configuration values."""
        try:
            # Validate model
            if not isinstance(self._config['model'], str) or not self._config['model'].strip():
                return False
            
            # Validate continuous polling flag
            if not isinstance(self._config['enable_continuous_polling'], bool):
                return False
            
            # Validate polling interval
            if not isinstance(self._config['polling_interval_minutes'], int):
                return False
            if self._config['polling_interval_minutes'] < MIN_POLLING_INTERVAL_MINUTES:
                return False
            
            return True
        except Exception:
            return False


# Global configuration instance
config_manager = ConfigurationManager()