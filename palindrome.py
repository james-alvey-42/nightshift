"""
Palindrome checker module.

This module provides functionality to check if a string is a palindrome,
ignoring case, spaces, and punctuation.
"""

import re


def is_palindrome(text):
    """
    Check if a string is a palindrome.

    A palindrome is a word, phrase, number, or other sequence of characters
    that reads the same forward and backward. This function ignores case,
    spaces, and punctuation when checking.

    Args:
        text (str): The string to check for palindrome property.

    Returns:
        bool: True if the string is a palindrome, False otherwise.

    Examples:
        >>> is_palindrome("racecar")
        True
        >>> is_palindrome("hello")
        False
        >>> is_palindrome("A man a plan a canal Panama")
        True
        >>> is_palindrome("Was it a rat I saw?")
        True
    """
    # Remove all non-alphanumeric characters and convert to lowercase
    cleaned_text = re.sub(r'[^a-zA-Z0-9]', '', text).lower()

    # Check if the cleaned text is equal to its reverse
    return cleaned_text == cleaned_text[::-1]


if __name__ == '__main__':
    # Test cases
    test_cases = [
        ("racecar", True),
        ("Racecar", True),
        ("hello", False),
        ("A man a plan a canal Panama", True),
        ("Was it a rat I saw?", True),
        ("Never odd or even", True),
        ("Python", False),
        ("Madam", True),
        ("", True),  # Empty string is considered a palindrome
        ("a", True),  # Single character is a palindrome
    ]

    print("Palindrome Checker Test Results:")
    print("=" * 50)

    all_passed = True
    for text, expected in test_cases:
        result = is_palindrome(text)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        print(f"{status}: is_palindrome('{text}') = {result} (expected {expected})")
        if result != expected:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("All tests passed! ✓")
    else:
        print("Some tests failed! ✗")
