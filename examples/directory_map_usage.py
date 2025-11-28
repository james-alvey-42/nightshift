"""
Example usage of DirectoryMap in nightshift tasks.

This demonstrates how nightshift can use the directory map to:
1. Find project directories
2. Resolve paths by number or name
3. Navigate your directory structure

NOTE: Customize directory_map.py first to match your file organization.
"""

from nightshift.config.directory_map import DirectoryMap


def example_find_project_workspace():
    """
    Example: Find all directories related to a project.

    This is useful when nightshift needs to work across multiple
    aspects of a project.
    """
    mapper = DirectoryMap()

    # Find all directories matching a project name
    project_name = "my-project"
    directories = mapper.find_project_directories(project_name)

    print(f"Found {len(directories)} directories for '{project_name}':")
    for path in directories:
        print(f"  - {path}")


def example_resolve_path_by_number():
    """
    Example: Resolve a directory path using a number (if using numbered system).
    """
    mapper = DirectoryMap()

    # Example: User might say "Save this in 40.47" if using numbered directories
    number = "40.47"
    path = mapper.get_path(number)

    if path:
        print(f"Directory {number} resolved to: {path}")
    else:
        print(f"Directory {number} not found")


def example_resolve_path_by_name():
    """
    Example: Resolve a directory path by searching for a name.
    """
    mapper = DirectoryMap()

    name = "Projects"
    path = mapper.get_path(name)

    if path:
        print(f"Directory '{name}' resolved to: {path}")
    else:
        print(f"Directory '{name}' not found")


def example_get_category_contents():
    """
    Example: Get all directories within a category.
    """
    mapper = DirectoryMap()

    # If you have categorized directories
    category = "Work"
    paths = mapper.get_category_paths(category)

    print(f"\nFound {len(paths)} directories in '{category}'")


if __name__ == "__main__":
    print("=" * 60)
    print("Directory Map Usage Examples")
    print("=" * 60)
    print("\nNOTE: Customize directory_map.py first!")
    print("=" * 60)

    print("\n1. Find project workspace")
    print("-" * 60)
    example_find_project_workspace()

    print("\n2. Resolve path by number")
    print("-" * 60)
    example_resolve_path_by_number()

    print("\n3. Resolve path by name")
    print("-" * 60)
    example_resolve_path_by_name()

    print("\n4. Get category contents")
    print("-" * 60)
    example_get_category_contents()
