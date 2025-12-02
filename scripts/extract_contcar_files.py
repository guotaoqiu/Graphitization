#!/usr/bin/env python3
"""
Script to extract all CONTCAR files from 02_calculations directory
while preserving the folder structure.

Usage:
    python3 extract_contcar_files.py [--output-dir DIR] [--dry-run]

Options:
    --output-dir DIR    Output directory for extracted CONTCAR files (default: ../extracted_contcars)
    --dry-run          Show what would be extracted without actually copying files
"""

import os
import shutil
import argparse
from pathlib import Path


class CONTCARExtractor:
    """Extract CONTCAR files while preserving directory structure"""

    def __init__(self, calc_dir, output_dir, dry_run=False):
        """
        Initialize the CONTCAR extractor

        Args:
            calc_dir: Source directory containing calculations (02_calculations)
            output_dir: Destination directory for extracted CONTCAR files
            dry_run: If True, only show what would be extracted without copying
        """
        self.calc_dir = Path(calc_dir)
        self.output_dir = Path(output_dir)
        self.dry_run = dry_run
        self.contcar_files = []

    def find_all_contcar_files(self):
        """Find all CONTCAR files in the calculation directory"""
        print("="*70)
        print("Searching for CONTCAR files...")
        print("="*70)
        print()

        # Recursively find all CONTCAR files
        for contcar_path in self.calc_dir.rglob('CONTCAR'):
            # Get relative path from calc_dir
            rel_path = contcar_path.relative_to(self.calc_dir)
            self.contcar_files.append((contcar_path, rel_path))
            print(f"Found: {rel_path}")

        print()
        print(f"Total CONTCAR files found: {len(self.contcar_files)}")
        print()

        return self.contcar_files

    def extract_contcar_files(self):
        """Extract CONTCAR files to output directory while preserving structure"""
        if not self.contcar_files:
            print("No CONTCAR files to extract. Run find_all_contcar_files() first.")
            return

        print("="*70)
        if self.dry_run:
            print("DRY RUN: Showing what would be extracted")
        else:
            print("Extracting CONTCAR files...")
        print("="*70)
        print()

        extracted_count = 0
        failed_count = 0

        for source_path, rel_path in self.contcar_files:
            # Create destination path
            dest_path = self.output_dir / rel_path

            try:
                if self.dry_run:
                    print(f"Would extract: {rel_path}")
                    print(f"  → {dest_path}")
                else:
                    # Create parent directories if they don't exist
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    # Copy the file
                    shutil.copy2(source_path, dest_path)
                    print(f"✓ Extracted: {rel_path}")

                extracted_count += 1

            except Exception as e:
                print(f"✗ Failed to extract {rel_path}: {e}")
                failed_count += 1

            print()

        print("="*70)
        if self.dry_run:
            print(f"DRY RUN Summary:")
            print(f"  Would extract: {extracted_count} files")
        else:
            print(f"Extraction Summary:")
            print(f"  Successfully extracted: {extracted_count} files")
            print(f"  Failed: {failed_count} files")
            print(f"  Output directory: {self.output_dir.resolve()}")
        print("="*70)

    def generate_file_list(self):
        """Generate a text file listing all extracted CONTCAR files"""
        if self.dry_run:
            return

        list_file = self.output_dir / "contcar_file_list.txt"

        with open(list_file, 'w') as f:
            f.write("="*70 + "\n")
            f.write("Extracted CONTCAR Files\n")
            f.write("="*70 + "\n\n")
            f.write(f"Total files: {len(self.contcar_files)}\n")
            f.write(f"Source directory: {self.calc_dir.resolve()}\n")
            f.write(f"Output directory: {self.output_dir.resolve()}\n\n")
            f.write("-"*70 + "\n")
            f.write("File List:\n")
            f.write("-"*70 + "\n\n")

            for _, rel_path in sorted(self.contcar_files):
                f.write(f"{rel_path}\n")

        print(f"\n✓ File list saved to: {list_file}")

    def create_directory_tree(self):
        """Create a visual directory tree of the extracted structure"""
        if self.dry_run:
            return

        tree_file = self.output_dir / "directory_tree.txt"

        with open(tree_file, 'w') as f:
            f.write("="*70 + "\n")
            f.write("Directory Structure\n")
            f.write("="*70 + "\n\n")

            # Build directory tree
            tree_dict = {}
            for _, rel_path in self.contcar_files:
                parts = rel_path.parts
                current = tree_dict
                for part in parts[:-1]:  # Exclude CONTCAR filename
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                # Add CONTCAR to the last directory
                current['CONTCAR'] = None

            # Print tree recursively
            def print_tree(d, prefix="", f=f):
                items = sorted(d.items())
                for i, (name, sub_dict) in enumerate(items):
                    is_last = (i == len(items) - 1)
                    current_prefix = "└── " if is_last else "├── "
                    f.write(f"{prefix}{current_prefix}{name}\n")

                    if sub_dict is not None:
                        extension = "    " if is_last else "│   "
                        print_tree(sub_dict, prefix + extension, f)

            f.write(f"{self.output_dir.name}/\n")
            print_tree(tree_dict, "", f)

        print(f"✓ Directory tree saved to: {tree_file}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Extract CONTCAR files while preserving folder structure'
    )
    parser.add_argument(
        '--calc-dir',
        default='../02_calculations',
        help='Source directory containing calculations (default: ../02_calculations)'
    )
    parser.add_argument(
        '--output-dir',
        default='../extracted_contcars',
        help='Output directory for extracted files (default: ../extracted_contcars)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be extracted without actually copying files'
    )

    args = parser.parse_args()

    # Initialize extractor
    extractor = CONTCARExtractor(
        calc_dir=args.calc_dir,
        output_dir=args.output_dir,
        dry_run=args.dry_run
    )

    # Check if source directory exists
    if not extractor.calc_dir.exists():
        print(f"Error: Source directory does not exist: {extractor.calc_dir.resolve()}")
        print(f"\nPlease make sure you have run the calculations first.")
        print(f"The directory should be created after running: ./02_batch_submit_jobs.sh")
        return

    # Find all CONTCAR files
    contcar_files = extractor.find_all_contcar_files()

    if not contcar_files:
        print("No CONTCAR files found in the calculation directory.")
        print(f"Searched in: {extractor.calc_dir.resolve()}")
        return

    # Extract files
    extractor.extract_contcar_files()

    # Generate reports
    if not args.dry_run:
        extractor.generate_file_list()
        extractor.create_directory_tree()

    print("\n✓ Done!")


if __name__ == "__main__":
    main()
