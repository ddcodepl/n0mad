#!/usr/bin/env python3
"""
Commit Message Generation Service

Generates standardized, informative commit messages following conventional commits format.
Integrates with task data to create consistent and meaningful commit messages.
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from utils.logging_config import get_logger

logger = get_logger(__name__)


class CommitType(str, Enum):
    """Standard conventional commit types."""
    FEAT = "feat"           # New feature
    FIX = "fix"             # Bug fix
    DOCS = "docs"           # Documentation changes
    STYLE = "style"         # Code style changes (formatting, etc.)
    REFACTOR = "refactor"   # Code refactoring
    PERF = "perf"          # Performance improvements
    TEST = "test"          # Adding or updating tests
    BUILD = "build"        # Build system or dependency changes
    CI = "ci"              # CI/CD changes
    CHORE = "chore"        # Maintenance tasks
    REVERT = "revert"      # Reverting changes
    WIP = "wip"            # Work in progress (for development)


@dataclass
class CommitMessageTemplate:
    """Represents a commit message template with metadata."""
    type_prefix: CommitType
    scope: Optional[str]
    description_template: str
    examples: List[str]
    max_description_length: int = 50
    
    
@dataclass
class TaskCommitData:
    """Structured task data for commit message generation."""
    ticket_id: str
    task_title: str
    task_description: Optional[str] = None
    task_type: Optional[str] = None
    completion_summary: Optional[str] = None
    changed_files: Optional[List[str]] = None
    is_breaking_change: bool = False


class CommitMessageGenerator:
    """
    Service for generating standardized commit messages from task data.
    
    Features:
    - Conventional Commits format compliance
    - Automatic commit type detection
    - Ticket number integration
    - Description optimization and truncation
    - Validation against git best practices
    """
    
    def __init__(self):
        """Initialize the commit message generator with templates and rules."""
        self.max_subject_length = 72  # Git recommended maximum
        self.max_description_length = 50  # For readability
        self.min_description_length = 10  # Minimum meaningful description
        
        # Commit type detection patterns
        self.type_detection_patterns = {
            CommitType.FEAT: [
                r'\b(add|implement|introduce|create|new)\b',
                r'\b(feature|functionality)\b',
                r'\b(support for|enable)\b'
            ],
            CommitType.FIX: [
                r'\b(fix|resolve|correct|repair)\b',
                r'\b(bug|issue|problem|error)\b',
                r'\b(handle|prevent)\b.*\b(error|exception)\b'
            ],
            CommitType.DOCS: [
                r'\b(document|documentation|readme|guide)\b',
                r'\b(update|add).*\b(docs|comments)\b',
                r'\b(api.*docs|user.*guide)\b'
            ],
            CommitType.REFACTOR: [
                r'\b(refactor|restructure|reorganize)\b',
                r'\b(clean.*up|optimize|improve)\b',
                r'\b(extract|split|merge).*\b(function|method|class)\b'
            ],
            CommitType.STYLE: [
                r'\b(format|formatting|style|lint)\b',
                r'\b(whitespace|indentation|syntax)\b',
                r'\b(prettier|eslint|flake8)\b'
            ],
            CommitType.TEST: [
                r'\b(test|testing|spec|coverage)\b',
                r'\b(unit.*test|integration.*test)\b',
                r'\b(mock|stub|fixture)\b'
            ],
            CommitType.PERF: [
                r'\b(performance|optimize|speed)\b',
                r'\b(cache|caching|memoiz)\b',
                r'\b(efficient|faster|slower)\b'
            ],
            CommitType.BUILD: [
                r'\b(build|compile|package|deploy)\b',
                r'\b(dependency|dependencies|requirements)\b',
                r'\b(webpack|babel|rollup)\b'
            ],
            CommitType.CHORE: [
                r'\b(chore|maintenance|cleanup)\b',
                r'\b(update.*version|bump)\b',
                r'\b(config|configuration)\b'
            ]
        }
        
        # Common word replacements for conciseness
        self.word_replacements = {
            'implementation': 'impl',
            'functionality': 'feature',
            'configuration': 'config',
            'authentication': 'auth',
            'authorization': 'authz',
            'database': 'db',
            'application': 'app',
            'environment': 'env',
            'development': 'dev',
            'production': 'prod',
            'optimization': 'opt',
            'performance': 'perf',
            'repository': 'repo',
            'validation': 'val',
            'generation': 'gen',
            'management': 'mgmt'
        }
        
        logger.info("🔧 CommitMessageGenerator initialized with conventional commits support")
    
    def generate_commit_message(self, 
                              task_data: TaskCommitData,
                              commit_type: Optional[CommitType] = None,
                              custom_scope: Optional[str] = None) -> str:
        """
        Generate a commit message from task data.
        
        Args:
            task_data: Structured task information
            commit_type: Override automatic type detection
            custom_scope: Override automatic scope detection
            
        Returns:
            Formatted commit message following conventional commits
        """
        try:
            logger.info(f"🔧 Generating commit message for ticket {task_data.ticket_id}")
            
            # Step 1: Determine commit type
            detected_type = commit_type or self._detect_commit_type(task_data)
            logger.debug(f"📝 Commit type: {detected_type.value}")
            
            # Step 2: Extract/generate scope
            scope = custom_scope or self._extract_scope(task_data)
            logger.debug(f"📝 Scope: {scope}")
            
            # Step 3: Generate description
            description = self._generate_description(task_data, detected_type)
            logger.debug(f"📝 Raw description: {description}")
            
            # Step 4: Optimize description length
            optimized_description = self._optimize_description(description, detected_type, scope, task_data.ticket_id)
            logger.debug(f"📝 Optimized description: {optimized_description}")
            
            # Step 5: Construct final message
            commit_message = self._construct_commit_message(
                commit_type=detected_type,
                scope=scope,
                description=optimized_description,
                ticket_id=task_data.ticket_id,
                is_breaking=task_data.is_breaking_change
            )
            
            # Step 6: Validate final message
            validation_result = self._validate_commit_message(commit_message)
            if not validation_result.is_valid:
                logger.warning(f"⚠️ Generated commit message validation issues: {validation_result.warnings}")
            
            logger.info(f"✅ Generated commit message: {commit_message}")
            return commit_message
            
        except Exception as e:
            logger.error(f"❌ Failed to generate commit message: {e}")
            # Fallback to simple format
            return self._generate_fallback_message(task_data)
    
    def _detect_commit_type(self, task_data: TaskCommitData) -> CommitType:
        """
        Automatically detect commit type based on task content.
        
        Args:
            task_data: Task information
            
        Returns:
            Detected commit type
        """
        # Combine relevant text for analysis
        analysis_text = " ".join(filter(None, [
            task_data.task_title,
            task_data.task_description,
            task_data.completion_summary
        ])).lower()
        
        # Score each commit type based on pattern matches
        type_scores = {}
        
        for commit_type, patterns in self.type_detection_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, analysis_text, re.IGNORECASE))
                score += matches
            
            if score > 0:
                type_scores[commit_type] = score
        
        # Return highest scoring type, default to FEAT for new functionality
        if type_scores:
            detected_type = max(type_scores.items(), key=lambda x: x[1])[0]
            logger.debug(f"🔍 Type detection scores: {dict(type_scores)}")
            return detected_type
        else:
            # Default heuristics based on task title keywords
            title_lower = task_data.task_title.lower()
            if any(word in title_lower for word in ['fix', 'bug', 'error', 'issue']):
                return CommitType.FIX
            elif any(word in title_lower for word in ['doc', 'readme', 'guide']):
                return CommitType.DOCS
            elif any(word in title_lower for word in ['test', 'spec', 'coverage']):
                return CommitType.TEST
            else:
                return CommitType.FEAT  # Default assumption
    
    def _extract_scope(self, task_data: TaskCommitData) -> Optional[str]:
        """
        Extract or infer scope from task data.
        
        Args:
            task_data: Task information
            
        Returns:
            Scope string or None
        """
        # Try to extract scope from ticket ID (e.g., NOMAD-AUTH-123 -> auth)
        ticket_match = re.match(r'([A-Z]+)-([A-Z]+)-\d+', task_data.ticket_id)
        if ticket_match:
            return ticket_match.group(2).lower()
        
        # Try to infer from changed files
        if task_data.changed_files:
            # Look for common directory patterns
            common_scopes = []
            for file_path in task_data.changed_files:
                path_parts = file_path.split('/')
                if len(path_parts) > 1:
                    # Extract potential scope from directory structure
                    for part in path_parts[:-1]:  # Exclude filename
                        if part in ['auth', 'api', 'ui', 'db', 'core', 'utils', 'services', 'components']:
                            common_scopes.append(part)
            
            if common_scopes:
                # Return most common scope
                from collections import Counter
                return Counter(common_scopes).most_common(1)[0][0]
        
        # Try to infer from task title
        title_lower = task_data.task_title.lower()
        scope_keywords = {
            'auth': ['auth', 'login', 'user', 'session', 'token'],
            'api': ['api', 'endpoint', 'rest', 'graphql', 'service'],
            'ui': ['ui', 'interface', 'component', 'frontend', 'view'],
            'db': ['database', 'sql', 'query', 'table', 'migration'],
            'config': ['config', 'setting', 'environment', 'env'],
            'test': ['test', 'spec', 'coverage', 'mock'],
            'docs': ['doc', 'readme', 'guide', 'comment']
        }
        
        for scope, keywords in scope_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                return scope
        
        return None  # No scope identified
    
    def _generate_description(self, task_data: TaskCommitData, commit_type: CommitType) -> str:
        """
        Generate commit description from task data.
        
        Args:
            task_data: Task information
            commit_type: Detected commit type
            
        Returns:
            Generated description
        """
        # Use completion summary if available and relevant
        if task_data.completion_summary and len(task_data.completion_summary.strip()) > 10:
            description = task_data.completion_summary.strip()
        else:
            # Use task title as base
            description = task_data.task_title.strip()
        
        # Clean up the description
        description = self._clean_description(description, task_data.ticket_id)
        
        # Adjust based on commit type
        if commit_type == CommitType.FIX:
            if not any(word in description.lower() for word in ['fix', 'resolve', 'correct']):
                description = f"fix {description}"
        elif commit_type == CommitType.FEAT:
            if not any(word in description.lower() for word in ['add', 'implement', 'introduce']):
                description = f"add {description}"
        
        return description
    
    def _clean_description(self, description: str, ticket_id: str) -> str:
        """
        Clean and normalize description text.
        
        Args:
            description: Raw description
            ticket_id: Ticket identifier
            
        Returns:
            Cleaned description
        """
        # Remove ticket ID if present
        cleaned = re.sub(r'\b' + re.escape(ticket_id) + r'\b:?\s*', '', description, flags=re.IGNORECASE)
        
        # Remove common prefixes
        prefixes_to_remove = [
            r'^(task|ticket|issue):\s*',
            r'^(implement|add|create|fix|update):\s*',
            r'^(feature|enhancement):\s*'
        ]
        
        for prefix in prefixes_to_remove:
            cleaned = re.sub(prefix, '', cleaned, flags=re.IGNORECASE)
        
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Ensure lowercase start (conventional commits style)
        if cleaned and cleaned[0].isupper():
            cleaned = cleaned[0].lower() + cleaned[1:]
        
        # Apply word replacements for conciseness
        for long_word, short_word in self.word_replacements.items():
            cleaned = re.sub(r'\b' + re.escape(long_word) + r'\b', short_word, cleaned, flags=re.IGNORECASE)
        
        return cleaned.strip()
    
    def _optimize_description(self, 
                            description: str, 
                            commit_type: CommitType, 
                            scope: Optional[str], 
                            ticket_id: str) -> str:
        """
        Optimize description length to fit within commit message limits.
        
        Args:
            description: Original description
            commit_type: Commit type
            scope: Optional scope
            ticket_id: Ticket identifier
            
        Returns:
            Optimized description
        """
        # Calculate available space for description
        prefix_length = len(commit_type.value) + 2  # "feat: "
        if scope:
            prefix_length += len(scope) + 2  # "(scope)"
        
        suffix_length = len(ticket_id) + 3  # " (TICKET-123)"
        available_length = self.max_subject_length - prefix_length - suffix_length
        
        if len(description) <= available_length:
            return description
        
        # Need to truncate - try different strategies
        logger.debug(f"📝 Description too long ({len(description)} chars), optimizing for {available_length} chars")
        
        # Strategy 1: Remove redundant words
        optimized = self._remove_redundant_words(description)
        if len(optimized) <= available_length:
            return optimized
        
        # Strategy 2: Use abbreviations more aggressively
        optimized = self._apply_aggressive_abbreviations(optimized)
        if len(optimized) <= available_length:
            return optimized
        
        # Strategy 3: Truncate with ellipsis
        if available_length > 3:
            return optimized[:available_length-3] + "..."
        else:
            return optimized[:available_length]
    
    def _remove_redundant_words(self, description: str) -> str:
        """Remove redundant or unnecessary words."""
        # Common redundant words in commit messages
        redundant_words = [
            'the', 'a', 'an', 'this', 'that', 'these', 'those',
            'very', 'really', 'quite', 'just', 'only', 'also',
            'some', 'many', 'much', 'more', 'most', 'all'
        ]
        
        words = description.split()
        filtered_words = []
        
        for word in words:
            if word.lower() not in redundant_words or len(filtered_words) == 0:
                filtered_words.append(word)
        
        return ' '.join(filtered_words)
    
    def _apply_aggressive_abbreviations(self, description: str) -> str:
        """Apply more aggressive abbreviations."""
        aggressive_replacements = {
            'implementation': 'impl',
            'function': 'fn',
            'method': 'method',
            'service': 'svc',
            'component': 'comp',
            'interface': 'iface',
            'message': 'msg',
            'response': 'resp',
            'request': 'req',
            'parameter': 'param',
            'parameters': 'params',
            'variable': 'var',
            'variables': 'vars',
            'configuration': 'cfg',
            'initialization': 'init',
            'validation': 'val',
            'authentication': 'auth',
            'authorization': 'authz'
        }
        
        result = description
        for long_form, short_form in aggressive_replacements.items():
            result = re.sub(r'\b' + re.escape(long_form) + r'\b', short_form, result, flags=re.IGNORECASE)
        
        return result
    
    def _construct_commit_message(self,
                                commit_type: CommitType,
                                scope: Optional[str],
                                description: str,
                                ticket_id: str,
                                is_breaking: bool = False) -> str:
        """
        Construct the final commit message.
        
        Args:
            commit_type: Type of commit
            scope: Optional scope
            description: Optimized description
            ticket_id: Ticket identifier
            is_breaking: Whether this is a breaking change
            
        Returns:
            Complete commit message
        """
        # Build the commit message parts
        parts = [commit_type.value]
        
        if scope:
            parts[0] += f"({scope})"
        
        if is_breaking:
            parts[0] += "!"
        
        parts.append(": ")
        parts.append(description)
        parts.append(f" ({ticket_id})")
        
        return "".join(parts)
    
    def _validate_commit_message(self, message: str) -> 'CommitValidationResult':
        """
        Validate commit message against best practices.
        
        Args:
            message: Complete commit message
            
        Returns:
            Validation result with warnings/errors
        """
        warnings = []
        errors = []
        
        # Check length
        if len(message) > self.max_subject_length:
            errors.append(f"Subject line too long ({len(message)} > {self.max_subject_length})")
        
        # Check conventional commits format
        if not re.match(r'^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|wip)(\(.+\))?!?:', message):
            warnings.append("Does not follow conventional commits format")
        
        # Check description quality
        description_match = re.search(r':\s*(.+?)\s*\([A-Z]+-\d+\)', message)
        if description_match:
            description = description_match.group(1)
            if len(description) < self.min_description_length:
                warnings.append("Description might be too brief for clarity")
        
        return CommitValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _generate_fallback_message(self, task_data: TaskCommitData) -> str:
        """
        Generate a simple fallback message when main generation fails.
        
        Args:
            task_data: Task information
            
        Returns:
            Simple commit message
        """
        # Very basic format as fallback
        cleaned_title = self._clean_description(task_data.task_title, task_data.ticket_id)
        if len(cleaned_title) > 40:
            cleaned_title = cleaned_title[:37] + "..."
        
        return f"feat: {cleaned_title} ({task_data.ticket_id})"
    
    def generate_batch_messages(self, 
                              tasks_data: List[TaskCommitData],
                              commit_type: Optional[CommitType] = None) -> List[Tuple[str, str]]:
        """
        Generate commit messages for multiple tasks.
        
        Args:
            tasks_data: List of task data
            commit_type: Optional uniform commit type
            
        Returns:
            List of (ticket_id, commit_message) tuples
        """
        results = []
        
        for task_data in tasks_data:
            try:
                message = self.generate_commit_message(task_data, commit_type)
                results.append((task_data.ticket_id, message))
            except Exception as e:
                logger.error(f"❌ Failed to generate message for {task_data.ticket_id}: {e}")
                fallback = self._generate_fallback_message(task_data)
                results.append((task_data.ticket_id, fallback))
        
        return results
    
    def get_supported_types(self) -> List[CommitType]:
        """Get list of supported commit types."""
        return list(CommitType)
    
    def validate_custom_message(self, message: str) -> 'CommitValidationResult':
        """
        Validate a custom commit message.
        
        Args:
            message: Custom commit message
            
        Returns:
            Validation result
        """
        return self._validate_commit_message(message)


@dataclass
class CommitValidationResult:
    """Result of commit message validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]