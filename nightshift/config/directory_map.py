"""
Directory Map Generator for NightShift

This module generates and manages a directory structure map,
providing nightshift with knowledge of available directories and their purposes.

Users should customize this module to match their own file organization system.
The default configuration provides an example structure that can be adapted.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class DirectoryInfo:
    """Information about a directory in the map."""
    path: str
    number: str
    name: str
    description: str
    level: int
    children: List['DirectoryInfo'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


class DirectoryMap:
    """
    Manages a directory structure and provides path resolution for NightShift.

    This class serves a similar purpose to claude-code-tools-reference.md but for
    directory navigation instead of tool discovery.

    CUSTOMIZE THIS CLASS:
    - Set BASE_ROOT to your main directory
    - Update CATEGORIES to match your directory organization
    - Modify COMMON_PATTERNS for your naming conventions
    """

    # Base path - CUSTOMIZE THIS to your directory root
    BASE_ROOT = str(Path.home())  # Default to home directory

    # Category descriptions - CUSTOMIZE THIS for your directory structure
    # Example structure shown below (adapt to your needs):
    CATEGORIES = {
        # Example: Numbered organizational system
        # "00-09 System": "System-wide organization",
        # "10-19 Personal": "Personal files",
        # "20-29 Work": "Work-related files",
    }

    # Common subdirectory patterns - CUSTOMIZE THIS for your naming system
    # Example patterns shown below (adapt to your needs):
    COMMON_PATTERNS = {
        # Example: Numbered sub-categories
        # ".01": "Inbox",
        # ".02": "Ongoing",
        # ".09": "Archive",
    }

    def __init__(self, root_path: Optional[str] = None):
        """
        Initialize the directory map.

        Args:
            root_path: Override the default BASE_ROOT path
        """
        self.root_path = Path(root_path) if root_path else Path(self.BASE_ROOT)
        self._directory_tree: Optional[Dict] = None

    def scan_directories(self, max_depth: int = 3) -> Dict[str, DirectoryInfo]:
        """
        Scan the directory structure.

        Args:
            max_depth: Maximum depth to scan (default: 3 levels)

        Returns:
            Dictionary mapping directory paths to DirectoryInfo objects
        """
        directories = {}

        for root, dirs, _ in os.walk(self.root_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            rel_path = os.path.relpath(root, self.root_path)
            depth = rel_path.count(os.sep)

            if depth >= max_depth:
                dirs[:] = []  # Don't recurse further
                continue

            # Parse directory name
            dir_name = os.path.basename(root)
            number, name = self._parse_directory_name(dir_name)

            dir_info = DirectoryInfo(
                path=root,
                number=number,
                name=name,
                description=self._get_description(rel_path, number, name),
                level=depth
            )

            directories[rel_path] = dir_info

        return directories

    def _parse_directory_name(self, dir_name: str) -> tuple[str, str]:
        """
        Parse a directory name into number and name components.

        Args:
            dir_name: Directory name like "40 Software" or "40.14 GW Scattering Spectra"

        Returns:
            Tuple of (number, name)
        """
        parts = dir_name.split(' ', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", dir_name

    def _get_description(self, rel_path: str, number: str, name: str) -> str:
        """
        Get a description for a directory based on its location and name.

        Args:
            rel_path: Relative path from JimDex root
            number: Directory number (e.g., "40.14")
            name: Directory name

        Returns:
            Description string
        """
        # Check if it's a top-level category
        if rel_path in self.CATEGORIES:
            return self.CATEGORIES[rel_path]

        # Check for common patterns
        for pattern, desc in self.COMMON_PATTERNS.items():
            if number.endswith(pattern):
                return desc

        # Default description based on name
        return name

    def get_path(self, search_term: str) -> Optional[str]:
        """
        Find a directory path by searching for a term.

        Args:
            search_term: Search term (can be number, name, or part of path)

        Returns:
            Full path to the directory, or None if not found
        """
        directories = self.scan_directories()

        # Try exact number match first
        for rel_path, info in directories.items():
            if info.number == search_term:
                return info.path

        # Try name match
        search_lower = search_term.lower()
        for rel_path, info in directories.items():
            if search_lower in info.name.lower():
                return info.path

        return None

    def generate_markdown_map(self, output_path: Optional[str] = None) -> str:
        """
        Generate a markdown document describing the directory structure.

        Similar to claude-code-tools-reference.md but for directories.

        Args:
            output_path: Optional path to write the markdown file

        Returns:
            Markdown string
        """
        directories = self.scan_directories()

        # Build markdown
        lines = [
            "# Directory Map",
            "",
            "A comprehensive reference of the directory structure for nightshift navigation.",
            "",
            f"**Root Path:** `{self.root_path}`",
            "",
            "**IMPORTANT NOTE:** This directory map is specific to your file organization system.",
            "Customize directory_map.py to match your structure.",
            "",
            "## Directory Structure",
            "",
        ]

        # Group by top-level categories
        current_category = None
        for rel_path in sorted(directories.keys()):
            if rel_path == '.':
                continue

            info = directories[rel_path]

            # Determine category
            category = rel_path.split(os.sep)[0] if os.sep in rel_path else rel_path

            # Add category header
            if category != current_category and category in self.CATEGORIES:
                current_category = category
                lines.append(f"### {category}")
                lines.append(f"*{self.CATEGORIES[category]}*")
                lines.append("")

            # Add directory entry with proper indentation
            indent = "  " * (info.level - 1) if info.level > 0 else ""
            if info.number:
                lines.append(f"{indent}- **{info.number} {info.name}** - {info.description}")
            else:
                lines.append(f"{indent}- **{info.name}** - {info.description}")

        lines.extend([
            "",
            "## Usage in Nightshift",
            "",
            "This directory map can be used by nightshift to:",
            "- Resolve directory paths by number or name",
            "- Understand the organization structure",
            "- Find appropriate locations for new files",
            "- Navigate the file system efficiently",
            "",
            "## Common Patterns",
            "",
        ])

        for pattern, desc in self.COMMON_PATTERNS.items():
            lines.append(f"- **{pattern}**: {desc}")

        lines.extend([
            "",
            "---",
            "",
            f"*Generated: {Path(__file__).name}*",
            ""
        ])

        markdown = "\n".join(lines)

        # Write to file if requested
        if output_path:
            Path(output_path).write_text(markdown)

        return markdown

    def get_category_paths(self, category: str) -> List[str]:
        """
        Get all paths within a specific category.

        Args:
            category: Category name (e.g., "40-49 Research Projects")

        Returns:
            List of full paths
        """
        directories = self.scan_directories()
        return [
            info.path
            for rel_path, info in directories.items()
            if rel_path.startswith(category)
        ]

    def find_project_directories(self, project_name: str) -> List[str]:
        """
        Find all directories related to a specific project.

        For example, finding all directories for "nightshift" would return:
        - 40 Software/40.47 nightshift
        - 41 Notes/41.47 nightshift
        - 42 Papers/42.47 nightshift
        - etc.

        Args:
            project_name: Name of the project to search for

        Returns:
            List of full paths to project directories
        """
        directories = self.scan_directories()
        project_lower = project_name.lower()

        matches = [
            info.path
            for info in directories.values()
            if project_lower in info.name.lower()
        ]

        return sorted(matches)


def main():
    """Generate and save the directory map markdown file."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate directory map for nightshift"
    )
    parser.add_argument(
        "--output",
        default="directory-map.md",
        help="Output markdown file path"
    )
    parser.add_argument(
        "--root",
        help="Override BASE_ROOT path (default: home directory)"
    )

    args = parser.parse_args()

    mapper = DirectoryMap(root_path=args.root)
    markdown = mapper.generate_markdown_map(output_path=args.output)

    print(f"Directory map generated: {args.output}")
    print(f"Total lines: {len(markdown.splitlines())}")


if __name__ == "__main__":
    main()
