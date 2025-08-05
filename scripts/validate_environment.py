#!/usr/bin/env python3
"""
Environment Configuration Validation Script for Nomad

This script validates environment variables and configuration for the Nomad application.
It can be used during deployment, testing, or troubleshooting to ensure all required
configuration is properly set.

Usage:
    python3 scripts/validate_environment.py
    python3 scripts/validate_environment.py --strict
    python3 scripts/validate_environment.py --env-file .env.production
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.global_config import GlobalConfigManager
from utils.env_security import EnvironmentSecurityManager

class EnvironmentValidator:
    """Validates Nomad environment configuration."""
    
    def __init__(self, strict_mode: bool = False, env_file: Optional[str] = None):
        self.strict_mode = strict_mode
        self.env_file = env_file
        self.security_manager = EnvironmentSecurityManager()
        self.issues = []
        self.warnings = []
        
    def load_environment(self):
        """Load environment variables from file if specified."""
        if self.env_file:
            env_path = Path(self.env_file)
            if env_path.exists():
                print(f"📁 Loading environment from: {env_path}")
                load_dotenv(env_path)
            else:
                print(f"❌ Environment file not found: {env_path}")
                if self.strict_mode:
                    sys.exit(1)
    
    def validate_required_variables(self) -> bool:
        """Validate required environment variables."""
        print("🔍 Validating required environment variables...")
        
        required_vars = {
            'NOTION_TOKEN': 'Notion API integration token',
            'NOTION_BOARD_DB': 'Notion database ID for task management'
        }
        
        # At least one AI provider is required
        ai_providers = {
            'OPENAI_API_KEY': 'OpenAI API key',
            'ANTHROPIC_API_KEY': 'Anthropic API key', 
            'OPENROUTER_API_KEY': 'OpenRouter API key'
        }
        
        success = True
        
        # Check required variables
        for var_name, description in required_vars.items():
            value = os.getenv(var_name)
            if not value or not value.strip():
                self.issues.append(f"Missing required variable: {var_name} ({description})")
                success = False
            else:
                print(f"  ✅ {var_name}: Configured")
        
        # Check AI providers
        ai_provider_found = False
        for var_name, description in ai_providers.items():
            value = os.getenv(var_name)
            if value and value.strip():
                ai_provider_found = True
                print(f"  ✅ {var_name}: Configured")
                
                # Validate API key format
                is_valid, format_issues = self.security_manager.validate_api_key_format(
                    var_name.replace('_API_KEY', '').lower(), value
                )
                if not is_valid:
                    self.warnings.extend([f"{var_name}: {issue}" for issue in format_issues])
            else:
                print(f"  ⚪ {var_name}: Not configured")
        
        if not ai_provider_found:
            self.issues.append("No AI provider API keys configured. At least one of OPENAI_API_KEY, ANTHROPIC_API_KEY, or OPENROUTER_API_KEY is required.")
            success = False
        else:
            print(f"  ✅ AI Provider: At least one configured")
            
        return success
    
    def validate_optional_variables(self):
        """Validate optional environment variables."""
        print("\n🔧 Checking optional configuration...")
        
        optional_vars = {
            'NOMAD_HOME': ('/app/.nomad', 'Base directory for Nomad files'),
            'NOMAD_TASKS_DIR': ('/app/tasks', 'Directory for task files'),
            'NOMAD_LOG_LEVEL': ('INFO', 'Logging level'),
            'NOMAD_MAX_CONCURRENT_TASKS': ('3', 'Maximum concurrent tasks'),
            'TASKS_DIR': ('./tasks', 'Legacy task directory'),
        }
        
        for var_name, (default_value, description) in optional_vars.items():
            value = os.getenv(var_name, default_value)
            print(f"  ⚙️  {var_name}: {value} ({description})")
    
    def validate_slack_configuration(self):
        """Validate Slack integration configuration."""
        print("\n💬 Checking Slack integration...")
        
        slack_enabled = os.getenv('SLACK_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
        slack_bot_token = os.getenv('SLACK_BOT_TOKEN')
        
        if slack_enabled:
            if slack_bot_token:
                print("  ✅ Slack: Enabled and configured")
                
                # Check additional Slack configuration
                slack_vars = {
                    'SLACK_DEFAULT_CHANNEL': '#general',
                    'SLACK_ERROR_CHANNEL': '#errors',
                    'SLACK_RATE_LIMIT_PER_MINUTE': '60',
                    'SLACK_RETRY_ATTEMPTS': '3',
                    'SLACK_TIMEOUT': '30'
                }
                
                for var_name, default_value in slack_vars.items():
                    value = os.getenv(var_name, default_value)
                    print(f"    ⚙️  {var_name}: {value}")
                    
            else:
                self.warnings.append("Slack notifications enabled but SLACK_BOT_TOKEN not configured")
                print("  ⚠️  Slack: Enabled but token missing")
        else:
            print("  ⚪ Slack: Disabled")
    
    def validate_docker_environment(self):
        """Validate Docker-specific configuration."""
        print("\n🐳 Checking Docker environment...")
        
        docker_env = os.getenv('NOMAD_DOCKER_ENV')
        if docker_env:
            print("  ✅ Docker: Running in container")
            
            # Check Docker-specific variables
            docker_vars = {
                'PYTHONDONTWRITEBYTECODE': '1',
                'PYTHONUNBUFFERED': '1', 
                'PYTHONPATH': '/app'
            }
            
            for var_name, expected_value in docker_vars.items():
                value = os.getenv(var_name, '')
                if value == expected_value:
                    print(f"    ✅ {var_name}: {value}")
                else:
                    print(f"    ⚠️  {var_name}: {value} (expected: {expected_value})")
        else:
            print("  ⚪ Docker: Not detected (local development)")
    
    def validate_file_permissions(self):
        """Validate file system permissions."""
        print("\n📁 Checking file system access...")
        
        paths_to_check = [
            os.getenv('NOMAD_HOME', '/app/.nomad'),
            os.getenv('NOMAD_TASKS_DIR', '/app/tasks'),
            '/app/logs',
            '/app/data'
        ]
        
        for path_str in paths_to_check:
            path = Path(path_str)
            try:
                # Check if path exists or can be created
                if path.exists():
                    if os.access(path, os.R_OK | os.W_OK):
                        print(f"  ✅ {path}: Accessible")
                    else:
                        self.issues.append(f"Path not writable: {path}")
                        print(f"  ❌ {path}: No write access")
                else:
                    # Try to create directory
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                        print(f"  ✅ {path}: Created")
                    except PermissionError:
                        self.issues.append(f"Cannot create directory: {path}")
                        print(f"  ❌ {path}: Cannot create")
            except Exception as e:
                self.warnings.append(f"Error checking path {path}: {e}")
                print(f"  ⚠️  {path}: Error checking - {e}")
    
    def validate_network_connectivity(self):
        """Validate external service connectivity (optional check)."""
        print("\n🌐 Checking external service connectivity...")
        
        # This is a basic check - in production you might want more sophisticated testing
        services = [
            'api.notion.com',
            'api.openai.com', 
            'api.anthropic.com',
            'openrouter.ai'
        ]
        
        # Note: We don't actually test connectivity here to avoid API calls
        # In production, you might implement actual connectivity tests
        print("  ℹ️  Network connectivity testing skipped (configure as needed)")
        for service in services:
            print(f"    📡 {service}: Assumed accessible")
    
    def generate_report(self) -> bool:
        """Generate final validation report."""
        print("\n" + "="*60)
        print("📊 VALIDATION REPORT")
        print("="*60)
        
        success = len(self.issues) == 0
        
        if success:
            print("✅ CONFIGURATION VALID")
            print("   All required configuration is present and valid.")
        else:
            print("❌ CONFIGURATION ISSUES FOUND")
            print(f"   {len(self.issues)} critical issues need attention:")
            for issue in self.issues:
                print(f"   🔴 {issue}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)} found):")
            for warning in self.warnings:
                print(f"   🟡 {warning}")
        
        print("\n📋 RECOMMENDATIONS:")
        if not success:
            print("   1. Fix all critical issues listed above")
            print("   2. Ensure all required environment variables are set")
            print("   3. Verify API key formats are correct")
        
        if self.warnings:
            print("   4. Review warnings and address as needed")
            
        print("   5. Test configuration with: python3 -m entry.main --config-status")
        print("   6. Run application health check after fixes")
        
        return success
    
    def run_validation(self) -> bool:
        """Run complete validation process."""
        print("🚀 Nomad Environment Configuration Validator")
        print("="*60)
        
        # Load environment
        self.load_environment()
        
        # Run validation steps
        required_valid = self.validate_required_variables()
        self.validate_optional_variables()
        self.validate_slack_configuration()
        self.validate_docker_environment()
        self.validate_file_permissions()
        self.validate_network_connectivity()
        
        # Generate report
        success = self.generate_report()
        
        return success

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Validate Nomad environment configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/validate_environment.py
  python3 scripts/validate_environment.py --strict
  python3 scripts/validate_environment.py --env-file .env.production
  
Exit codes:
  0: Configuration valid
  1: Configuration issues found (in strict mode)
  2: Validation script error
        """
    )
    
    parser.add_argument(
        '--strict', 
        action='store_true',
        help='Exit with error code if issues found'
    )
    
    parser.add_argument(
        '--env-file',
        help='Load environment variables from specified file'
    )
    
    args = parser.parse_args()
    
    try:
        validator = EnvironmentValidator(
            strict_mode=args.strict,
            env_file=args.env_file
        )
        
        success = validator.run_validation()
        
        if args.strict and not success:
            print("\n❌ Validation failed in strict mode")
            sys.exit(1)
        elif success:
            print("\n🎉 Validation completed successfully")
            sys.exit(0)
        else:
            print("\n⚠️  Validation completed with warnings")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n💥 Validation script error: {e}")
        sys.exit(2)

if __name__ == '__main__':
    main()