"""
Import organization utilities following PEP 8 standards.
"""

import ast
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class ImportType(Enum):
    """Types of imports for organization."""

    STANDARD_LIBRARY = "standard"
    THIRD_PARTY = "third_party"
    LOCAL = "local"
    RELATIVE = "relative"


@dataclass
class ImportStatement:
    """Represents an import statement."""

    module: str
    names: List[str]
    alias: Optional[str]
    import_type: ImportType
    line_number: int
    is_from_import: bool

    def __str__(self) -> str:
        """Convert to import statement string."""
        if self.is_from_import:
            if self.names == ["*"]:
                return f"from {self.module} import *"
            elif len(self.names) == 1 and self.alias:
                return f"from {self.module} import {self.names[0]} as {self.alias}"
            elif len(self.names) == 1:
                return f"from {self.module} import {self.names[0]}"
            else:
                # Multiple imports
                if len(self.names) <= 3:
                    names_str = ", ".join(self.names)
                    return f"from {self.module} import {names_str}"
                else:
                    # Multi-line import
                    names_str = ",\n    ".join(self.names)
                    return f"from {self.module} import (\n    {names_str}\n)"
        else:
            if self.alias:
                return f"import {self.module} as {self.alias}"
            else:
                return f"import {self.module}"


class ImportOrganizer:
    """Organizes imports according to PEP 8 standards."""

    # Standard library modules (Python 3.11+)
    STANDARD_LIBRARY_MODULES = {
        "abc",
        "aifc",
        "argparse",
        "array",
        "ast",
        "asynchat",
        "asyncio",
        "asyncore",
        "base64",
        "bdb",
        "binascii",
        "binhex",
        "bisect",
        "builtins",
        "bz2",
        "calendar",
        "cgi",
        "cgitb",
        "chunk",
        "cmd",
        "code",
        "codecs",
        "codeop",
        "collections",
        "colorsys",
        "compileall",
        "concurrent",
        "configparser",
        "contextlib",
        "copy",
        "copyreg",
        "cProfile",
        "csv",
        "ctypes",
        "curses",
        "dataclasses",
        "datetime",
        "dbm",
        "decimal",
        "difflib",
        "dis",
        "doctest",
        "email",
        "encodings",
        "enum",
        "errno",
        "faulthandler",
        "fcntl",
        "filecmp",
        "fileinput",
        "fnmatch",
        "fractions",
        "ftplib",
        "functools",
        "gc",
        "getopt",
        "getpass",
        "gettext",
        "glob",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "imaplib",
        "imghdr",
        "imp",
        "importlib",
        "inspect",
        "io",
        "ipaddress",
        "itertools",
        "json",
        "keyword",
        "lib2to3",
        "linecache",
        "locale",
        "logging",
        "lzma",
        "mailbox",
        "mailcap",
        "marshal",
        "math",
        "mimetypes",
        "mmap",
        "modulefinder",
        "multiprocessing",
        "netrc",
        "numbers",
        "operator",
        "optparse",
        "os",
        "ossaudiodev",
        "pathlib",
        "pdb",
        "pickle",
        "pickletools",
        "pipes",
        "pkgutil",
        "platform",
        "plistlib",
        "poplib",
        "posix",
        "pprint",
        "profile",
        "pstats",
        "pty",
        "pwd",
        "py_compile",
        "pyclbr",
        "pydoc",
        "queue",
        "quopri",
        "random",
        "re",
        "readline",
        "reprlib",
        "resource",
        "rlcompleter",
        "runpy",
        "sched",
        "secrets",
        "select",
        "selectors",
        "shelve",
        "shlex",
        "shutil",
        "signal",
        "site",
        "smtpd",
        "smtplib",
        "sndhdr",
        "socket",
        "socketserver",
        "sqlite3",
        "ssl",
        "stat",
        "statistics",
        "string",
        "stringprep",
        "struct",
        "subprocess",
        "sunau",
        "sys",
        "sysconfig",
        "syslog",
        "tabnanny",
        "tarfile",
        "tempfile",
        "termios",
        "textwrap",
        "threading",
        "time",
        "timeit",
        "tkinter",
        "token",
        "tokenize",
        "trace",
        "traceback",
        "tracemalloc",
        "tty",
        "turtle",
        "types",
        "typing",
        "typing_extensions",
        "unicodedata",
        "unittest",
        "urllib",
        "uuid",
        "venv",
        "warnings",
        "wave",
        "weakref",
        "webbrowser",
        "winreg",
        "winsound",
        "wsgiref",
        "xdrlib",
        "xml",
        "xmlrpc",
        "zipapp",
        "zipfile",
        "zipimport",
        "zlib",
    }

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize import organizer."""
        self.project_root = project_root or Path.cwd()

    def parse_imports(self, file_content: str) -> List[ImportStatement]:
        """Parse imports from file content."""
        imports = []

        try:
            tree = ast.parse(file_content)
        except SyntaxError:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_stmt = ImportStatement(
                        module=alias.name,
                        names=[alias.name.split(".")[-1]],
                        alias=alias.asname,
                        import_type=self._classify_import(alias.name),
                        line_number=node.lineno,
                        is_from_import=False,
                    )
                    imports.append(import_stmt)

            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue  # Skip problematic relative imports

                names = []
                for alias in node.names:
                    names.append(alias.name)

                import_stmt = ImportStatement(
                    module=node.module,
                    names=names,
                    alias=node.names[0].asname if len(node.names) == 1 else None,
                    import_type=self._classify_import(node.module, node.level > 0),
                    line_number=node.lineno,
                    is_from_import=True,
                )
                imports.append(import_stmt)

        return imports

    def _classify_import(self, module_name: str, is_relative: bool = False) -> ImportType:
        """Classify import type."""
        if is_relative or module_name.startswith("."):
            return ImportType.RELATIVE

        # Check if it's a standard library module
        top_level = module_name.split(".")[0]
        if top_level in self.STANDARD_LIBRARY_MODULES:
            return ImportType.STANDARD_LIBRARY

        # Check if it's a local module (relative to project root)
        if self._is_local_module(module_name):
            return ImportType.LOCAL

        return ImportType.THIRD_PARTY

    def _is_local_module(self, module_name: str) -> bool:
        """Check if module is local to the project."""
        # Simple heuristic: if module starts with known local package names
        local_packages = {"utils", "core", "clients", "entry", "tasks"}
        top_level = module_name.split(".")[0]
        return top_level in local_packages

    def organize_imports(self, imports: List[ImportStatement]) -> str:
        """Organize imports according to PEP 8."""
        # Group imports by type
        groups = {
            ImportType.STANDARD_LIBRARY: [],
            ImportType.THIRD_PARTY: [],
            ImportType.LOCAL: [],
            ImportType.RELATIVE: [],
        }

        for import_stmt in imports:
            groups[import_stmt.import_type].append(import_stmt)

        # Sort each group
        for import_type in groups:
            groups[import_type].sort(key=lambda x: (x.module, x.names))

        # Build organized import string
        organized_sections = []

        for import_type in [
            ImportType.STANDARD_LIBRARY,
            ImportType.THIRD_PARTY,
            ImportType.LOCAL,
            ImportType.RELATIVE,
        ]:
            if groups[import_type]:
                section_imports = []
                for import_stmt in groups[import_type]:
                    section_imports.append(str(import_stmt))

                organized_sections.append("\n".join(section_imports))

        return "\n\n".join(organized_sections) + "\n\n" if organized_sections else ""

    def organize_file_imports(self, file_path: Path) -> str:
        """Organize imports in a file and return the organized content."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        # Extract imports and non-import content
        imports = self.parse_imports(content)
        organized_imports = self.organize_imports(imports)

        # Remove existing imports from content
        content_without_imports = self._remove_imports_from_content(content)

        # Combine organized imports with remaining content
        if organized_imports and content_without_imports:
            return organized_imports + content_without_imports
        elif organized_imports:
            return organized_imports
        else:
            return content_without_imports

    def _remove_imports_from_content(self, content: str) -> str:
        """Remove import statements from content."""
        lines = content.split("\n")
        non_import_lines = []
        in_multiline_import = False
        skip_next_empty_lines = False

        for line in lines:
            stripped = line.strip()

            # Skip shebang and encoding declarations
            if stripped.startswith("#!") or stripped.startswith("# -*- ") or stripped.startswith("# coding:"):
                non_import_lines.append(line)
                continue

            # Handle multiline imports
            if in_multiline_import:
                if ")" in line:
                    in_multiline_import = False
                    skip_next_empty_lines = True
                continue

            # Skip import statements
            if stripped.startswith("import ") or stripped.startswith("from ") or (stripped and stripped.endswith("import (")):
                if stripped.endswith("import ("):
                    in_multiline_import = True
                skip_next_empty_lines = True
                continue

            # Skip empty lines immediately after imports
            if skip_next_empty_lines and not stripped:
                continue

            # Once we hit non-empty, non-import content, stop skipping
            if stripped:
                skip_next_empty_lines = False

            non_import_lines.append(line)

        return "\n".join(non_import_lines)

    def check_import_violations(self, imports: List[ImportStatement]) -> List[str]:
        """Check for PEP 8 import violations."""
        violations = []

        # Check for wildcard imports
        for import_stmt in imports:
            if import_stmt.is_from_import and "*" in import_stmt.names:
                violations.append(f"Line {import_stmt.line_number}: Wildcard import from {import_stmt.module}")

        # Check import order
        current_type = None
        for import_stmt in imports:
            if current_type is not None:
                if import_stmt.import_type.value < current_type.value:
                    violations.append(
                        f"Line {import_stmt.line_number}: Import order violation - {import_stmt.import_type.value} import after {current_type.value}"
                    )
            current_type = import_stmt.import_type

        return violations

    def generate_import_report(self, file_path: Path) -> Dict[str, any]:
        """Generate comprehensive import report for a file."""
        content = file_path.read_text(encoding="utf-8")
        imports = self.parse_imports(content)
        violations = self.check_import_violations(imports)

        # Count imports by type
        import_counts = {import_type.value: 0 for import_type in ImportType}
        for import_stmt in imports:
            import_counts[import_stmt.import_type.value] += 1

        return {
            "file_path": str(file_path),
            "total_imports": len(imports),
            "import_counts": import_counts,
            "violations": violations,
            "imports": [
                {
                    "module": imp.module,
                    "names": imp.names,
                    "type": imp.import_type.value,
                    "line_number": imp.line_number,
                    "is_from_import": imp.is_from_import,
                }
                for imp in imports
            ],
        }


def organize_project_imports(project_root: Path, dry_run: bool = True) -> Dict[str, any]:
    """Organize imports for all Python files in a project."""
    organizer = ImportOrganizer(project_root)
    results = {"processed_files": [], "violations": [], "errors": []}

    # Find all Python files
    python_files = list(project_root.rglob("*.py"))

    for file_path in python_files:
        try:
            report = organizer.generate_import_report(file_path)
            results["processed_files"].append(report)
            results["violations"].extend(report["violations"])

            if not dry_run and report["violations"]:
                # Organize imports and write back
                organized_content = organizer.organize_file_imports(file_path)
                file_path.write_text(organized_content, encoding="utf-8")

        except Exception as e:
            results["errors"].append({"file_path": str(file_path), "error": str(e)})

    return results
