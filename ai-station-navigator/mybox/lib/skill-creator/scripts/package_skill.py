#!/usr/bin/env python3
"""
Skill Packager - Creates a distributable .skill file of a skill folder

Source: https://github.com/anthropics/skills/tree/main/skills/skill-creator
License: Apache 2.0
Integrated by: AIOS (领航员) Project

Usage:
    package_skill.py <skill-path> [output-directory]
Example:
    package_skill.py ../../skills/custom/my-skill
    package_skill.py ../../skills/custom/my-skill ./dist
"""

import sys
import zipfile
from pathlib import Path

# Import quick_validate
try:
    from quick_validate import validate_skill
except ImportError:
    # Fallback if running standalone
    def validate_skill(skill_path):
        skill_path = Path(skill_path)
        skill_md = skill_path / 'SKILL.md'
        if not skill_md.exists():
            return False, "SKILL.md not found"
        return True, "Basic validation passed"


def package_skill(skill_path, output_dir=None):
    """
    Package a skill folder into a .skill file.

    Args:
        skill_path: Path to the skill folder
        output_dir: Optional output directory for the .skill file (defaults to current directory)

    Returns:
        Path to the created .skill file, or None if error
    """
    skill_path = Path(skill_path).resolve()

    # Validate skill folder exists
    if not skill_path.exists():
        print(f"[X] Error: Skill folder not found: {skill_path}")
        return None
    if not skill_path.is_dir():
        print(f"[X] Error: Path is not a directory: {skill_path}")
        return None

    # Validate SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"[X] Error: SKILL.md not found in {skill_path}")
        return None

    # Run validation before packaging
    print("[VALIDATE] Checking skill...")
    valid, message = validate_skill(skill_path)
    if not valid:
        print(f"[X] Validation failed: {message}")
        print(" Please fix the validation errors before packaging.")
        return None
    print(f"[OK] {message}\n")

    # Determine output location
    skill_name = skill_path.name
    if output_dir:
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path.cwd()
    skill_filename = output_path / f"{skill_name}.skill"

    # Create the .skill file (zip format)
    try:
        with zipfile.ZipFile(skill_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk through the skill directory
            for file_path in skill_path.rglob('*'):
                if file_path.is_file():
                    # Calculate the relative path within the zip
                    arcname = file_path.relative_to(skill_path.parent)
                    zipf.write(file_path, arcname)
                    print(f" Added: {arcname}")
        print(f"\n[OK] Successfully packaged skill to: {skill_filename}")
        return skill_filename
    except Exception as e:
        print(f"[X] Error creating .skill file: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: package_skill.py <skill-path> [output-directory]")
        print("\nExample:")
        print(" package_skill.py ../../skills/custom/my-skill")
        print(" package_skill.py ../../skills/custom/my-skill ./dist")
        sys.exit(1)

    skill_path_str = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"[PACKAGE] Creating skill archive: {Path(skill_path_str).name}")
    if output_dir:
        print(f" Output directory: {output_dir}")
    print()

    result = package_skill(skill_path_str, output_dir)
    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
