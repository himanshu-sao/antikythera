import ast
import builtins
import types
import sys
from typing import Any, Dict, List, Set, Optional

class SafeExecutorError(Exception):
    """Base exception for SafeExecutor."""
    pass

class SecurityError(SafeExecutorError):
    """Raised when a dangerous operation is attempted."""
    pass

class DependencyRequiredError(SafeExecutorError):
    """Raised when an import is not in the whitelist."""
    def __init__(self, module_name: str):
        self.module_name = module_name
        super().__init__(f"Required dependency not installed: {module_name}")

class SafeExecutor:
    """
    A safe executor for running untrusted Python code.
    - Uses AST to statically analyze imports.
    - Whitelists safe modules.
    - Blocks dangerous modules and built-in functions.
    - Executes in a restricted environment with a safe __import__ in builtins.
    """

    # Whitelist of allowed top-level modules.
    # These are considered safe and do not require explicit installation approval.
    WHITELIST: Set[str] = {
        'json', 're', 'httpx', 'datetime', 'yaml', 'typing', 'collections',
        'math', 'random', 'string', 'time', 'csv', 'decimal', 'fractions',
        'statistics', 'itertools', 'functools', 'hashlib', 'base64', 'uuid',
        'ipaddress', 'textwrap', 'difflib', 'pprint', 'copy', 'pprint',
        'enum', 'dataclasses', 'contextlib', 'queue', 'heapq', 'bisect',
        'array', 'weakref', 'types', 'operator', 'keyword', 'tokenize',
    }

    # Blocklist of modules that are never allowed due to security risks.
    BLOCKLIST: Set[str] = {
        'os', 'sys', 'subprocess', 'shutil', 'multiprocessing', 'threading',
        'socket', 'urllib', 'requests', 'http.client', 'ftplib', 'telnetlib',
        'imaplib', 'poplib', 'nnTPLib', 'smtplib', 'ssl', 'signal', 'resource',
        'pickle', 'marshal', 'shelve', 'dbm', 'sqlite3',  # Removed csv as it's in whitelist
        'ctypes', 'apelinker', 'imp', 'importlib', 'pkgutil', 'modulefinder',
        'runpy', 'site', 'user', 'builtins', '__main__', 'warnings',
    }

    # Dangerous built-in functions to remove from the execution environment.
    DANGEROUS_BUILTINS: Set[str] = {
        'eval', 'exec', 'compile', 'open', 'input', 'help', 'exit', 'quit',
        'copyright', 'credits', 'license', '__import__',  # We provide our own safe __import__
    }

    @classmethod
    def extract_imports(cls, code_string: str) -> Set[str]:
        """
        Extract all top-level module names imported in the code string.
        Returns a set of module names (as strings).
        """
        try:
            tree = ast.parse(code_string)
        except SyntaxError as e:
            raise SafeExecutorError(f"Invalid Python syntax: {e}") from e

        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Import the top-level module (e.g., 'import pandas' -> 'pandas')
                    # For 'import pandas as pd', we still get 'pandas'
                    module = alias.name.split('.')[0]
                    imports.add(module)
            elif isinstance(node, ast.ImportFrom):
                # From ... import ... : e.g., 'from pandas import DataFrame'
                # The module is node.module (could be None for relative imports)
                if node.module:
                    # Get the top-level module (e.g., 'from pandas.core import ...' -> 'pandas')
                    module = node.module.split('.')[0]
                    imports.add(module)
                # Note: We ignore relative imports (from . import ...) as they are local.
        return imports

    @classmethod
    def _check_imports(cls, imports: Set[str]) -> Optional[str]:
        """
        Check a set of imports against the whitelist and blocklist.
        Returns the first problematic module name (for blocklist or not in whitelist) or None if all are safe.
        """
        for module in imports:
            if module in cls.BLOCKLIST:
                return module  # Blocked due to security
            if module not in cls.WHITELIST:
                return module  # Not in whitelist, requires approval
        return None  # All imports are allowed

    @classmethod
    def _safe_import(cls, name: str, globals=None, locals=None, fromlist=(), level=0):
        """
        A safe replacement for the built-in __import__ function.
        Only allows importing modules that are in the whitelist.
        """
        # Determine the top-level module name.
        # For 'import pandas', name is 'pandas'.
        # For 'from pandas.core import ...', name is 'pandas.core'.
        # We want to check the top-level part.
        top_level_name = name.split('.')[0]

        # Check if the top-level module is allowed.
        if top_level_name in cls.BLOCKLIST:
            raise SecurityError(f"Blocked import due to security policy: {top_level_name}")
        if top_level_name not in cls.WHITELIST:
            raise DependencyRequiredError(top_level_name)

        # If allowed, use the real __import__.
        return __import__(name, globals, locals, fromlist, level)

    @classmethod
    def _create_safe_environment(cls) -> Dict[str, Any]:
        """
        Create a restricted globals dictionary for code execution.
        Includes a safe __import__ function in the builtins and pre-imported whitelisted modules.
        """
        # Start with a copy of safe builtins (without dangerous ones).
        safe_builtins = {
            name: getattr(builtins, name)
            for name in dir(builtins)
            if name not in cls.DANGEROUS_BUILTINS
        }

        # Add our safe __import__ to the builtins, overriding the existing one.
        safe_builtins['__import__'] = lambda name, globals=None, locals=None, fromlist=(), level=0: cls._safe_import(name, globals, locals, fromlist, level)

        # Pre-import all whitelisted modules and add them to globals.
        # This ensures that if a module is imported, it's already available and fast.
        safe_globals = {'__builtins__': safe_builtins}
        for module in cls.WHITELIST:
            try:
                safe_globals[module] = __import__(module)
            except ImportError:
                # If a whitelisted module is not available, we skip it.
                # In a real system, we would ensure the venv has these.
                pass

        return safe_globals

    @classmethod
    def execute(cls, code_string: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute the given Python code string in a safe environment.
        Args:
            code_string: The Python code to execute.
            context: A dictionary of variables to make available in the code's namespace.
        Returns:
            The result of the last expression in the code, or None if no result.
        Raises:
            SafeExecutorError: If the code is unsafe or has an error.
        """
        if context is None:
            context = {}

        # Step 1: Extract imports.
        imports = cls.extract_imports(code_string)

        # Step 2: Check for blocked or missing dependencies.
        problematic_module = cls._check_imports(imports)
        if problematic_module:
            if problematic_module in cls.BLOCKLIST:
                raise SecurityError(f"Blocked import due to security policy: {problematic_module}")
            else:
                raise DependencyRequiredError(problematic_module)

        # Step 3: Create the safe execution environment.
        safe_globals = cls._create_safe_environment()
        # Update with the context (variables passed in).
        safe_globals.update(context)

        # Step 4: Execute the code.
        try:
            # We compile the code to detect syntax errors early.
            compiled_code = compile(code_string, '<string>', 'exec')
            # We execute and capture the result.
            # Note: In a more advanced system, we might want to capture stdout/stderr.
            exec(compiled_code, safe_globals)
            # If the code assigns to a variable named 'result', we return it.
            # Otherwise, we return None. Alternatively, we could return the last expression?
            # For simplicity, we return the value of 'result' if it exists, else None.
            return safe_globals.get('result', None)
        except Exception as e:
            # Re-raise the exception with context.
            raise SafeExecutorError(f"Error during execution: {e}") from e

# Example usage (for testing):
if __name__ == "__main__":
    # This is a simple test.
    code = """
import json
import re
data = {"test": 123}
result = json.dumps(data)
    """
    try:
        output = SafeExecutor.execute(code)
        print(f"Execution successful: {output}")
    except SafeExecutorError as e:
        print(f"Execution failed: {e}")