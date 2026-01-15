#!/usr/bin/env python3
"""
Convert Graphviz DOT files to Lucid Chart compatible XML format.

Usage:
    python convert_to_lucid.py <input.dot> [output.xml]

If output is not specified, creates <input>.xml in the same directory.

Requirements:
    pip install graphviz2drawio
"""

import sys
import subprocess
from pathlib import Path


def check_dependencies():
    """Check if graphviz2drawio is installed."""
    try:
        result = subprocess.run(
            ["graphviz2drawio", "--version"],
            capture_output=True,
            text=True
        )
        return True
    except FileNotFoundError:
        return False


def install_graphviz2drawio():
    """Attempt to install graphviz2drawio."""
    print("Installing graphviz2drawio...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "graphviz2drawio"],
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def convert_dot_to_xml(input_path: str, output_path: str = None) -> str:
    """
    Convert a DOT file to Lucid Chart compatible XML.

    Args:
        input_path: Path to the .dot file
        output_path: Optional path for output .xml file

    Returns:
        Path to the generated XML file
    """
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if not input_file.suffix.lower() in [".dot", ".gv"]:
        raise ValueError(f"Expected .dot or .gv file, got: {input_file.suffix}")

    # Determine output path
    if output_path:
        output_file = Path(output_path)
    else:
        output_file = input_file.with_suffix(".xml")

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Run graphviz2drawio
    cmd = ["graphviz2drawio", str(input_file), "-o", str(output_file)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Successfully converted: {input_file} -> {output_file}")
        return str(output_file)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Conversion failed: {e.stderr}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    # Check dependencies
    if not check_dependencies():
        print("graphviz2drawio not found.")
        if not install_graphviz2drawio():
            print("Failed to install graphviz2drawio.")
            print("Please install manually: pip install graphviz2drawio")
            sys.exit(1)

    try:
        result = convert_dot_to_xml(input_path, output_path)
        print(f"\nOutput file: {result}")
        print("\nTo import into Lucid Chart:")
        print("  1. Open Lucid Chart")
        print("  2. Go to File > Import")
        print("  3. Select the generated .xml file")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
