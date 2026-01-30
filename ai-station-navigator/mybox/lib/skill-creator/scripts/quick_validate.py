#!/usr/bin/env python3
"""
Quick validation script for skills - minimal version

Source: https://github.com/anthropics/skills/tree/main/skills/skill-creator
License: Apache 2.0
Integrated by: AIOS (领航员) Project
Modified: Removed yaml dependency for better portability
"""

import sys
import re
from pathlib import Path


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter without yaml library

    Returns:
        (frontmatter_dict, error_message)
    """
    if not content.startswith('---'):
        return {}, "No YAML frontmatter found"

    # Extract frontmatter between --- markers
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}, "Invalid frontmatter format"

    frontmatter_text = match.group(1)

    # Simple YAML parser for our specific use case
    frontmatter = {}
    for line in frontmatter_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            frontmatter[key] = value

    return frontmatter, ""


def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path)

    # Check SKILL.md exists
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "SKILL.md not found"

    # Read and validate frontmatter
    try:
        content = skill_md.read_text(encoding='utf-8')
    except Exception as e:
        return False, f"Error reading SKILL.md: {e}"

    # Parse frontmatter
    frontmatter, error = parse_frontmatter(content)
    if error:
        return False, error

    if not isinstance(frontmatter, dict):
        return False, "Frontmatter must be a YAML dictionary"

    # Define allowed properties
    ALLOWED_PROPERTIES = {'name', 'description', 'license', 'allowed-tools', 'metadata'}

    # Check for unexpected properties (excluding nested keys under metadata)
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected_keys))}. "
            f"Allowed properties are: {', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    # Check required fields
    if 'name' not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if 'description' not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    # Extract name for validation
    name = frontmatter.get('name', '')
    name = name.strip()
    if name:
        # Check naming convention (hyphen-case: lowercase with hyphens)
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, f"Name '{name}' should be hyphen-case (lowercase letters, digits, and hyphens only)"
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
        # Check name length (max 64 characters per spec)
        if len(name) > 64:
            return False, f"Name is too long ({len(name)} characters). Maximum is 64 characters."

    # Extract and validate description
    description = frontmatter.get('description', '')
    description = description.strip()
    if description:
        # Check for angle brackets
        if '<' in description or '>' in description:
            return False, "Description cannot contain angle brackets (< or >)"
        # Check description length (max 1024 characters per spec)
        if len(description) > 1024:
            return False, f"Description is too long ({len(description)} characters). Maximum is 1024 characters."

    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill-path>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
