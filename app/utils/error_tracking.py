"""
Error tracking utilities for upload operations.

This module provides utilities for tracking, categorizing, and reporting
errors that occur during bulk upload operations.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Severity levels for upload errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorPattern:
    """Represents a pattern of errors for analysis."""
    error_type: str
    pattern_description: str
    affected_rows: List[int]
    severity: ErrorSeverity
    suggested_fix: str


class ErrorTracker:
    """
    Utility class for tracking and analyzing upload errors.
    
    This class provides methods for collecting, categorizing, and analyzing
    errors that occur during bulk upload operations to provide better
    feedback to users.
    """
    
    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
        self.error_patterns: List[ErrorPattern] = []
    
    def add_error(
        self, 
        row_number: int, 
        error_type: str, 
        error_message: str, 
        row_data: Dict[str, Any],
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ) -> None:
        """
        Add an error to the tracking system.
        
        Args:
            row_number: Row number where error occurred
            error_type: Type of error
            error_message: Error message
            row_data: Data from the row that caused the error
            severity: Severity level of the error
        """
        self.errors.append({
            "row_number": row_number,
            "error_type": error_type,
            "error_message": error_message,
            "row_data": row_data,
            "severity": severity.value
        })
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive error statistics.
        
        Returns:
            Dict[str, Any]: Error statistics including counts, types, and patterns
        """
        if not self.errors:
            return {
                "total_errors": 0,
                "error_types": {},
                "severity_distribution": {},
                "most_common_errors": []
            }
        
        error_types = Counter(error["error_type"] for error in self.errors)
        severity_distribution = Counter(error["severity"] for error in self.errors)
        
        # Find most common error messages
        error_messages = Counter(error["error_message"] for error in self.errors)
        most_common_errors = error_messages.most_common(5)
        
        return {
            "total_errors": len(self.errors),
            "error_types": dict(error_types),
            "severity_distribution": dict(severity_distribution),
            "most_common_errors": [
                {"message": msg, "count": count} 
                for msg, count in most_common_errors
            ]
        }
    
    def analyze_error_patterns(self) -> List[ErrorPattern]:
        """
        Analyze errors to identify common patterns and suggest fixes.
        
        Returns:
            List[ErrorPattern]: List of identified error patterns
        """
        patterns = []
        
        if not self.errors:
            return patterns
        
        # Group errors by type
        errors_by_type = defaultdict(list)
        for error in self.errors:
            errors_by_type[error["error_type"]].append(error)
        
        # Analyze missing required fields pattern
        if "missing_required_field" in errors_by_type:
            missing_field_errors = errors_by_type["missing_required_field"]
            affected_rows = [error["row_number"] for error in missing_field_errors]
            
            # Find most commonly missing fields
            missing_fields = []
            for error in missing_field_errors:
                # Handle both possible error message formats
                if "Missing required fields:" in error["error_message"]:
                    fields_part = error["error_message"].split("Missing required fields:")[1]
                    # Remove any trailing explanation text
                    fields_part = fields_part.split(".")[0]
                    fields = [f.strip() for f in fields_part.split(",")]
                    missing_fields.extend(fields)
                elif "Required fields are missing or empty:" in error["error_message"]:
                    fields_part = error["error_message"].split("Required fields are missing or empty:")[1]
                    # Remove any trailing explanation text
                    fields_part = fields_part.split(".")[0]
                    fields = [f.strip() for f in fields_part.split(",")]

            
            if missing_fields:
                most_common_missing = Counter(missing_fields).most_common(3)
                pattern = ErrorPattern(
                    error_type="missing_required_field",
                    pattern_description=f"Multiple rows missing required fields. Most common: {', '.join([f[0] for f in most_common_missing])}",
                    affected_rows=affected_rows,
                    severity=ErrorSeverity.HIGH,
                    suggested_fix="Review your Excel template and ensure all required columns are filled. Check the template instructions for required fields."
                )
                patterns.append(pattern)
        
        # Analyze lookup failures pattern
        if "lookup_failed" in errors_by_type:
            lookup_errors = errors_by_type["lookup_failed"]
            affected_rows = [error["row_number"] for error in lookup_errors]
            
            # Categorize lookup failures
            subject_failures = [e for e in lookup_errors if "Subject" in e["error_message"]]
            cognitive_failures = [e for e in lookup_errors if "Cognitive Learning" in e["error_message"]]
            difficulty_failures = [e for e in lookup_errors if "Difficulty" in e["error_message"]]
            
            if subject_failures:
                pattern = ErrorPattern(
                    error_type="lookup_failed",
                    pattern_description=f"Subject lookup failures in {len(subject_failures)} rows",
                    affected_rows=[e["row_number"] for e in subject_failures],
                    severity=ErrorSeverity.HIGH,
                    suggested_fix="Verify that all subjects in your Excel file exist in the system. Contact your administrator to add missing subjects."
                )
                patterns.append(pattern)
            
            if cognitive_failures:
                pattern = ErrorPattern(
                    error_type="lookup_failed",
                    pattern_description=f"Cognitive Learning lookup failures in {len(cognitive_failures)} rows",
                    affected_rows=[e["row_number"] for e in cognitive_failures],
                    severity=ErrorSeverity.MEDIUM,
                    suggested_fix="Use only valid Cognitive Learning values: 'Understanding' or 'Information'."
                )
                patterns.append(pattern)
            
            if difficulty_failures:
                pattern = ErrorPattern(
                    error_type="lookup_failed",
                    pattern_description=f"Difficulty lookup failures in {len(difficulty_failures)} rows",
                    affected_rows=[e["row_number"] for e in difficulty_failures],
                    severity=ErrorSeverity.MEDIUM,
                    suggested_fix="Use only valid Difficulty values: 'Easy', 'Medium', or 'Hard'."
                )
                patterns.append(pattern)
        
        # Analyze data type validation pattern
        if "invalid_data_type" in errors_by_type:
            data_type_errors = errors_by_type["invalid_data_type"]
            affected_rows = [error["row_number"] for error in data_type_errors]
            
            pattern = ErrorPattern(
                error_type="invalid_data_type",
                pattern_description=f"Data format issues in {len(data_type_errors)} rows",
                affected_rows=affected_rows,
                severity=ErrorSeverity.MEDIUM,
                suggested_fix="Check data formats: correct_answer should be A/B/C/D, Class should be numeric, and text fields should not exceed length limits."
            )
            patterns.append(pattern)
        
        self.error_patterns = patterns
        return patterns
    
    def generate_error_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive error report.
        
        Returns:
            Dict[str, Any]: Comprehensive error report with statistics and recommendations
        """
        statistics = self.get_error_statistics()
        patterns = self.analyze_error_patterns()
        
        # Generate recommendations based on patterns
        recommendations = []
        for pattern in patterns:
            recommendations.append({
                "issue": pattern.pattern_description,
                "severity": pattern.severity.value,
                "affected_rows_count": len(pattern.affected_rows),
                "suggested_fix": pattern.suggested_fix
            })
        
        return {
            "statistics": statistics,
            "patterns": [
                {
                    "error_type": p.error_type,
                    "description": p.pattern_description,
                    "affected_rows_count": len(p.affected_rows),
                    "severity": p.severity.value,
                    "suggested_fix": p.suggested_fix
                }
                for p in patterns
            ],
            "recommendations": recommendations,
            "summary": self._generate_summary_message(statistics, patterns)
        }
    
    def _generate_summary_message(
        self, 
        statistics: Dict[str, Any], 
        patterns: List[ErrorPattern]
    ) -> str:
        """
        Generate a summary message for the error report.
        
        Args:
            statistics: Error statistics
            patterns: Identified error patterns
            
        Returns:
            str: Summary message
        """
        total_errors = statistics["total_errors"]
        
        if total_errors == 0:
            return "No errors detected in the upload."
        
        # Find the most critical issues
        critical_patterns = [p for p in patterns if p.severity == ErrorSeverity.CRITICAL]
        high_patterns = [p for p in patterns if p.severity == ErrorSeverity.HIGH]
        
        if critical_patterns:
            return f"Found {total_errors} errors with {len(critical_patterns)} critical issues that need immediate attention."
        elif high_patterns:
            return f"Found {total_errors} errors with {len(high_patterns)} high-priority issues. Review the recommendations for quick fixes."
        else:
            return f"Found {total_errors} errors that are mostly minor issues. Review the error details and apply suggested fixes."
    
    def get_errors_by_type(self, error_type: str) -> List[Dict[str, Any]]:
        """
        Get all errors of a specific type.
        
        Args:
            error_type: Type of error to filter by
            
        Returns:
            List[Dict[str, Any]]: List of errors of the specified type
        """
        return [error for error in self.errors if error["error_type"] == error_type]
    
    def get_errors_by_severity(self, severity: ErrorSeverity) -> List[Dict[str, Any]]:
        """
        Get all errors of a specific severity level.
        
        Args:
            severity: Severity level to filter by
            
        Returns:
            List[Dict[str, Any]]: List of errors of the specified severity
        """
        return [error for error in self.errors if error["severity"] == severity.value]
    
    def clear_errors(self) -> None:
        """Clear all tracked errors."""
        self.errors.clear()
        self.error_patterns.clear()


# Create a global error tracker instance
error_tracker = ErrorTracker()