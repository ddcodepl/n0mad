#!/usr/bin/env python3
"""
Security audit script for Nomad global installation.
Checks for credential exposure, access control, and security best practices.
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
import json
import stat


class SecurityAuditor:
    """Perform comprehensive security audit of Nomad installation."""
    
    def __init__(self):
        self.results = {
            "timestamp": int(__import__("time").time()),
            "audit_version": "1.0",
            "findings": [],
            "recommendations": [],
            "summary": {}
        }
        self.sensitive_patterns = [
            r'sk-[a-zA-Z0-9]{40,}',  # OpenAI API keys
            r'sk-ant-[a-zA-Z0-9_-]+',  # Anthropic keys
            r'sk-or-[a-zA-Z0-9_-]+',  # OpenRouter keys
            r'secret_[a-zA-Z0-9]{40,}',  # Notion tokens
            r'[a-f0-9]{32}',  # Potential database IDs
        ]
    
    def add_finding(self, severity: str, category: str, title: str, description: str, recommendation: str = None):
        """Add a security finding."""
        finding = {
            "severity": severity,  # critical, high, medium, low, info
            "category": category,
            "title": title,
            "description": description
        }
        
        if recommendation:
            finding["recommendation"] = recommendation
            
        self.results["findings"].append(finding)
        
        if recommendation and recommendation not in self.results["recommendations"]:
            self.results["recommendations"].append(recommendation)
    
    def check_credential_exposure(self):
        """Check for credential exposure in command outputs."""
        print("🔍 Checking for credential exposure...")
        
        commands_to_test = [
            (["nomad", "--help"], "help output"),
            (["nomad", "--version"], "version output"),
            (["nomad", "--config-help"], "config help output")
        ]
        
        for command, description in commands_to_test:
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    # Check for credential patterns
                    exposed_patterns = []
                    for pattern in self.sensitive_patterns:
                        if re.search(pattern, result.stdout + result.stderr):
                            exposed_patterns.append(pattern)
                    
                    if exposed_patterns:
                        self.add_finding(
                            "critical",
                            "credential_exposure",
                            f"Credentials exposed in {description}",
                            f"Found potential credentials in {description}: {exposed_patterns}",
                            f"Ensure {description} does not contain actual API keys or tokens"
                        )
                    else:
                        print(f"  ✅ {description}: No credentials exposed")
                else:
                    print(f"  ⚠️  {description}: Command failed with return code {result.returncode}")
                    
            except subprocess.TimeoutExpired:
                print(f"  ❌ {description}: Command timed out")
            except Exception as e:
                print(f"  ❌ {description}: Error - {e}")
    
    def check_configuration_security(self):
        """Check configuration-related security issues."""
        print("⚙️  Checking configuration security...")
        
        try:
            # Test config status output for proper masking
            result = subprocess.run(["nomad", "--config-status"], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                # Check if sensitive values are masked
                has_masking = any(char in result.stdout for char in ['*', '…', '***'])
                
                if has_masking:
                    print("  ✅ Configuration values are properly masked")
                else:
                    self.add_finding(
                        "medium",
                        "configuration",
                        "Configuration values not masked",
                        "Configuration status output may expose sensitive values",
                        "Implement proper masking for sensitive configuration values"
                    )
                
                # Check for actual credential patterns in config output
                exposed_patterns = []
                for pattern in self.sensitive_patterns:
                    matches = re.findall(pattern, result.stdout)
                    if matches:
                        exposed_patterns.extend(matches)
                
                if exposed_patterns:
                    self.add_finding(
                        "critical",
                        "credential_exposure",
                        "Credentials exposed in configuration status",
                        f"Found {len(exposed_patterns)} potential credentials in config status output",
                        "Ensure configuration status properly masks all sensitive values"
                    )
                else:
                    print("  ✅ No credentials found in configuration output")
            else:
                print(f"  ⚠️  Config status command failed: {result.returncode}")
                if result.stderr:
                    print(f"     Error: {result.stderr[:100]}")
                    
        except Exception as e:
            print(f"  ❌ Configuration security check failed: {e}")
    
    def check_file_permissions(self):
        """Check file and directory permissions."""
        print("📁 Checking file permissions...")
        
        try:
            # Get expected directories from global config
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from utils.global_config import get_global_config
            
            config = get_global_config(strict_validation=False)
            directories_to_check = [
                ("Home directory", config.get_home_directory()),
                ("Tasks directory", config.get_tasks_directory())
            ]
            
            for name, directory_path in directories_to_check:
                if directory_path and Path(directory_path).exists():
                    self._check_directory_permissions(name, Path(directory_path))
                else:
                    print(f"  ℹ️  {name} does not exist: {directory_path}")
                    
        except Exception as e:
            print(f"  ❌ File permission check failed: {e}")
    
    def _check_directory_permissions(self, name: str, path: Path):
        """Check permissions for a specific directory."""
        try:
            stat_info = path.stat()
            permissions = stat.filemode(stat_info.st_mode)
            octal_permissions = oct(stat_info.st_mode)[-3:]
            
            print(f"  📁 {name}: {path}")
            print(f"     Permissions: {permissions} ({octal_permissions})")
            
            # Check if permissions are too permissive
            if stat_info.st_mode & stat.S_IWOTH:  # World writable
                self.add_finding(
                    "high",
                    "file_permissions",
                    f"{name} is world-writable",
                    f"Directory {path} has world-write permissions ({permissions})",
                    f"Restrict permissions on {path} using chmod 750 or similar"
                )
            elif stat_info.st_mode & stat.S_IROTH:  # World readable
                self.add_finding(
                    "medium",
                    "file_permissions",
                    f"{name} is world-readable",
                    f"Directory {path} has world-read permissions ({permissions})",
                    f"Consider restricting permissions on {path}"
                )
            else:
                print(f"     ✅ Permissions appear secure")
                
            # Check for config files in the directory
            for config_file in path.glob("*.env"):
                self._check_config_file_permissions(config_file)
                
        except Exception as e:
            print(f"  ❌ Could not check permissions for {path}: {e}")
    
    def _check_config_file_permissions(self, config_file: Path):
        """Check permissions for configuration files."""
        try:
            stat_info = config_file.stat()
            permissions = stat.filemode(stat_info.st_mode)
            octal_permissions = oct(stat_info.st_mode)[-3:]
            
            print(f"  📄 Config file: {config_file.name}")
            print(f"     Permissions: {permissions} ({octal_permissions})")
            
            # Config files should be restrictive (600 or 640)
            if stat_info.st_mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
                if stat_info.st_mode & (stat.S_IROTH | stat.S_IWOTH):
                    severity = "high"
                    issue = "world-accessible"
                else:
                    severity = "medium" 
                    issue = "group-accessible"
                    
                self.add_finding(
                    severity,
                    "file_permissions",
                    f"Config file {config_file.name} is {issue}",
                    f"Configuration file {config_file} has permissive permissions ({permissions})",
                    f"Set restrictive permissions: chmod 600 {config_file}"
                )
            else:
                print(f"     ✅ Config file permissions are secure")
                
        except Exception as e:
            print(f"  ❌ Could not check config file permissions: {e}")
    
    def check_environment_leakage(self):
        """Check for potential environment variable leakage."""
        print("🌍 Checking for environment leakage...")
        
        # Common places where environment variables might leak
        potential_leak_files = [
            ".bash_history",
            ".zsh_history", 
            ".history",
            "Dockerfile",
            "docker-compose.yml",
            ".github/workflows/*.yml",
            ".env.example",
            "README.md"
        ]
        
        current_dir = Path.cwd()
        leaked_files = []
        
        for file_pattern in potential_leak_files:
            if '*' in file_pattern:
                files = list(current_dir.glob(file_pattern))
            else:
                files = [current_dir / file_pattern] if (current_dir / file_pattern).exists() else []
            
            for file_path in files:
                if file_path.exists() and file_path.is_file():
                    try:
                        # Only check reasonably sized text files
                        if file_path.stat().st_size < 1024 * 1024:  # 1MB limit
                            content = file_path.read_text(encoding='utf-8', errors='ignore')
                            
                            # Check for credential patterns
                            found_patterns = []
                            for pattern in self.sensitive_patterns:
                                matches = re.findall(pattern, content)
                                if matches:
                                    found_patterns.extend(matches[:3])  # Limit to first 3 matches
                            
                            if found_patterns:
                                leaked_files.append((str(file_path), found_patterns))
                                
                    except Exception as e:
                        print(f"  ⚠️  Could not read {file_path}: {e}")
        
        if leaked_files:
            for file_path, patterns in leaked_files:
                self.add_finding(
                    "high",
                    "credential_leakage",
                    f"Potential credentials found in {Path(file_path).name}",
                    f"Found {len(patterns)} potential credential patterns in {file_path}",
                    f"Review and remove any actual credentials from {file_path}"
                )
                print(f"  ❌ Potential leakage in: {file_path}")
        else:
            print("  ✅ No obvious credential leakage found")
    
    def check_command_injection(self):
        """Check for potential command injection vulnerabilities."""
        print("💉 Checking for command injection risks...")
        
        # Test with potentially dangerous inputs
        dangerous_inputs = [
            "; echo 'injected'",
            "$(echo 'injected')",
            "`echo 'injected'`",
            "--help; echo 'injected'",
            "../../../etc/passwd"
        ]
        
        injection_found = False
        
        for dangerous_input in dangerous_inputs:
            try:
                # Test with --working-dir parameter
                result = subprocess.run(
                    ["nomad", "--working-dir", dangerous_input, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                # Check if injection succeeded
                if "injected" in result.stdout or "injected" in result.stderr:
                    self.add_finding(
                        "critical",
                        "command_injection",
                        "Command injection vulnerability found",
                        f"Input '{dangerous_input}' resulted in command injection",
                        "Implement proper input validation and sanitization"
                    )
                    injection_found = True
                    print(f"  ❌ Command injection possible with: {dangerous_input}")
                    
            except subprocess.TimeoutExpired:
                # Timeout might indicate hanging process due to injection
                print(f"  ⚠️  Timeout with input: {dangerous_input}")
            except Exception as e:
                # Expected for invalid inputs
                pass
        
        if not injection_found:
            print("  ✅ No command injection vulnerabilities found")
    
    def generate_report(self):
        """Generate comprehensive security audit report."""
        print("\n📋 Security Audit Summary")
        print("=" * 40)
        
        # Count findings by severity
        severity_counts = {}
        for finding in self.results["findings"]:
            severity = finding["severity"]
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Overall security score (0-100)
        total_findings = len(self.results["findings"])
        critical_count = severity_counts.get("critical", 0)
        high_count = severity_counts.get("high", 0)
        medium_count = severity_counts.get("medium", 0)
        
        # Calculate score (deduct points for findings)
        score = 100
        score -= critical_count * 30  # Critical: -30 points each
        score -= high_count * 15      # High: -15 points each  
        score -= medium_count * 5     # Medium: -5 points each
        score = max(0, score)         # Don't go below 0
        
        self.results["summary"] = {
            "total_findings": total_findings,
            "severity_breakdown": severity_counts,
            "security_score": score,
            "recommendations_count": len(self.results["recommendations"])
        }
        
        print(f"Security Score: {score}/100")
        print(f"Total Findings: {total_findings}")
        
        if severity_counts:
            print("Findings by Severity:")
            for severity in ["critical", "high", "medium", "low", "info"]:
                count = severity_counts.get(severity, 0)
                if count > 0:
                    icon = "🔴" if severity == "critical" else "🟡" if severity in ["high", "medium"] else "ℹ️"
                    print(f"  {icon} {severity.title()}: {count}")
        
        # Print top recommendations
        if self.results["recommendations"]:
            print(f"\nTop Recommendations:")
            for i, rec in enumerate(self.results["recommendations"][:5], 1):
                print(f"  {i}. {rec}")
        
        # Save detailed report
        report_file = Path("security_audit_report.json")
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        return report_file, score
    
    def run_full_audit(self):
        """Run complete security audit."""
        print("🔒 Starting Nomad Security Audit")
        print("=" * 40)
        
        self.check_credential_exposure()
        self.check_configuration_security()
        self.check_file_permissions()
        self.check_environment_leakage()
        self.check_command_injection()
        
        return self.generate_report()


def main():
    """Run security audit."""
    auditor = SecurityAuditor()
    report_file, score = auditor.run_full_audit()
    
    print(f"\n🎯 Audit Complete!")
    print(f"Security Score: {score}/100")
    print(f"Report: {report_file}")
    
    # Return appropriate exit code
    if score >= 80:
        print("✅ Good security posture")
        return 0
    elif score >= 60:
        print("⚠️  Security needs attention")
        return 1
    else:
        print("❌ Serious security issues found")
        return 2


if __name__ == "__main__":
    sys.exit(main())