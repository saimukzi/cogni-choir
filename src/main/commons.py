"""Common utility functions and custom exceptions for the application.

This module provides helper functions that are used across various
parts of the application, such as file reading utilities. It also
defines custom exceptions like `EscapeException` for specific error
handling scenarios.
"""

class EscapeException(Exception):
    """Custom exception for specific error handling scenarios.

    This exception can be used to signal errors that should be handled
    in a particular way by higher-level parts of the application,
    potentially indicating a need to escape a certain process or operation.
    """
    pass

def read_str(filepath : str) -> str:
    """Reads the content of a file and returns it as a string.

    Args:
        filepath: str. The path to the file.
        
    Returns:
        str: The content of the file as a string.
        
    Raises:
        EscapeException: If the file is not found or an error occurs during reading.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        raise EscapeException(f"File not found: {filepath}")
    except Exception as e:
        raise EscapeException(f"An error occurred while reading the file: {e}")
