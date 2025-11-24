#!/usr/bin/env python3
"""
Script to generate doped graphite structures
Supports both substitutional and interstitial doping
"""

import os
import json
from pathlib import Path
from pymatgen.core import Structure
from pymatgen.transformations.standard_transformations import (
    SubstitutionTransformation,
)
from pymatgen.transformations.site_transformations import InsertSitesTransformation
import numpy as np


class GraphiteDopingGenerator:
    """Generate doped graphite structures for high-throughput calculations"""

    def __init__(self, pristine_structure_path, output_dir):
        """
        Initialize the doping generator

        Args:
            pristine_structure_path: Path to relaxed pristine graphite CONTCAR/POSCAR
            output_dir: Directory to save generated structures
        """
        self.structure = Structure.from_file(pristine_structure_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Store metadata for all generated structures
        self.metadata = []

    def generate_substitutional_structures(self, dopant_elements, site_indices=None):
        """
        Generate substitutional doped structures

        Args:
            dopant_elements: List of dopant elements (e.g., ['B', 'La', 'Mg'])
            site_indices: List of site indices to substitute. If None, will substitute all C sites

        Returns:
            List of generated structure file paths
        """
        generated_files = []

        # If no site indices specified, get all C sites
        if site_indices is None:
            site_indices = [i for i, site in enumerate(self.structure)
                          if site.species_string in ['C']]

        print(f"Found {len(site_indices)} C sites for substitutional doping")

        for dopant in dopant_elements:
            for site_idx in site_indices:
                # Create a copy of the structure
                doped_structure = self.structure.copy()

                # Substitute the site
                doped_structure.replace(site_idx, dopant)

                # Generate filename
                site_label = f"site{site_idx}"
                filename = f"graphite_sub_{dopant}_{site_label}.vasp"
                filepath = self.output_dir / filename

                # Save structure
                doped_structure.to(filename=str(filepath), fmt='poscar')
                generated_files.append(str(filepath))

                # Store metadata
                self.metadata.append({
                    'filename': filename,
                    'doping_type': 'substitutional',
                    'dopant': dopant,
                    'site_index': site_idx,
                    'original_species': 'C',
                    'composition': doped_structure.composition.formula,
                })

                print(f"Generated: {filename}")

        return generated_files

    def generate_interstitial_structures(self, dopant_elements, interstitial_positions=None):
        """
        Generate interstitial doped structures

        Args:
            dopant_elements: List of dopant elements (e.g., ['B', 'La', 'Mg'])
            interstitial_positions: List of fractional coordinates for interstitial sites
                                  If None, will use common interstitial positions

        Returns:
            List of generated structure file paths
        """
        generated_files = []

        # Default interstitial positions in graphite
        # Between layers at hollow sites
        if interstitial_positions is None:
            interstitial_positions = [
                [0.0, 0.0, 0.25],      # Between layer 1 and 2, hollow site
                [0.333333, 0.666667, 0.25],  # Between layer 1 and 2, over atom site
                [0.0, 0.0, 0.75],      # Between layer 2 and 1, hollow site
                [0.666667, 0.333333, 0.75],  # Between layer 2 and 1, over atom site
            ]

        print(f"Using {len(interstitial_positions)} interstitial positions")

        for dopant in dopant_elements:
            for idx, position in enumerate(interstitial_positions):
                # Create a copy of the structure
                doped_structure = self.structure.copy()

                # Add interstitial site
                doped_structure.append(dopant, position, coords_are_cartesian=False)

                # Generate filename
                pos_label = f"pos{idx}"
                filename = f"graphite_int_{dopant}_{pos_label}.vasp"
                filepath = self.output_dir / filename

                # Save structure
                doped_structure.to(filename=str(filepath), fmt='poscar')
                generated_files.append(str(filepath))

                # Store metadata
                self.metadata.append({
                    'filename': filename,
                    'doping_type': 'interstitial',
                    'dopant': dopant,
                    'position': position,
                    'composition': doped_structure.composition.formula,
                })

                print(f"Generated: {filename}")

        return generated_files

    def generate_supercell_structures(self, supercell_matrix, dopant_elements,
                                     doping_type='substitutional', num_dopants=1):
        """
        Generate doped supercell structures for lower doping concentrations

        Args:
            supercell_matrix: Supercell matrix, e.g., [[2,0,0],[0,2,0],[0,0,1]]
            dopant_elements: List of dopant elements
            doping_type: 'substitutional' or 'interstitial'
            num_dopants: Number of dopant atoms to add

        Returns:
            List of generated structure file paths
        """
        generated_files = []

        # Create supercell
        supercell = self.structure.copy()
        supercell.make_supercell(supercell_matrix)

        supercell_label = "x".join([str(m[i]) for i, m in enumerate(supercell_matrix)])

        if doping_type == 'substitutional':
            # Get C sites
            c_sites = [i for i, site in enumerate(supercell)
                      if site.species_string == 'C']

            for dopant in dopant_elements:
                # Substitute first num_dopants C sites
                for site_combo_idx in range(min(num_dopants, len(c_sites))):
                    doped_structure = supercell.copy()
                    doped_structure.replace(c_sites[site_combo_idx], dopant)

                    filename = f"graphite_sub_{dopant}_{supercell_label}_n{site_combo_idx+1}.vasp"
                    filepath = self.output_dir / filename

                    doped_structure.to(filename=str(filepath), fmt='poscar')
                    generated_files.append(str(filepath))

                    self.metadata.append({
                        'filename': filename,
                        'doping_type': 'substitutional',
                        'dopant': dopant,
                        'supercell': supercell_label,
                        'num_dopants': 1,
                        'composition': doped_structure.composition.formula,
                    })

                    print(f"Generated: {filename}")

        elif doping_type == 'interstitial':
            # Use first interstitial position scaled to supercell
            for dopant in dopant_elements:
                doped_structure = supercell.copy()
                # Add interstitial at a typical position
                doped_structure.append(dopant, [0.0, 0.0, 0.25], coords_are_cartesian=False)

                filename = f"graphite_int_{dopant}_{supercell_label}.vasp"
                filepath = self.output_dir / filename

                doped_structure.to(filename=str(filepath), fmt='poscar')
                generated_files.append(str(filepath))

                self.metadata.append({
                    'filename': filename,
                    'doping_type': 'interstitial',
                    'dopant': dopant,
                    'supercell': supercell_label,
                    'composition': doped_structure.composition.formula,
                })

                print(f"Generated: {filename}")

        return generated_files

    def save_metadata(self, filename='structure_metadata.json'):
        """Save metadata for all generated structures"""
        metadata_path = self.output_dir / filename
        with open(metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        print(f"\nMetadata saved to: {metadata_path}")


def main():
    """Main function to generate all doped structures"""

    # Configuration
    PRISTINE_STRUCTURE = "../00_initial_structure/CONTCAR"  # Use relaxed structure
    OUTPUT_DIR = "../01_structure_generation/doped_structures"

    # Check if relaxed structure exists, otherwise use pristine
    if not os.path.exists(PRISTINE_STRUCTURE):
        print(f"Warning: {PRISTINE_STRUCTURE} not found.")
        print("Using pristine structure. Run initial relaxation first for best results!")
        PRISTINE_STRUCTURE = "../00_initial_structure/graphite_pristine.vasp"

    # Dopant elements to consider
    DOPANT_ELEMENTS = ['B', 'N', 'La', 'Mg', 'Al', 'Si', 'P', 'S']

    # Initialize generator
    generator = GraphiteDopingGenerator(PRISTINE_STRUCTURE, OUTPUT_DIR)

    print("="*60)
    print("Graphite Doping Structure Generator")
    print("="*60)
    print(f"Pristine structure: {PRISTINE_STRUCTURE}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Dopants: {', '.join(DOPANT_ELEMENTS)}")
    print("="*60)
    print()

    # Generate substitutional structures (unit cell)
    print("Generating substitutional structures (unit cell)...")
    print("-"*60)
    generator.generate_substitutional_structures(DOPANT_ELEMENTS)
    print()

    # Generate interstitial structures (unit cell)
    print("Generating interstitial structures (unit cell)...")
    print("-"*60)
    generator.generate_interstitial_structures(DOPANT_ELEMENTS)
    print()

    # Generate supercell structures for lower concentrations (optional)
    # Uncomment if you want to study lower doping concentrations
    # print("Generating supercell structures (2x2x1)...")
    # print("-"*60)
    # supercell_matrix = [[2, 0, 0], [0, 2, 0], [0, 0, 1]]
    # generator.generate_supercell_structures(supercell_matrix, DOPANT_ELEMENTS[:3],
    #                                        doping_type='substitutional')
    # print()

    # Save metadata
    generator.save_metadata()

    print("="*60)
    print(f"Total structures generated: {len(generator.metadata)}")
    print("="*60)


if __name__ == "__main__":
    main()
