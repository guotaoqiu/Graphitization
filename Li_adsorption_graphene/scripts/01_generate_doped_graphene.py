#!/usr/bin/env python3
"""
Script to generate doped graphene structures for Li adsorption study
Substitutes C014 atom with various dopant elements
"""

import os
import json
from pathlib import Path
from pymatgen.core import Structure
import numpy as np


class GrapheneDopingGenerator:
    """Generate doped graphene structures by substituting C014"""

    def __init__(self, pristine_structure_path, output_dir):
        """
        Initialize the doping generator

        Args:
            pristine_structure_path: Path to pristine graphene POSCAR
            output_dir: Directory to save generated structures
        """
        self.structure = Structure.from_file(pristine_structure_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Store metadata for all generated structures
        self.metadata = []

        # C014 is at index 13 (0-indexed)
        self.target_site_index = 13

        print(f"Loaded structure with {len(self.structure)} atoms")
        print(f"Target site C014 (index {self.target_site_index}): {self.structure[self.target_site_index].frac_coords}")

    def generate_doped_structures(self, dopant_elements):
        """
        Generate doped structures by substituting C014

        Args:
            dopant_elements: List of dopant elements (e.g., ['B', 'N', 'O', ...])

        Returns:
            List of generated structure file paths
        """
        generated_files = []

        print(f"\nGenerating doped structures for {len(dopant_elements)} elements...")
        print("-" * 80)

        for dopant in dopant_elements:
            # Create a copy of the structure
            doped_structure = self.structure.copy()

            # Substitute C014 (index 13) with dopant
            doped_structure.replace(self.target_site_index, dopant)

            # Generate filename
            filename = f"graphene_{dopant}_doped.vasp"
            filepath = self.output_dir / filename

            # Save structure
            doped_structure.to(filename=str(filepath), fmt='poscar')
            generated_files.append(str(filepath))

            # Store metadata
            self.metadata.append({
                'filename': filename,
                'structure_type': 'doped',
                'dopant': dopant,
                'site_index': self.target_site_index,
                'site_label': 'C014',
                'original_species': 'C',
                'composition': doped_structure.composition.formula,
                'num_atoms': len(doped_structure),
            })

            print(f"  ✓ Generated: {filename} ({doped_structure.composition.formula})")

        return generated_files

    def save_pristine_structure(self):
        """Save a copy of pristine structure for reference"""
        filename = "graphene_pristine.vasp"
        filepath = self.output_dir / filename

        self.structure.to(filename=str(filepath), fmt='poscar')

        self.metadata.append({
            'filename': filename,
            'structure_type': 'pristine',
            'dopant': None,
            'composition': self.structure.composition.formula,
            'num_atoms': len(self.structure),
        })

        print(f"\n  ✓ Saved pristine structure: {filename}")

    def save_metadata(self, filename='doped_structures_metadata.json'):
        """Save metadata for all generated structures"""
        metadata_path = self.output_dir / filename
        with open(metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        print(f"\n✓ Metadata saved to: {metadata_path}")


def main():
    """Main function to generate all doped structures"""

    # Configuration
    PRISTINE_STRUCTURE = "../00_initial_structure/POSCAR_REV.vasp"
    OUTPUT_DIR = "../01_doped_structures"

    # Dopant elements to consider
    # User specified: B, N, O, F, Si, P, S, Cl, Br, I
    # Added a few more potentially interesting elements
    DOPANT_ELEMENTS = [
        'B',   # Boron - electron deficient, expected to have strong Li binding
        'N',   # Nitrogen - isoelectronic to C, slightly more electronegative
        'O',   # Oxygen
        'F',   # Fluorine - highly electronegative
        'Si',  # Silicon - same group as C but larger
        'P',   # Phosphorus
        'S',   # Sulfur
        'Cl',  # Chlorine
        'Br',  # Bromine
        'I',   # Iodine
        'Al',  # Aluminum - similar to B but larger
        'Se',  # Selenium - similar to S
    ]

    print("=" * 80)
    print("Graphene Doping Structure Generator for Li Adsorption Study")
    print("=" * 80)
    print(f"Pristine structure: {PRISTINE_STRUCTURE}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Target site: C014 (index 13)")
    print(f"Number of dopants: {len(DOPANT_ELEMENTS)}")
    print(f"Dopants: {', '.join(DOPANT_ELEMENTS)}")
    print("=" * 80)

    # Check if pristine structure exists
    if not os.path.exists(PRISTINE_STRUCTURE):
        print(f"\n✗ Error: {PRISTINE_STRUCTURE} not found!")
        print("Please ensure the pristine structure file exists.")
        return

    # Initialize generator
    generator = GrapheneDopingGenerator(PRISTINE_STRUCTURE, OUTPUT_DIR)

    # Save pristine structure
    generator.save_pristine_structure()

    # Generate doped structures
    generated_files = generator.generate_doped_structures(DOPANT_ELEMENTS)

    # Save metadata
    generator.save_metadata()

    print("\n" + "=" * 80)
    print(f"Total structures generated: {len(generator.metadata)}")
    print("=" * 80)
    print("\nStructure breakdown:")
    print(f"  Pristine: 1")
    print(f"  Doped: {len(generated_files)}")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Relax doped structures using: ./02_relax_doped_structures.sh")
    print("  2. Generate Li adsorption sites: python3 03_generate_li_adsorption.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
