#!/usr/bin/env python3
"""
Enhanced Name Validation Utilities

Advanced validation and sanitization utilities for task names, branch names,
and other identifiers used in the system.
"""
import logging
import re
import string
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ValidationResult(str, Enum):
    """Validation result status."""

    VALID = "valid"
    INVALID = "invalid"
    SANITIZED = "sanitized"
    FALLBACK = "fallback"


@dataclass
class NameValidationReport:
    """Detailed validation report for names."""

    original_name: str
    sanitized_name: str
    task_id: Optional[str]
    result: ValidationResult
    issues_found: List[str]
    changes_made: List[str]
    confidence_score: float
    is_git_safe: bool
    is_readable: bool
    character_count: int
    word_count: int


class AdvancedNameValidator:
    """
    Advanced name validator with enhanced features for task and branch naming.

    Features:
    - Unicode normalization and transliteration
    - Conflict detection and resolution
    - Readability scoring
    - Custom naming patterns
    - Detailed validation reporting
    """

    # Git branch naming constraints
    MAX_BRANCH_LENGTH = 250
    MIN_BRANCH_LENGTH = 1

    # Character sets
    SAFE_CHARS = set(string.ascii_letters + string.digits + "-._/")
    REPLACEMENT_CHARS = {
        " ": "-",
        "_": "-",
        "\t": "-",
        "\n": "-",
        "\r": "-",
    }

    # Unicode categories to remove
    REMOVE_CATEGORIES = {
        "Cc",
        "Cf",
        "Cs",
        "Co",
        "Cn",
        "Mn",
        "Me",
        "Mc",
    }  # Control, format, surrogate, private, unassigned, marks

    # Forbidden patterns (regex)
    FORBIDDEN_PATTERNS = [
        r"^\.|\.$",  # Start or end with dot
        r"\.\.+",  # Multiple consecutive dots
        r"//+",  # Multiple consecutive slashes
        r"^/|/$",  # Start or end with slash
        r"@\{",  # @{ sequence
        r"[\x00-\x1f\x7f]",  # Control characters
        r"^-+|-+$",  # Start or end with hyphens
    ]

    # Reserved names
    RESERVED_NAMES = {
        "master",
        "main",
        "head",
        "origin",
        "upstream",
        "refs",
        "HEAD",
        "FETCH_HEAD",
        "ORIG_HEAD",
        "MERGE_HEAD",
        "cherry-pick-head",
    }

    def __init__(self, custom_patterns: Optional[Dict[str, str]] = None):
        """
        Initialize the advanced name validator.

        Args:
            custom_patterns: Custom naming patterns for specific contexts
        """
        self.custom_patterns = custom_patterns or {}
        self.validation_cache: Dict[str, NameValidationReport] = {}
        self._existing_branches: Set[str] = set()  # Would be populated from Git

        logger.info("🔍 AdvancedNameValidator initialized")

    def validate_and_sanitize(self, name: str, task_id: Optional[str] = None, context: str = "default") -> NameValidationReport:
        """
        Perform comprehensive validation and sanitization of a name.

        Args:
            name: Name to validate and sanitize
            task_id: Optional task identifier
            context: Validation context (affects rules applied)

        Returns:
            Detailed validation report
        """
        cache_key = f"{name}:{task_id}:{context}"
        if cache_key in self.validation_cache:
            return self.validation_cache[cache_key]

        logger.debug(f"🔍 Validating name: '{name}' (context: {context})")

        report = NameValidationReport(
            original_name=name,
            sanitized_name="",
            task_id=task_id,
            result=ValidationResult.VALID,
            issues_found=[],
            changes_made=[],
            confidence_score=1.0,
            is_git_safe=False,
            is_readable=False,
            character_count=len(name) if name else 0,
            word_count=0,
        )

        try:
            # Step 1: Initial validation
            if not name or not isinstance(name, str):
                report.sanitized_name = self._generate_fallback_name(task_id)
                report.result = ValidationResult.FALLBACK
                report.issues_found.append("Empty or invalid input")
                report.confidence_score = 0.1
                return self._finalize_report(report, cache_key)

            # Step 2: Unicode normalization and cleaning
            cleaned_name = self._normalize_unicode(name)
            if cleaned_name != name:
                report.changes_made.append("Unicode normalization applied")

            # Step 3: Remove problematic characters
            sanitized_name = self._remove_problematic_characters(cleaned_name)
            if sanitized_name != cleaned_name:
                report.changes_made.append("Problematic characters removed")

            # Step 4: Apply character replacements
            sanitized_name = self._apply_replacements(sanitized_name)
            if sanitized_name != cleaned_name:
                report.changes_made.append("Character replacements applied")

            # Step 5: Handle length constraints
            sanitized_name = self._enforce_length_limits(sanitized_name, task_id)
            if len(sanitized_name) != len(name):
                report.changes_made.append(f"Length adjusted to {len(sanitized_name)} chars")

            # Step 6: Clean up formatting
            sanitized_name = self._cleanup_formatting(sanitized_name)

            # Step 7: Add task ID prefix if provided
            if task_id:
                clean_task_id = self._sanitize_task_id(task_id)
                if clean_task_id and not sanitized_name.startswith(clean_task_id):
                    sanitized_name = f"{clean_task_id}-{sanitized_name}"
                    report.changes_made.append(f"Task ID prefix added: {clean_task_id}")

            # Step 8: Final validation
            sanitized_name = self._apply_final_validation(sanitized_name, task_id)

            # Step 9: Quality assessment
            report.sanitized_name = sanitized_name
            report = self._assess_quality(report)

            # Step 10: Determine final result
            if report.sanitized_name == report.original_name:
                report.result = ValidationResult.VALID
            elif report.confidence_score > 0.7:
                report.result = ValidationResult.SANITIZED
            else:
                report.result = ValidationResult.FALLBACK

            return self._finalize_report(report, cache_key)

        except Exception as e:
            logger.error(f"❌ Error validating name '{name}': {e}")
            report.sanitized_name = self._generate_fallback_name(task_id)
            report.result = ValidationResult.FALLBACK
            report.issues_found.append(f"Validation error: {str(e)}")
            report.confidence_score = 0.1
            return self._finalize_report(report, cache_key)

    def _normalize_unicode(self, name: str) -> str:
        """Normalize Unicode characters and remove problematic categories."""
        # Normalize to NFD (canonical decomposition)
        normalized = unicodedata.normalize("NFD", name)

        # Remove characters from problematic Unicode categories
        filtered_chars = []
        for char in normalized:
            category = unicodedata.category(char)
            if category not in self.REMOVE_CATEGORIES:
                # Try to transliterate accented characters
                if category.startswith("L"):  # Letter categories
                    # Remove combining marks to get base character
                    base_char = unicodedata.normalize("NFD", char)[0]
                    if base_char.isascii():
                        filtered_chars.append(base_char)
                    elif char.isascii():
                        filtered_chars.append(char)
                elif char.isascii():
                    filtered_chars.append(char)

        return "".join(filtered_chars)

    def _remove_problematic_characters(self, name: str) -> str:
        """Remove characters that are problematic for Git branch names."""
        # Remove characters that aren't in safe set
        safe_chars = []
        for char in name:
            if char in self.SAFE_CHARS or char in self.REPLACEMENT_CHARS:
                safe_chars.append(char)
            # Skip other characters

        return "".join(safe_chars)

    def _apply_replacements(self, name: str) -> str:
        """Apply character replacements."""
        result = name
        for old_char, new_char in self.REPLACEMENT_CHARS.items():
            result = result.replace(old_char, new_char)

        # Collapse multiple hyphens
        result = re.sub(r"-+", "-", result)

        return result

    def _enforce_length_limits(self, name: str, task_id: Optional[str] = None) -> str:
        """Enforce length limits while preserving readability."""
        if len(name) <= self.MAX_BRANCH_LENGTH:
            return name

        # Calculate available space (reserve space for task ID if needed)
        reserved_space = 0
        if task_id:
            clean_task_id = self._sanitize_task_id(task_id)
            reserved_space = len(clean_task_id) + 1  # +1 for hyphen

        available_length = self.MAX_BRANCH_LENGTH - reserved_space

        if available_length < self.MIN_BRANCH_LENGTH:
            # Not enough space, use fallback
            return self._generate_fallback_name(task_id)

        # Truncate intelligently at word boundaries
        truncated = name[:available_length]

        # Try to truncate at word boundary
        last_hyphen = truncated.rfind("-")
        if last_hyphen > available_length // 2:  # At least half the length
            truncated = truncated[:last_hyphen]

        # Clean up trailing hyphens
        truncated = truncated.rstrip("-")

        return truncated or self._generate_fallback_name(task_id)

    def _cleanup_formatting(self, name: str) -> str:
        """Clean up formatting issues."""
        # Remove leading/trailing hyphens and dots
        cleaned = name.strip(".-")

        # Apply forbidden pattern fixes
        for pattern in self.FORBIDDEN_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned)

        # Ensure not empty
        if not cleaned:
            return "unnamed"

        return cleaned

    def _sanitize_task_id(self, task_id: str) -> str:
        """Sanitize task ID for use in branch names."""
        if not task_id:
            return ""

        # Remove problematic characters from task ID
        sanitized = re.sub(r"[^a-zA-Z0-9-]", "", str(task_id))

        # Ensure it's not empty and not too long
        if not sanitized:
            return ""

        if len(sanitized) > 50:  # Reasonable limit for task IDs
            sanitized = sanitized[:50]

        return sanitized

    def _apply_final_validation(self, name: str, task_id: Optional[str]) -> str:
        """Apply final validation and fixes."""
        # Check against reserved names
        if name.lower() in self.RESERVED_NAMES:
            safe_name = f"{name}-task"
            if task_id:
                clean_task_id = self._sanitize_task_id(task_id)
                if clean_task_id:
                    safe_name = f"{clean_task_id}-{name}"
            return safe_name

        # Ensure it's not empty after all processing
        if not name or len(name) < self.MIN_BRANCH_LENGTH:
            return self._generate_fallback_name(task_id)

        # Final Git safety check
        if not self._is_git_safe(name):
            return self._generate_fallback_name(task_id)

        return name

    def _generate_fallback_name(self, task_id: Optional[str] = None) -> str:
        """Generate a safe fallback name."""
        import time

        timestamp = int(time.time())

        if task_id:
            clean_task_id = self._sanitize_task_id(task_id)
            if clean_task_id:
                return f"task-{clean_task_id}-{timestamp}"

        return f"task-{timestamp}"

    def _assess_quality(self, report: NameValidationReport) -> NameValidationReport:
        """Assess the quality of the sanitized name."""
        name = report.sanitized_name

        # Git safety check
        report.is_git_safe = self._is_git_safe(name)

        # Readability assessment
        report.is_readable = self._assess_readability(name)
        report.word_count = len([word for word in name.split("-") if word])

        # Confidence scoring
        confidence = 1.0

        # Penalize for issues found
        confidence -= len(report.issues_found) * 0.1

        # Penalize for major changes
        if len(report.changes_made) > 3:
            confidence -= 0.2

        # Penalize for low readability
        if not report.is_readable:
            confidence -= 0.3

        # Penalize for fallback generation
        if name.startswith("task-") and name.count("-") >= 2:
            if name.split("-")[-1].isdigit():  # Timestamp-based fallback
                confidence = 0.1

        # Bonus for maintaining word structure
        if report.word_count >= 2:
            confidence += 0.1

        report.confidence_score = max(0.0, min(1.0, confidence))

        return report

    def _is_git_safe(self, name: str) -> bool:
        """Check if name is safe for Git branch usage."""
        if not name or not isinstance(name, str):
            return False

        # Length check
        if len(name) > self.MAX_BRANCH_LENGTH:
            return False

        # Forbidden pattern checks
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, name):
                return False

        # Reserved name check
        if name.lower() in self.RESERVED_NAMES:
            return False

        # .lock extension check
        if name.endswith(".lock"):
            return False

        # ASCII check
        if not name.isascii():
            return False

        return True

    def _assess_readability(self, name: str) -> bool:
        """Assess if the name is readable and meaningful."""
        if not name:
            return False

        # Check for meaningful word structure
        words = [word for word in name.split("-") if word and not word.isdigit()]

        if len(words) < 1:
            return False

        # Check average word length (too short suggests over-sanitization)
        avg_word_length = sum(len(word) for word in words) / len(words)
        if avg_word_length < 2:
            return False

        # Check for too many consecutive single characters
        single_char_segments = [word for word in words if len(word) == 1]
        if len(single_char_segments) > len(words) // 2:
            return False

        return True

    def _finalize_report(self, report: NameValidationReport, cache_key: str) -> NameValidationReport:
        """Finalize the validation report."""
        # Cache the result
        self.validation_cache[cache_key] = report

        # Keep cache size manageable
        if len(self.validation_cache) > 1000:
            # Remove oldest entries (simple approach)
            keys_to_remove = list(self.validation_cache.keys())[:100]
            for key in keys_to_remove:
                del self.validation_cache[key]

        # Log summary for debugging
        logger.debug(
            f"🔍 Validation complete: '{report.original_name}' → '{report.sanitized_name}' "
            f"({report.result.value}, confidence: {report.confidence_score:.2f})"
        )

        return report

    def check_name_conflicts(self, name: str, existing_names: List[str]) -> Dict[str, Any]:
        """
        Check for naming conflicts and suggest alternatives.

        Args:
            name: Name to check
            existing_names: List of existing names to check against

        Returns:
            Dictionary with conflict information and suggestions
        """
        conflicts = {
            "has_conflict": False,
            "conflicting_names": [],
            "suggestions": [],
            "severity": "none",
        }

        name_lower = name.lower()

        # Exact match check
        for existing in existing_names:
            if existing.lower() == name_lower:
                conflicts["has_conflict"] = True
                conflicts["conflicting_names"].append(existing)
                conflicts["severity"] = "exact"

        # Similar name check (Levenshtein distance)
        similar_names = []
        for existing in existing_names:
            if self._calculate_similarity(name_lower, existing.lower()) > 0.8:
                similar_names.append(existing)

        if similar_names:
            conflicts["conflicting_names"].extend(similar_names)
            if not conflicts["has_conflict"]:
                conflicts["has_conflict"] = True
                conflicts["severity"] = "similar"

        # Generate suggestions if conflicts found
        if conflicts["has_conflict"]:
            conflicts["suggestions"] = self._generate_conflict_alternatives(name, existing_names)

        return conflicts

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (simplified Levenshtein)."""
        if not str1 or not str2:
            return 0.0

        len1, len2 = len(str1), len(str2)
        if len1 == 0:
            return 0.0 if len2 == 0 else 0.0
        if len2 == 0:
            return 0.0

        # Simple approach: compare character overlap
        set1, set2 = set(str1), set(str2)
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))

        return intersection / union if union > 0 else 0.0

    def _generate_conflict_alternatives(self, name: str, existing_names: List[str]) -> List[str]:
        """Generate alternative names to avoid conflicts."""
        alternatives = []
        existing_lower = [n.lower() for n in existing_names]

        # Add numeric suffixes
        for i in range(1, 10):
            candidate = f"{name}-{i}"
            if candidate.lower() not in existing_lower:
                alternatives.append(candidate)
                if len(alternatives) >= 3:
                    break

        # Add descriptive suffixes
        suffixes = ["new", "updated", "revised", "v2", "alt"]
        for suffix in suffixes:
            candidate = f"{name}-{suffix}"
            if candidate.lower() not in existing_lower:
                alternatives.append(candidate)
                if len(alternatives) >= 5:
                    break

        return alternatives[:5]  # Return max 5 suggestions
