#!/usr/bin/env python3
"""
CSV to JSON Converter

This script converts CSV files to JSON format with support for both
simple CSV files and those with headers.

Usage:
    python csv_to_json.py <input_csv_file> [output_json_file]
    python csv_to_json.py --help

Arguments:
    input_csv_file      Path to the input CSV file
    output_json_file    Optional path to save JSON output (prints to stdout if not provided)

Options:
    --help              Show this help message and exit

Examples:
    # Convert CSV and print to stdout
    python csv_to_json.py data.csv

    # Convert CSV and save to file
    python csv_to_json.py data.csv output.json

    # Show help
    python csv_to_json.py --help

The script automatically detects whether the CSV file has headers and processes
it accordingly. Output is formatted as a JSON array of objects (with headers)
or arrays (without headers).
"""

import csv
import json
import sys
import os
from typing import List, Dict, Any, Union


def show_help() -> None:
    """Display help information and exit."""
    print(__doc__)
    sys.exit(0)


def detect_has_headers(csv_file_path: str) -> bool:
    """
    Attempt to detect if the CSV file has headers.

    Args:
        csv_file_path: Path to the CSV file

    Returns:
        True if headers are detected, False otherwise
    """
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            sniffer = csv.Sniffer()
            # Read a sample to detect headers
            sample = f.read(2048)
            return sniffer.has_header(sample)
    except csv.Error:
        # If detection fails, assume no headers
        return False


def csv_to_json(csv_file_path: str) -> List[Union[Dict[str, Any], List[Any]]]:
    """
    Convert CSV file to JSON-compatible Python data structure.

    Args:
        csv_file_path: Path to the input CSV file

    Returns:
        List of dictionaries (if headers present) or list of lists (if no headers)

    Raises:
        FileNotFoundError: If the CSV file doesn't exist
        PermissionError: If the file cannot be read due to permissions
        ValueError: If the CSV format is invalid
    """
    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

    if not os.path.isfile(csv_file_path):
        raise ValueError(f"Path is not a file: {csv_file_path}")

    has_headers = detect_has_headers(csv_file_path)
    data = []

    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
            if has_headers:
                # Use DictReader for CSV with headers
                reader = csv.DictReader(csv_file)
                for row in reader:
                    # Convert OrderedDict to regular dict
                    data.append(dict(row))
            else:
                # Use regular reader for CSV without headers
                reader = csv.reader(csv_file)
                for row in reader:
                    data.append(row)

        if not data:
            print("Warning: CSV file is empty", file=sys.stderr)

    except PermissionError as e:
        raise PermissionError(f"Permission denied reading file: {csv_file_path}") from e
    except csv.Error as e:
        raise ValueError(f"Invalid CSV format in file {csv_file_path}: {e}") from e
    except UnicodeDecodeError as e:
        raise ValueError(f"Unable to decode file {csv_file_path}. Ensure it's a valid text file.") from e

    return data


def save_json(data: List[Union[Dict[str, Any], List[Any]]], output_file_path: str) -> None:
    """
    Save JSON data to a file.

    Args:
        data: The data to save
        output_file_path: Path to the output JSON file

    Raises:
        PermissionError: If the file cannot be written due to permissions
        OSError: If there's an error creating/writing the file
    """
    try:
        with open(output_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, indent=2, ensure_ascii=False)
    except PermissionError as e:
        raise PermissionError(f"Permission denied writing to file: {output_file_path}") from e
    except OSError as e:
        raise OSError(f"Error writing to file {output_file_path}: {e}") from e


def main() -> int:
    """
    Main entry point for the script.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse command-line arguments
    args = sys.argv[1:]

    # Check for help flag
    if '--help' in args or '-h' in args or len(args) == 0:
        show_help()

    # Validate argument count
    if len(args) < 1 or len(args) > 2:
        print("Error: Invalid number of arguments", file=sys.stderr)
        print("\nUsage: python csv_to_json.py <input_csv_file> [output_json_file]", file=sys.stderr)
        print("Use --help for more information", file=sys.stderr)
        return 1

    input_file = args[0]
    output_file = args[1] if len(args) == 2 else None

    try:
        # Convert CSV to JSON
        json_data = csv_to_json(input_file)

        if output_file:
            # Save to file
            save_json(json_data, output_file)
            print(f"Successfully converted '{input_file}' to '{output_file}'")
            print(f"Total records: {len(json_data)}")
        else:
            # Print to stdout
            print(json.dumps(json_data, indent=2, ensure_ascii=False))

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except PermissionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
