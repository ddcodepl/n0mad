#!/usr/bin/env python3
"""
Checkbox Utilities

Utility functions for checkbox state management across different task formats
and data sources. Provides consistent checkbox handling for various integrations.
"""
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class CheckboxFormat(str, Enum):
    """Supported checkbox format types."""
    NOTION = "notion"           # Notion API format
    TASKMASTER = "taskmaster"   # Task Master format
    SIMPLE = "simple"           # Simple key-value format
    BOOLEAN = "boolean"         # Direct boolean value


@dataclass
class CheckboxProperty:
    """Represents a checkbox property with metadata."""
    name: str
    value: bool
    format_type: CheckboxFormat
    raw_data: Dict[str, Any]
    confidence: float = 1.0  # Confidence in the detected value (0.0-1.0)


class CheckboxParser:
    """
    Enhanced checkbox parser that handles multiple formats and provides
    detailed parsing results with confidence scoring.
    """
    
    # Common boolean true values
    TRUE_VALUES = {
        "true", "yes", "1", "on", "enabled", "checked", 
        "active", "selected", "positive", "y"
    }
    
    # Common boolean false values  
    FALSE_VALUES = {
        "false", "no", "0", "off", "disabled", "unchecked",
        "inactive", "unselected", "negative", "n"
    }
    
    @classmethod
    def parse_checkbox_property(cls, 
                                property_name: str, 
                                property_data: Any) -> Optional[CheckboxProperty]:
        """
        Parse a checkbox property from various formats.
        
        Args:
            property_name: Name of the property
            property_data: Property data in any supported format
            
        Returns:
            CheckboxProperty if successfully parsed, None otherwise
        """
        if property_data is None:
            return None
        
        # Direct boolean value
        if isinstance(property_data, bool):
            return CheckboxProperty(
                name=property_name,
                value=property_data,
                format_type=CheckboxFormat.BOOLEAN,
                raw_data={"value": property_data},
                confidence=1.0
            )
        
        # Dictionary-based formats
        if isinstance(property_data, dict):
            return cls._parse_dict_property(property_name, property_data)
        
        # String-based formats
        if isinstance(property_data, str):
            return cls._parse_string_property(property_name, property_data)
        
        # Number-based formats
        if isinstance(property_data, (int, float)):
            return CheckboxProperty(
                name=property_name,
                value=bool(property_data),
                format_type=CheckboxFormat.SIMPLE,
                raw_data={"value": property_data},
                confidence=0.8  # Lower confidence for numeric conversion
            )
        
        logger.warning(f"⚠️  Unable to parse checkbox property '{property_name}' with type {type(property_data)}")
        return None
    
    @classmethod
    def _parse_dict_property(cls, 
                             property_name: str, 
                             property_data: Dict[str, Any]) -> Optional[CheckboxProperty]:
        """Parse checkbox from dictionary format."""
        # Notion checkbox format
        if property_data.get("type") == "checkbox" and "checkbox" in property_data:
            checkbox_value = property_data["checkbox"]
            if isinstance(checkbox_value, bool):
                return CheckboxProperty(
                    name=property_name,
                    value=checkbox_value,
                    format_type=CheckboxFormat.NOTION,
                    raw_data=property_data,
                    confidence=1.0
                )
        
        # Simple value format
        if "value" in property_data:
            value_data = property_data["value"]
            parsed_value = cls._parse_value_to_boolean(value_data)
            if parsed_value is not None:
                return CheckboxProperty(
                    name=property_name,
                    value=parsed_value[0],
                    format_type=CheckboxFormat.SIMPLE,
                    raw_data=property_data,
                    confidence=parsed_value[1]
                )
        
        # Check for other common keys
        for key in ["checked", "enabled", "active", "selected"]:
            if key in property_data:
                value_data = property_data[key]
                parsed_value = cls._parse_value_to_boolean(value_data)
                if parsed_value is not None:
                    return CheckboxProperty(
                        name=property_name,
                        value=parsed_value[0],
                        format_type=CheckboxFormat.SIMPLE,
                        raw_data=property_data,
                        confidence=parsed_value[1] * 0.9  # Slightly lower confidence
                    )
        
        return None
    
    @classmethod
    def _parse_string_property(cls, 
                               property_name: str, 
                               property_data: str) -> Optional[CheckboxProperty]:
        """Parse checkbox from string format."""
        parsed_value = cls._parse_value_to_boolean(property_data)
        if parsed_value is not None:
            return CheckboxProperty(
                name=property_name,
                value=parsed_value[0],
                format_type=CheckboxFormat.SIMPLE,
                raw_data={"value": property_data},
                confidence=parsed_value[1]
            )
        return None
    
    @classmethod
    def _parse_value_to_boolean(cls, value: Any) -> Optional[tuple[bool, float]]:
        """
        Parse any value to boolean with confidence score.
        
        Args:
            value: Value to parse
            
        Returns:
            Tuple of (boolean_value, confidence) or None if cannot parse
        """
        if isinstance(value, bool):
            return value, 1.0
        
        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in cls.TRUE_VALUES:
                return True, 1.0
            elif value_lower in cls.FALSE_VALUES:
                return False, 1.0
            else:
                # Try to infer from common patterns
                if "check" in value_lower or "select" in value_lower or "enable" in value_lower:
                    return True, 0.6
                elif "uncheck" in value_lower or "deselect" in value_lower or "disable" in value_lower:
                    return False, 0.6
        
        if isinstance(value, (int, float)):
            return bool(value), 0.8
        
        return None


class CheckboxValidator:
    """
    Validates checkbox configurations and provides validation reports.
    """
    
    @classmethod
    def validate_checkbox_configuration(cls, 
                                        task_data: Dict[str, Any], 
                                        required_checkboxes: List[str] = None,
                                        optional_checkboxes: List[str] = None) -> Dict[str, Any]:
        """
        Validate checkbox configuration in task data.
        
        Args:
            task_data: Task data to validate
            required_checkboxes: List of required checkbox property names
            optional_checkboxes: List of optional checkbox property names
            
        Returns:
            Validation report dictionary
        """
        report = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "detected_checkboxes": [],
            "missing_required": [],
            "validation_details": {}
        }
        
        if not isinstance(task_data, dict):
            report["is_valid"] = False
            report["errors"].append("Task data must be a dictionary")
            return report
        
        properties = task_data.get("properties", {})
        if not isinstance(properties, dict):
            report["warnings"].append("Task properties is not a dictionary")
            properties = {}
        
        # Parse all detected checkboxes
        parser = CheckboxParser()
        for prop_name, prop_data in properties.items():
            checkbox_prop = parser.parse_checkbox_property(prop_name, prop_data)
            if checkbox_prop:
                report["detected_checkboxes"].append({
                    "name": checkbox_prop.name,
                    "value": checkbox_prop.value,
                    "format": checkbox_prop.format_type.value,
                    "confidence": checkbox_prop.confidence
                })
                
                report["validation_details"][prop_name] = {
                    "parsed_successfully": True,
                    "value": checkbox_prop.value,
                    "confidence": checkbox_prop.confidence,
                    "format_type": checkbox_prop.format_type.value
                }
        
        # Check required checkboxes
        if required_checkboxes:
            detected_names = {cb["name"].lower() for cb in report["detected_checkboxes"]}
            for required_name in required_checkboxes:
                if required_name.lower() not in detected_names:
                    report["missing_required"].append(required_name)
                    report["errors"].append(f"Required checkbox '{required_name}' not found")
        
        # Set overall validity
        if report["errors"] or report["missing_required"]:
            report["is_valid"] = False
        
        return report
    
    @classmethod
    def validate_checkbox_value(cls, 
                                checkbox_property: CheckboxProperty,
                                expected_value: Optional[bool] = None,
                                min_confidence: float = 0.5) -> Dict[str, Any]:
        """
        Validate a specific checkbox property.
        
        Args:
            checkbox_property: Checkbox property to validate
            expected_value: Expected boolean value (if any)
            min_confidence: Minimum confidence threshold
            
        Returns:
            Validation result dictionary
        """
        validation = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "checkbox_name": checkbox_property.name,
            "checkbox_value": checkbox_property.value,
            "confidence": checkbox_property.confidence
        }
        
        # Check confidence threshold
        if checkbox_property.confidence < min_confidence:
            validation["warnings"].append(
                f"Low confidence ({checkbox_property.confidence:.2f}) in checkbox value"
            )
        
        # Check expected value
        if expected_value is not None and checkbox_property.value != expected_value:
            validation["errors"].append(
                f"Checkbox value {checkbox_property.value} does not match expected {expected_value}"
            )
            validation["is_valid"] = False
        
        return validation


class CheckboxUtilities:
    """
    General utility functions for checkbox management.
    """
    
    @staticmethod
    def find_checkbox_properties(task_data: Dict[str, Any], 
                                  search_names: List[str]) -> List[CheckboxProperty]:
        """
        Find checkbox properties by name (case-insensitive).
        
        Args:
            task_data: Task data to search
            search_names: List of checkbox names to search for
            
        Returns:
            List of found CheckboxProperty objects
        """
        found_properties = []
        
        if not isinstance(task_data, dict) or "properties" not in task_data:
            return found_properties
        
        properties = task_data["properties"]
        if not isinstance(properties, dict):
            return found_properties
        
        parser = CheckboxParser()
        search_names_lower = [name.lower() for name in search_names]
        
        for prop_name, prop_data in properties.items():
            if prop_name.lower() in search_names_lower:
                checkbox_prop = parser.parse_checkbox_property(prop_name, prop_data)
                if checkbox_prop:
                    found_properties.append(checkbox_prop)
        
        return found_properties
    
    @staticmethod
    def get_checkbox_summary(task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a summary of all checkbox properties in task data.
        
        Args:
            task_data: Task data to analyze
            
        Returns:
            Summary dictionary with checkbox information
        """
        summary = {
            "total_checkboxes": 0,
            "checked_count": 0,
            "unchecked_count": 0,
            "checkboxes": [],
            "format_distribution": {},
            "confidence_stats": {
                "min": 1.0,
                "max": 1.0,
                "avg": 1.0
            }
        }
        
        if not isinstance(task_data, dict) or "properties" not in task_data:
            return summary
        
        properties = task_data["properties"]
        if not isinstance(properties, dict):
            return summary
        
        parser = CheckboxParser()
        confidences = []
        
        for prop_name, prop_data in properties.items():
            checkbox_prop = parser.parse_checkbox_property(prop_name, prop_data)
            if checkbox_prop:
                summary["total_checkboxes"] += 1
                confidences.append(checkbox_prop.confidence)
                
                if checkbox_prop.value:
                    summary["checked_count"] += 1
                else:
                    summary["unchecked_count"] += 1
                
                summary["checkboxes"].append({
                    "name": checkbox_prop.name,
                    "value": checkbox_prop.value,
                    "format": checkbox_prop.format_type.value,
                    "confidence": checkbox_prop.confidence
                })
                
                # Track format distribution
                format_type = checkbox_prop.format_type.value
                summary["format_distribution"][format_type] = \
                    summary["format_distribution"].get(format_type, 0) + 1
        
        # Calculate confidence statistics
        if confidences:
            summary["confidence_stats"] = {
                "min": min(confidences),
                "max": max(confidences),
                "avg": sum(confidences) / len(confidences)
            }
        
        return summary
    
    @staticmethod
    def normalize_checkbox_data(task_data: Dict[str, Any], 
                                target_format: CheckboxFormat = CheckboxFormat.SIMPLE) -> Dict[str, Any]:
        """
        Normalize checkbox data to a consistent format.
        
        Args:
            task_data: Task data with checkboxes to normalize
            target_format: Target format for normalization
            
        Returns:
            Task data with normalized checkbox properties
        """
        if not isinstance(task_data, dict) or "properties" not in task_data:
            return task_data
        
        normalized_data = task_data.copy()
        properties = normalized_data.get("properties", {})
        
        if not isinstance(properties, dict):
            return normalized_data
        
        parser = CheckboxParser()
        normalized_properties = properties.copy()
        
        for prop_name, prop_data in properties.items():
            checkbox_prop = parser.parse_checkbox_property(prop_name, prop_data)
            if checkbox_prop:
                # Normalize to target format
                if target_format == CheckboxFormat.SIMPLE:
                    normalized_properties[prop_name] = {
                        "value": checkbox_prop.value
                    }
                elif target_format == CheckboxFormat.NOTION:
                    normalized_properties[prop_name] = {
                        "type": "checkbox",
                        "checkbox": checkbox_prop.value
                    }
                elif target_format == CheckboxFormat.BOOLEAN:
                    normalized_properties[prop_name] = checkbox_prop.value
        
        normalized_data["properties"] = normalized_properties
        return normalized_data
    
    @staticmethod
    def log_checkbox_analysis(task_id: str, checkbox_summary: Dict[str, Any]) -> None:
        """
        Log checkbox analysis results for debugging and monitoring.
        
        Args:
            task_id: Task identifier for logging context
            checkbox_summary: Checkbox summary from get_checkbox_summary()
        """
        logger.info(f"📋 Checkbox analysis for task {task_id}:")
        logger.info(f"   📊 Total checkboxes: {checkbox_summary['total_checkboxes']}")
        logger.info(f"   ✅ Checked: {checkbox_summary['checked_count']}")
        logger.info(f"   ❌ Unchecked: {checkbox_summary['unchecked_count']}")
        
        if checkbox_summary["checkboxes"]:
            logger.info("   📝 Individual checkboxes:")
            for checkbox in checkbox_summary["checkboxes"]:
                status = "✅" if checkbox["value"] else "❌"
                logger.info(f"     {status} {checkbox['name']} ({checkbox['format']}, confidence: {checkbox['confidence']:.2f})")
        
        if checkbox_summary["format_distribution"]:
            logger.info("   📈 Format distribution:")
            for format_type, count in checkbox_summary["format_distribution"].items():
                logger.info(f"     {format_type}: {count}")
        
        conf_stats = checkbox_summary["confidence_stats"]
        logger.info(f"   🎯 Confidence stats: min={conf_stats['min']:.2f}, max={conf_stats['max']:.2f}, avg={conf_stats['avg']:.2f}")