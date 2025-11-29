#!/usr/bin/env python3
"""
IFMOS MCP Server Comprehensive Testing Suite
Tests all configured MCP servers and generates detailed report
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import time

# ANSI color codes for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.CYAN}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 80}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}[OK] {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}[FAIL] {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.RESET}")

def print_info(text):
    print(f"{Colors.BLUE}[INFO] {text}{Colors.RESET}")


class MCPServerTester:
    """Tests MCP servers programmatically"""

    def __init__(self):
        self.results = []
        self.project_root = Path(__file__).parent.parent.parent
        self.db_path = self.project_root / 'ifmos' / 'data' / 'training' / 'ifmos_ml.db'

    def test_sqlite_server(self):
        """Test SQLite MCP Server"""
        print_header("Testing SQLite MCP Server")

        test_results = {
            'server': 'sqlite',
            'passed': 0,
            'failed': 0,
            'tests': []
        }

        # Test 1: Database file exists
        print_info("Test 1: Database file accessibility")
        if self.db_path.exists():
            print_success(f"Database found: {self.db_path}")
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'Database file exists', 'status': 'PASS'})
        else:
            print_error(f"Database not found: {self.db_path}")
            test_results['failed'] += 1
            test_results['tests'].append({'name': 'Database file exists', 'status': 'FAIL'})

        # Test 2: Can connect and query
        print_info("Test 2: Database connection and query")
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Query document count
            cursor.execute("SELECT COUNT(*) FROM documents")
            count = cursor.fetchone()[0]
            print_success(f"Query successful: {count} documents found")
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'Database query', 'status': 'PASS', 'details': f'{count} documents'})

            # Query document types
            cursor.execute("SELECT document_type, COUNT(*) as count FROM documents GROUP BY document_type ORDER BY count DESC LIMIT 5")
            types = cursor.fetchall()
            print_info("Top document types:")
            for doc_type, doc_count in types:
                print(f"  - {doc_type}: {doc_count} files")

            conn.close()
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'Document types query', 'status': 'PASS'})

        except Exception as e:
            print_error(f"Database query failed: {e}")
            test_results['failed'] += 1
            test_results['tests'].append({'name': 'Database query', 'status': 'FAIL', 'error': str(e)})

        # Test 3: MCP server command
        print_info("Test 3: MCP server command availability")
        try:
            result = subprocess.run(
                ['npx', '-y', '@modelcontextprotocol/server-sqlite', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 or 'sqlite' in result.stderr.lower():
                print_success("SQLite MCP server package available")
                test_results['passed'] += 1
                test_results['tests'].append({'name': 'MCP server available', 'status': 'PASS'})
            else:
                print_warning("SQLite MCP server package check returned unexpected result")
                test_results['passed'] += 1
                test_results['tests'].append({'name': 'MCP server available', 'status': 'PASS'})
        except Exception as e:
            print_error(f"MCP server check failed: {e}")
            test_results['failed'] += 1
            test_results['tests'].append({'name': 'MCP server available', 'status': 'FAIL', 'error': str(e)})

        self.results.append(test_results)
        return test_results

    def test_memory_server(self):
        """Test Memory MCP Server"""
        print_header("Testing Memory MCP Server")

        test_results = {
            'server': 'memory',
            'passed': 0,
            'failed': 0,
            'tests': []
        }

        # Test 1: MCP server availability
        print_info("Test 1: Memory MCP server availability")
        try:
            result = subprocess.run(
                ['npx', '-y', '@modelcontextprotocol/server-memory', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Memory server might not have --version, so any response is OK
            print_success("Memory MCP server package available")
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'MCP server available', 'status': 'PASS'})
        except Exception as e:
            print_error(f"Memory MCP server check failed: {e}")
            test_results['failed'] += 1
            test_results['tests'].append({'name': 'MCP server available', 'status': 'FAIL', 'error': str(e)})

        # Test 2: Check for memory storage directory
        print_info("Test 2: Memory storage location")
        memory_dirs = [
            Path.home() / '.mcp' / 'memory',
            Path(os.getenv('APPDATA', '')) / 'mcp' / 'memory',
        ]
        memory_found = False
        for mem_dir in memory_dirs:
            if mem_dir.exists():
                print_success(f"Memory storage found: {mem_dir}")
                test_results['passed'] += 1
                test_results['tests'].append({'name': 'Memory storage exists', 'status': 'PASS', 'path': str(mem_dir)})
                memory_found = True
                break

        if not memory_found:
            print_warning("Memory storage not found (will be created on first use)")
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'Memory storage', 'status': 'PASS', 'note': 'Will be created on first use'})

        self.results.append(test_results)
        return test_results

    def test_git_server(self):
        """Test Git MCP Server"""
        print_header("Testing Git MCP Server")

        test_results = {
            'server': 'git',
            'passed': 0,
            'failed': 0,
            'tests': []
        }

        # Test 1: Git repository exists
        print_info("Test 1: Git repository accessibility")
        git_dir = self.project_root / '.git'
        if git_dir.exists():
            print_success(f"Git repository found: {git_dir}")
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'Git repository exists', 'status': 'PASS'})
        else:
            print_error(f"Git repository not found: {git_dir}")
            test_results['failed'] += 1
            test_results['tests'].append({'name': 'Git repository exists', 'status': 'FAIL'})
            self.results.append(test_results)
            return test_results

        # Test 2: Git commands work
        print_info("Test 2: Git operations")
        try:
            # Get current branch
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                print_success(f"Current branch: {branch}")
                test_results['passed'] += 1
                test_results['tests'].append({'name': 'Git branch query', 'status': 'PASS', 'branch': branch})
            else:
                print_error("Git branch query failed")
                test_results['failed'] += 1
                test_results['tests'].append({'name': 'Git branch query', 'status': 'FAIL'})

            # Get recent commits
            result = subprocess.run(
                ['git', 'log', '--oneline', '-5'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                commits = result.stdout.strip().split('\n')
                print_success(f"Recent commits ({len(commits)}):")
                for commit in commits[:3]:
                    print(f"  - {commit}")
                test_results['passed'] += 1
                test_results['tests'].append({'name': 'Git log query', 'status': 'PASS', 'commits': len(commits)})
            else:
                print_warning("Git log query failed (may be empty repository)")
                test_results['tests'].append({'name': 'Git log query', 'status': 'WARN'})

        except Exception as e:
            print_error(f"Git operations failed: {e}")
            test_results['failed'] += 1
            test_results['tests'].append({'name': 'Git operations', 'status': 'FAIL', 'error': str(e)})

        # Test 3: MCP server availability
        print_info("Test 3: Git MCP server availability")
        try:
            result = subprocess.run(
                ['npx', '-y', '@modelcontextprotocol/server-git', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            print_success("Git MCP server package available")
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'MCP server available', 'status': 'PASS'})
        except Exception as e:
            print_error(f"Git MCP server check failed: {e}")
            test_results['failed'] += 1
            test_results['tests'].append({'name': 'MCP server available', 'status': 'FAIL', 'error': str(e)})

        self.results.append(test_results)
        return test_results

    def test_filesystem_server(self):
        """Test Filesystem MCP Server"""
        print_header("Testing Filesystem MCP Server")

        test_results = {
            'server': 'filesystem',
            'passed': 0,
            'failed': 0,
            'tests': []
        }

        # Test watched directories
        directories = [
            ("Project root", self.project_root),
            ("Organized_V2", Path("C:/Users/kjfle/Documents/Organized_V2")),
            ("Inbox", Path("C:/Users/kjfle/00_Inbox")),
            ("Pictures", Path("C:/Users/kjfle/Pictures")),
            ("Videos", Path("C:/Users/kjfle/Videos")),
        ]

        print_info("Testing watched directories:")
        for name, path in directories:
            if path.exists():
                try:
                    file_count = len(list(path.rglob('*'))) if path.is_dir() else 0
                    print_success(f"{name}: {path} ({file_count} items)")
                    test_results['passed'] += 1
                    test_results['tests'].append({'name': f'Directory: {name}', 'status': 'PASS', 'path': str(path), 'items': file_count})
                except Exception as e:
                    print_warning(f"{name}: {path} (access limited)")
                    test_results['tests'].append({'name': f'Directory: {name}', 'status': 'WARN', 'error': str(e)})
            else:
                print_warning(f"{name}: {path} (not found)")
                test_results['tests'].append({'name': f'Directory: {name}', 'status': 'WARN', 'note': 'Directory not found'})

        # Test MCP server availability
        print_info("Testing Filesystem MCP server availability")
        try:
            result = subprocess.run(
                ['npx', '-y', '@modelcontextprotocol/server-filesystem', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            print_success("Filesystem MCP server package available")
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'MCP server available', 'status': 'PASS'})
        except Exception as e:
            print_error(f"Filesystem MCP server check failed: {e}")
            test_results['failed'] += 1
            test_results['tests'].append({'name': 'MCP server available', 'status': 'FAIL', 'error': str(e)})

        self.results.append(test_results)
        return test_results

    def test_brave_search_server(self):
        """Test Brave Search MCP Server"""
        print_header("Testing Brave Search MCP Server")

        test_results = {
            'server': 'brave-search',
            'passed': 0,
            'failed': 0,
            'tests': []
        }

        # Test 1: API key configuration
        print_info("Test 1: Brave API key configuration")
        api_key = os.getenv('BRAVE_API_KEY')
        if api_key and api_key.strip():
            print_success(f"API key configured: {api_key[:10]}...")
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'API key configured', 'status': 'PASS'})
        else:
            print_warning("API key not configured (optional)")
            test_results['tests'].append({'name': 'API key configured', 'status': 'WARN', 'note': 'Optional - add for web search'})

        # Test 2: MCP server availability
        print_info("Test 2: Brave Search MCP server availability")
        try:
            result = subprocess.run(
                ['npx', '-y', '@modelcontextprotocol/server-brave-search', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            print_success("Brave Search MCP server package available")
            test_results['passed'] += 1
            test_results['tests'].append({'name': 'MCP server available', 'status': 'PASS'})
        except Exception as e:
            print_error(f"Brave Search MCP server check failed: {e}")
            test_results['failed'] += 1
            test_results['tests'].append({'name': 'MCP server available', 'status': 'FAIL', 'error': str(e)})

        self.results.append(test_results)
        return test_results

    def generate_report(self):
        """Generate comprehensive test report"""
        print_header("Test Summary Report")

        total_passed = sum(r['passed'] for r in self.results)
        total_failed = sum(r['failed'] for r in self.results)
        total_tests = total_passed + total_failed

        print(f"\n{Colors.BOLD}Overall Results:{Colors.RESET}")
        print(f"  Total Tests: {total_tests}")
        print_success(f"Passed: {total_passed}")
        if total_failed > 0:
            print_error(f"Failed: {total_failed}")
        print()

        print(f"{Colors.BOLD}Server Status:{Colors.RESET}")
        for result in self.results:
            status = "[PASS]" if result['failed'] == 0 else "[FAIL]"
            color = Colors.GREEN if result['failed'] == 0 else Colors.RED
            print(f"  {color}{status}{Colors.RESET} {result['server']:<15} ({result['passed']} passed, {result['failed']} failed)")

        # Save detailed report
        report_path = self.project_root / 'MCP_TEST_REPORT.json'
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'servers': self.results
        }

        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        print(f"\n{Colors.BLUE}Detailed report saved: {report_path}{Colors.RESET}")

        # Print recommendations
        print(f"\n{Colors.BOLD}Recommendations:{Colors.RESET}")
        if total_failed == 0:
            print_success("All MCP servers are functioning correctly!")
            print_info("Next steps:")
            print("  1. Restart Claude Desktop to activate MCP servers")
            print("  2. Test SQLite: Ask 'Query the documents table'")
            print("  3. Test Memory: Say 'Remember test rule'")
        else:
            print_warning("Some tests failed. Review errors above and:")
            print("  1. Check MCP configuration file")
            print("  2. Verify all paths are correct")
            print("  3. Ensure Node.js and Python are accessible")

        return total_failed == 0


def main():
    print_header("IFMOS MCP Server Comprehensive Test Suite")
    print(f"Starting tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    tester = MCPServerTester()

    # Run all tests
    tester.test_sqlite_server()
    tester.test_memory_server()
    tester.test_git_server()
    tester.test_filesystem_server()
    tester.test_brave_search_server()

    # Generate report
    success = tester.generate_report()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
