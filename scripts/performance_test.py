#!/usr/bin/env python3
"""
Performance testing script for Nomad global installation.
Tests startup time, memory usage, and various configuration scenarios.
"""

import os
import sys
import time
import psutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any
import json


class PerformanceProfiler:
    """Profile performance characteristics of Nomad installation."""
    
    def __init__(self):
        self.results = {
            "timestamp": time.time(),
            "system_info": self._get_system_info(),
            "tests": {}
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for context."""
        return {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": sys.platform,
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "nomad_location": subprocess.run(["which", "nomad"], capture_output=True, text=True).stdout.strip()
        }
    
    def time_command(self, command: List[str], description: str) -> Dict[str, Any]:
        """Time execution of a command and measure resource usage."""
        print(f"Testing: {description}")
        
        # Get baseline memory
        process = psutil.Process()
        baseline_memory = process.memory_info().rss
        
        start_time = time.time()
        start_cpu = time.process_time()
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            end_time = time.time()
            end_cpu = time.process_time()
            
            # Measure memory after command
            final_memory = process.memory_info().rss
            
            execution_data = {
                "success": result.returncode == 0,
                "wall_time": end_time - start_time,
                "cpu_time": end_cpu - start_cpu,
                "memory_used": final_memory - baseline_memory,
                "return_code": result.returncode,
                "stdout_lines": len(result.stdout.splitlines()) if result.stdout else 0,
                "stderr_lines": len(result.stderr.splitlines()) if result.stderr else 0
            }
            
            if result.stderr:
                execution_data["stderr_sample"] = result.stderr[:200]
            
            print(f"  ✅ {description}: {execution_data['wall_time']:.3f}s")
            return execution_data
            
        except subprocess.TimeoutExpired:
            print(f"  ❌ {description}: Timeout after 30s")
            return {
                "success": False,
                "wall_time": 30.0,
                "cpu_time": 0,
                "memory_used": 0,
                "return_code": -1,
                "error": "timeout"
            }
        except Exception as e:
            print(f"  ❌ {description}: Error - {e}")
            return {
                "success": False,
                "wall_time": 0,
                "cpu_time": 0,
                "memory_used": 0,
                "return_code": -1,
                "error": str(e)
            }
    
    def test_basic_commands(self):
        """Test basic command performance."""
        print("\n📊 Testing Basic Commands")
        print("=" * 40)
        
        commands = [
            (["nomad", "--version"], "Version check"),
            (["nomad", "--help"], "Help display"),
            (["nomad", "--config-help"], "Configuration help"),
            (["nomad", "--config-status"], "Configuration status"),
            (["nomad", "--health-check"], "Health check")
        ]
        
        test_results = {}
        for command, description in commands:
            test_results[description.lower().replace(" ", "_")] = self.time_command(command, description)
        
        self.results["tests"]["basic_commands"] = test_results
    
    def test_directory_independence(self):
        """Test performance from different directories."""
        print("\n📁 Testing Directory Independence")
        print("=" * 40)
        
        test_directories = [
            Path.home(),
            Path("/tmp"),
            Path.cwd(),
            Path.cwd() / "clients"
        ]
        
        test_results = {}
        for directory in test_directories:
            if directory.exists():
                print(f"Testing from: {directory}")
                
                # Change to directory and test
                original_cwd = Path.cwd()
                try:
                    os.chdir(directory)
                    result = self.time_command(["nomad", "--version"], f"Version from {directory.name}")
                    test_results[str(directory)] = result
                finally:
                    os.chdir(original_cwd)
            else:
                print(f"Skipping non-existent directory: {directory}")
        
        self.results["tests"]["directory_independence"] = test_results
    
    def test_configuration_scenarios(self):
        """Test performance with different configuration scenarios."""
        print("\n⚙️  Testing Configuration Scenarios")
        print("=" * 40)
        
        scenarios = [
            ("minimal", {}),  # No additional env vars
            ("full_config", {
                "NOMAD_LOG_LEVEL": "DEBUG",
                "NOMAD_MAX_CONCURRENT_TASKS": "5"
            }),
            ("custom_paths", {
                "NOMAD_HOME": "/tmp/nomad_test",
                "NOMAD_TASKS_DIR": "/tmp/nomad_test/tasks"
            })
        ]
        
        test_results = {}
        original_env = dict(os.environ)
        
        for scenario_name, env_vars in scenarios:
            print(f"Testing scenario: {scenario_name}")
            
            # Set environment variables
            for key, value in env_vars.items():
                os.environ[key] = value
            
            try:
                result = self.time_command(["nomad", "--config-status"], f"Config status - {scenario_name}")
                test_results[scenario_name] = result
            finally:
                # Restore original environment
                os.environ.clear()
                os.environ.update(original_env)
        
        self.results["tests"]["configuration_scenarios"] = test_results
    
    def test_concurrent_execution(self):
        """Test concurrent command execution."""
        print("\n🚀 Testing Concurrent Execution")
        print("=" * 40)
        
        import concurrent.futures
        import threading
        
        def run_version_check():
            return subprocess.run(["nomad", "--version"], capture_output=True, text=True)
        
        # Test with different concurrency levels
        concurrency_levels = [1, 2, 5, 10]
        test_results = {}
        
        for level in concurrency_levels:
            print(f"Testing {level} concurrent executions")
            
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=level) as executor:
                futures = [executor.submit(run_version_check) for _ in range(level)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            end_time = time.time()
            
            success_count = sum(1 for r in results if r.returncode == 0)
            
            test_results[f"concurrency_{level}"] = {
                "total_time": end_time - start_time,
                "success_count": success_count,
                "total_count": level,
                "success_rate": success_count / level
            }
            
            print(f"  ✅ {level} concurrent: {end_time - start_time:.3f}s, {success_count}/{level} successful")
        
        self.results["tests"]["concurrent_execution"] = test_results
    
    def run_security_audit(self):
        """Run basic security audit checks."""
        print("\n🔒 Security Audit")
        print("=" * 40)
        
        security_results = {}
        
        # Test 1: Check for credential exposure in help output
        help_result = subprocess.run(["nomad", "--help"], capture_output=True, text=True)
        security_results["help_credential_exposure"] = {
            "clean": "api" not in help_result.stdout.lower() and "token" not in help_result.stdout.lower()
        }
        
        # Test 2: Check for credential exposure in version output
        version_result = subprocess.run(["nomad", "--version"], capture_output=True, text=True)
        security_results["version_credential_exposure"] = {
            "clean": "api" not in version_result.stdout.lower() and "token" not in version_result.stdout.lower()
        }
        
        # Test 3: Check configuration status masks credentials
        config_result = subprocess.run(["nomad", "--config-status"], capture_output=True, text=True)
        has_masked_values = "***" in config_result.stdout or "*" in config_result.stdout
        security_results["config_credential_masking"] = {
            "masks_credentials": has_masked_values
        }
        
        # Test 4: Check file permissions on created directories
        try:
            from utils.global_config import get_global_config
            config = get_global_config()
            home_dir = config.get_home_directory()
            
            if Path(home_dir).exists():
                stat_info = os.stat(home_dir)
                permissions = oct(stat_info.st_mode)[-3:]
                security_results["directory_permissions"] = {
                    "home_dir": str(home_dir),
                    "permissions": permissions,
                    "secure": permissions in ["700", "750", "755"]  # Reasonable permissions
                }
        except Exception as e:
            security_results["directory_permissions"] = {"error": str(e)}
        
        self.results["tests"]["security_audit"] = security_results
        
        # Print security summary
        print("Security Audit Results:")
        for test_name, result in security_results.items():
            if isinstance(result, dict) and "error" not in result:
                status = "✅" if any(result.values()) else "⚠️"
                print(f"  {status} {test_name}: {result}")
            else:
                print(f"  ❌ {test_name}: {result}")
    
    def generate_report(self):
        """Generate performance and security report."""
        print("\n📋 Performance Report")
        print("=" * 40)
        
        # Basic command performance summary
        if "basic_commands" in self.results["tests"]:
            print("Basic Command Performance:")
            for cmd, data in self.results["tests"]["basic_commands"].items():
                if data["success"]:
                    print(f"  {cmd}: {data['wall_time']:.3f}s")
                else:
                    print(f"  {cmd}: FAILED")
        
        # Directory independence summary
        if "directory_independence" in self.results["tests"]:
            print("\nDirectory Independence:")
            times = [data["wall_time"] for data in self.results["tests"]["directory_independence"].values() if data["success"]]
            if times:
                print(f"  Average time: {sum(times)/len(times):.3f}s")
                print(f"  Min time: {min(times):.3f}s")
                print(f"  Max time: {max(times):.3f}s")
        
        # Save detailed results
        report_file = Path("performance_report.json")
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        return report_file


def main():
    """Run comprehensive performance and security testing."""
    print("🏁 Nomad Performance and Security Testing")
    print("=" * 50)
    
    profiler = PerformanceProfiler()
    
    # Run performance tests
    profiler.test_basic_commands()
    profiler.test_directory_independence()
    profiler.test_configuration_scenarios()
    profiler.test_concurrent_execution()
    
    # Run security audit
    profiler.run_security_audit()
    
    # Generate report
    report_file = profiler.generate_report()
    
    print("\n🎉 Testing completed!")
    print(f"See {report_file} for detailed results.")


if __name__ == "__main__":
    main()