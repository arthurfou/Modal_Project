"""Small shared helpers."""
import os

CLEAR_LINE = " " * 100


def log(module_file, message, end="\n"):
    """Print a message prefixed with the name of the calling module."""
    print(f"[{os.path.basename(module_file)}] {message}", end=end)


def int_response(question):
    """Ask the user a question until they answer with a valid integer, and return it."""
    while True:
        answer = input(question)
        try:
            return int(answer)
        except ValueError:
            print("Not a valid integer, try again.")
