class EscapeException(Exception):
    pass

def read_str(filepath : str) -> str:
    """
    Reads the content of a file and returns it as a string.
    
    Args:
        filepath: The path to the file.
        
    Returns:
        The content of the file as a string.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        raise EscapeException(f"File not found: {filepath}")
    except Exception as e:
        raise EscapeException(f"An error occurred while reading the file: {e}")
