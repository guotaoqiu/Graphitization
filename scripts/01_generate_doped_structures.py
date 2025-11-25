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

        # If no site indices specified, get only the central C site
        # This ensures one and only one doped atom for lower concentration
        if site_indices is None:
            c_sites = [(i, site) for i, site in enumerate(self.structure)
                      if site.species_string in ['C']]

            # Find the center of the structure
            center = np.mean([site.frac_coords for _, site in c_sites], axis=0)

            # Find the C atom closest to the center
            min_dist = float('inf')
            central_site_idx = None
            for idx, site in c_sites:
                dist = np.linalg.norm(site.frac_coords - center)
                if dist < min_dist:
                    min_dist = dist
                    central_site_idx = idx

            site_indices = [central_site_idx] if central_site_idx is not None else []

        print(f"Using {len(site_indices)} C site(s) for substitutional doping")

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
            interstitial_positions: List of tuples (position, label) for interstitial sites
                                  If None, will use common interstitial positions

        Returns:
            List of generated structure file paths
        """
        generated_files = []

        # Default interstitial positions in graphite
        # One position per site type (duplicates removed due to periodic boundary along c)
        # Each structure contains one and only one doped atom
        if interstitial_positions is None:
            interstitial_positions = [
                # Hollow site (between layers, centered in hexagon)
                ([0.0, 0.0, 0.25], 'hollow'),

                # Atom-above site (between layers, above/below an atom)
                ([0.333333, 0.666667, 0.25], 'above_atom'),

                # Bridge sites (between layers, on edge of hexagon)
                ([0.166667, 0.333333, 0.25], 'bridge'),
                ([0.5, 0.5, 0.25], 'bridge_alt'),

                # In-ring site (inside carbon hexagon, in-plane)
                ([0.333333, 0.666667, 0.0], 'in_ring'),
            ]

        print(f"Using {len(interstitial_positions)} interstitial positions")

        for dopant in dopant_elements:
            for position, pos_label in interstitial_positions:
                # Create a copy of the structure
                doped_structure = self.structure.copy()

                # Add interstitial site
                doped_structure.append(dopant, position, coords_are_cartesian=False)

                # Generate filename
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
                    'position_label': pos_label,
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
            # Get C sites and find the central one
            c_sites = [(i, site) for i, site in enumerate(supercell)
                      if site.species_string == 'C']

            # Find the center of the supercell
            center = np.mean([site.frac_coords for _, site in c_sites], axis=0)

            # Find the C atom closest to the center
            min_dist = float('inf')
            central_site_idx = None
            for idx, site in c_sites:
                dist = np.linalg.norm(site.frac_coords - center)
                if dist < min_dist:
                    min_dist = dist
                    central_site_idx = idx

            for dopant in dopant_elements:
                # Substitute only the central C site (one and only one doped atom)
                if central_site_idx is not None:
                    doped_structure = supercell.copy()
                    doped_structure.replace(central_site_idx, dopant)

                    filename = f"graphite_sub_{dopant}_{supercell_label}.vasp"
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

    def generate_pure_supercells(self, supercell_sizes):
        """
        Generate pure graphite supercells for formation energy calculations

        Args:
            supercell_sizes: List of supercell sizes, e.g., [(2,2,1), (3,3,1), ...]

        Returns:
            List of generated structure file paths
        """
        generated_files = []

        for size in supercell_sizes:
            nx, ny, nz = size
            supercell_matrix = [[nx, 0, 0], [0, ny, 0], [0, 0, nz]]

            # Create supercell
            supercell = self.structure.copy()
            supercell.make_supercell(supercell_matrix)

            supercell_label = f"{nx}x{ny}x{nz}"
            filename = f"graphite_pure_{supercell_label}.vasp"
            filepath = self.output_dir / filename

            supercell.to(filename=str(filepath), fmt='poscar')
            generated_files.append(str(filepath))

            self.metadata.append({
                'filename': filename,
                'doping_type': 'pure',
                'dopant': None,
                'supercell': supercell_label,
                'supercell_size': size,
                'composition': supercell.composition.formula,
                'num_atoms': len(supercell),
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

    # Supercell sizes for different concentrations
    SUPERCELL_SIZES = [(2, 2, 1), (3, 3, 1), (4, 4, 1), (5, 5, 1), (6, 6, 1)]

    # Initialize generator
    generator = GraphiteDopingGenerator(PRISTINE_STRUCTURE, OUTPUT_DIR)

    print("="*80)
    print("Graphite Doping Structure Generator")
    print("="*80)
    print(f"Pristine structure: {PRISTINE_STRUCTURE}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Dopants: {', '.join(DOPANT_ELEMENTS)}")
    print(f"Supercell sizes: {', '.join([f'{x}x{y}x{z}' for x,y,z in SUPERCELL_SIZES])}")
    print("="*80)
    print()

    # Generate pure unit cell
    print("Generating pure graphite (unit cell)...")
    print("-"*80)
    pure_structure = generator.structure.copy()
    pure_filepath = generator.output_dir / "graphite_pure_1x1x1.vasp"
    pure_structure.to(filename=str(pure_filepath), fmt='poscar')
    generator.metadata.append({
        'filename': 'graphite_pure_1x1x1.vasp',
        'doping_type': 'pure',
        'dopant': None,
        'supercell': '1x1x1',
        'composition': pure_structure.composition.formula,
    })
    print(f"Generated: graphite_pure_1x1x1.vasp")
    print()

    # Generate pure supercells
    print("Generating pure graphite supercells...")
    print("-"*80)
    generator.generate_pure_supercells(SUPERCELL_SIZES)
    print()

    # Generate substitutional structures (unit cell)
    print("Generating substitutional structures (unit cell)...")
    print("-"*80)
    generator.generate_substitutional_structures(DOPANT_ELEMENTS)
    print()

    # Generate interstitial structures (unit cell)
    print("Generating interstitial structures (unit cell)...")
    print("-"*80)
    generator.generate_interstitial_structures(DOPANT_ELEMENTS)
    print()

    # Generate supercell doped structures for different concentrations
    print("Generating doped supercell structures...")
    print("-"*80)
    for size in SUPERCELL_SIZES:
        nx, ny, nz = size
        supercell_label = f"{nx}x{ny}x{nz}"
        print(f"\nSupercell {supercell_label}:")
        supercell_matrix = [[nx, 0, 0], [0, ny, 0], [0, 0, nz]]

        # Substitutional doping
        generator.generate_supercell_structures(
            supercell_matrix, DOPANT_ELEMENTS,
            doping_type='substitutional', num_dopants=1
        )

        # Interstitial doping
        generator.generate_supercell_structures(
            supercell_matrix, DOPANT_ELEMENTS,
            doping_type='interstitial', num_dopants=1
        )
    print()

    # Save metadata
    generator.save_metadata()

    print("="*80)
    print(f"Total structures generated: {len(generator.metadata)}")
    print("="*80)
    print("\nStructure breakdown:")
    print(f"  Pure structures: {len([m for m in generator.metadata if m['doping_type'] == 'pure'])}")
    print(f"  Substitutional: {len([m for m in generator.metadata if m['doping_type'] == 'substitutional'])}")
    print(f"  Interstitial: {len([m for m in generator.metadata if m['doping_type'] == 'interstitial'])}")
    print("="*80)


if __name__ == "__main__":
    main()
