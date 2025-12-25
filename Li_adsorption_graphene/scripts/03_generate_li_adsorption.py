#!/usr/bin/env python3
"""
Script to generate Li adsorption structures on pristine and doped graphene
Generates multiple adsorption sites: top, hollow, and bridge
"""

import os
import json
from pathlib import Path
from pymatgen.core import Structure
import numpy as np


class LiAdsorptionGenerator:
    """Generate Li adsorption structures on graphene"""

    def __init__(self, input_dir, output_dir, adsorption_height=2.0):
        """
        Initialize the Li adsorption generator

        Args:
            input_dir: Directory containing relaxed doped/pristine structures
            output_dir: Directory to save generated adsorption structures
            adsorption_height: Initial height of Li above graphene plane (Angstroms)
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.adsorption_height = adsorption_height

        # Store metadata for all generated structures
        self.metadata = []

        print(f"Li adsorption height: {adsorption_height} Å")

    def find_adsorption_sites(self, structure, dopant_index=None):
        """
        Find key adsorption sites on graphene surface

        Args:
            structure: pymatgen Structure object
            dopant_index: Index of dopant atom (if any) to define sites relative to it

        Returns:
            Dictionary of adsorption sites with fractional coordinates
        """
        # Get all carbon/dopant atoms (should all be at same z-level for single-layer graphene)
        atoms = [(i, site) for i, site in enumerate(structure)]

        # Find average z-coordinate of graphene sheet
        z_avg = np.mean([site.frac_coords[2] for _, site in atoms])

        # Convert adsorption height to fractional coordinates
        height_frac = self.adsorption_height / structure.lattice.c

        sites = {}

        if dopant_index is not None:
            # For doped structures, define sites relative to dopant
            dopant_coords = structure[dopant_index].frac_coords

            # Top site: directly above the dopant atom
            sites['top_dopant'] = [
                dopant_coords[0],
                dopant_coords[1],
                z_avg + height_frac
            ]

            # Find nearest neighbors to dopant for bridge site
            distances = []
            for i, site in atoms:
                if i != dopant_index:
                    # Calculate distance in xy plane (ignore z)
                    dx = site.frac_coords[0] - dopant_coords[0]
                    dy = site.frac_coords[1] - dopant_coords[1]
                    # Handle periodic boundary conditions
                    dx = dx - np.round(dx)
                    dy = dy - np.round(dy)
                    dist = np.sqrt(dx**2 + dy**2)
                    distances.append((i, dist, site))

            # Sort by distance to find nearest neighbor
            distances.sort(key=lambda x: x[1])

            if len(distances) >= 1:
                nearest_neighbor = distances[0][2]
                # Bridge site: midpoint between dopant and nearest neighbor
                sites['bridge_dopant'] = [
                    (dopant_coords[0] + nearest_neighbor.frac_coords[0]) / 2,
                    (dopant_coords[1] + nearest_neighbor.frac_coords[1]) / 2,
                    z_avg + height_frac
                ]

            if len(distances) >= 2:
                # Find two nearest neighbors that form ~120° angle (hexagon geometry)
                neighbor1 = distances[0][2]
                neighbor2 = distances[1][2]

                # Hollow site: center of triangle formed by dopant and two nearest neighbors
                sites['hollow_dopant'] = [
                    (dopant_coords[0] + neighbor1.frac_coords[0] + neighbor2.frac_coords[0]) / 3,
                    (dopant_coords[1] + neighbor1.frac_coords[1] + neighbor2.frac_coords[1]) / 3,
                    z_avg + height_frac
                ]

        else:
            # For pristine graphene, use generic high-symmetry sites
            # Top site: above an atom (use atom at origin or near center)
            center_atom = None
            min_dist_to_center = float('inf')
            for i, site in atoms:
                # Find atom closest to cell center (0.5, 0.5)
                dx = abs(site.frac_coords[0] - 0.5)
                dy = abs(site.frac_coords[1] - 0.5)
                dist = dx + dy
                if dist < min_dist_to_center:
                    min_dist_to_center = dist
                    center_atom = (i, site)

            if center_atom:
                atom_coords = center_atom[1].frac_coords
                sites['top'] = [
                    atom_coords[0],
                    atom_coords[1],
                    z_avg + height_frac
                ]

                # Find nearest neighbor to this central atom
                distances = []
                for i, site in atoms:
                    if i != center_atom[0]:
                        dx = site.frac_coords[0] - atom_coords[0]
                        dy = site.frac_coords[1] - atom_coords[1]
                        dx = dx - np.round(dx)
                        dy = dy - np.round(dy)
                        dist = np.sqrt(dx**2 + dy**2)
                        distances.append((i, dist, site))

                distances.sort(key=lambda x: x[1])

                if len(distances) >= 1:
                    neighbor = distances[0][2]
                    # Bridge site
                    sites['bridge'] = [
                        (atom_coords[0] + neighbor.frac_coords[0]) / 2,
                        (atom_coords[1] + neighbor.frac_coords[1]) / 2,
                        z_avg + height_frac
                    ]

                if len(distances) >= 2:
                    neighbor1 = distances[0][2]
                    neighbor2 = distances[1][2]
                    # Hollow site
                    sites['hollow'] = [
                        (atom_coords[0] + neighbor1.frac_coords[0] + neighbor2.frac_coords[0]) / 3,
                        (atom_coords[1] + neighbor1.frac_coords[1] + neighbor2.frac_coords[1]) / 3,
                        z_avg + height_frac
                    ]

        return sites

    def generate_adsorption_structures(self, structure_file, dopant=None, dopant_index=13):
        """
        Generate Li adsorption structures for a given graphene structure

        Args:
            structure_file: Path to structure file (POSCAR/CONTCAR)
            dopant: Dopant element name (None for pristine)
            dopant_index: Index of dopant atom (for doped structures)

        Returns:
            List of generated structure file paths
        """
        generated_files = []

        # Load structure
        structure = Structure.from_file(structure_file)

        # Determine base name
        if dopant:
            base_name = f"graphene_{dopant}"
            print(f"\nGenerating Li adsorption sites for {dopant}-doped graphene...")
        else:
            base_name = "graphene_pristine"
            print(f"\nGenerating Li adsorption sites for pristine graphene...")

        # Find adsorption sites
        sites = self.find_adsorption_sites(structure, dopant_index if dopant else None)

        print(f"  Found {len(sites)} adsorption sites: {', '.join(sites.keys())}")

        # Generate structure for each adsorption site
        for site_name, site_coords in sites.items():
            # Create structure with Li adsorbed
            ads_structure = structure.copy()
            ads_structure.append('Li', site_coords, coords_are_cartesian=False)

            # Generate filename
            filename = f"{base_name}_Li_{site_name}.vasp"
            filepath = self.output_dir / filename

            # Save structure
            ads_structure.to(filename=str(filepath), fmt='poscar')
            generated_files.append(str(filepath))

            # Store metadata
            self.metadata.append({
                'filename': filename,
                'structure_type': 'adsorption',
                'substrate': 'doped' if dopant else 'pristine',
                'dopant': dopant,
                'adsorbate': 'Li',
                'adsorption_site': site_name,
                'adsorption_coords': site_coords,
                'composition': ads_structure.composition.formula,
                'num_atoms': len(ads_structure),
            })

            print(f"    ✓ {filename}")

        return generated_files

    def process_all_structures(self, structures_dict):
        """
        Process all doped and pristine structures

        Args:
            structures_dict: Dictionary mapping structure name to file path
                            Format: {'pristine': path, 'B': path, 'N': path, ...}

        Returns:
            List of all generated structure file paths
        """
        all_generated = []

        print("=" * 80)
        print("Generating Li Adsorption Structures")
        print("=" * 80)

        # Process pristine structure
        if 'pristine' in structures_dict:
            files = self.generate_adsorption_structures(
                structures_dict['pristine'],
                dopant=None
            )
            all_generated.extend(files)

        # Process doped structures
        for dopant, filepath in structures_dict.items():
            if dopant != 'pristine':
                files = self.generate_adsorption_structures(
                    filepath,
                    dopant=dopant,
                    dopant_index=13  # C014 position
                )
                all_generated.extend(files)

        return all_generated

    def save_metadata(self, filename='adsorption_structures_metadata.json'):
        """Save metadata for all generated structures"""
        metadata_path = self.output_dir / filename
        with open(metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        print(f"\n✓ Metadata saved to: {metadata_path}")


def main():
    """Main function to generate Li adsorption structures"""

    # Get script directory for absolute paths
    import os
    SCRIPT_DIR = Path(__file__).resolve().parent

    # Configuration
    CALC_DIR_DOPED = SCRIPT_DIR / ".." / "03_calculations" / "doped_relaxation"
    UNRELAXED_DIR = SCRIPT_DIR / ".." / "01_doped_structures"
    OUTPUT_DIR = SCRIPT_DIR / ".." / "02_adsorption_structures"
    ADSORPTION_HEIGHT = 2.0  # Å, initial Li height above graphene

    print("=" * 80)
    print("Li Adsorption Structure Generator")
    print("=" * 80)
    print(f"Looking for relaxed structures in: {CALC_DIR_DOPED}")
    print(f"Fallback to unrelaxed structures in: {UNRELAXED_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Li adsorption height: {ADSORPTION_HEIGHT} Å")
    print("=" * 80)

    structures = {}
    using_relaxed = {}

    # Function to find CONTCAR in calculation directory
    def find_relaxed_structure(calc_dir, structure_name):
        """Find relaxed CONTCAR in mpjob output directory"""
        # mpjob creates: calc_dir/structure_name/structure_name/task_type/CONTCAR
        # Try both possible patterns
        patterns = [
            Path(calc_dir) / structure_name / structure_name / "PBE_U_relax" / "CONTCAR",
            Path(calc_dir) / structure_name / structure_name / "u_relax" / "CONTCAR",
            Path(calc_dir) / structure_name / "CONTCAR",  # Fallback
        ]
        for contcar_path in patterns:
            if contcar_path.exists():
                # Check if calculation completed
                outcar = contcar_path.parent / "OUTCAR"
                if outcar.exists():
                    with open(outcar, 'r') as f:
                        if 'reached required accuracy' in f.read():
                            return str(contcar_path)
        return None

    print("\n" + "-" * 80)
    print("Searching for structures...")
    print("-" * 80)

    # Look for pristine structure (relaxed or unrelaxed)
    pristine_relaxed = find_relaxed_structure(CALC_DIR_DOPED, "graphene_pristine")
    pristine_unrelaxed = Path(UNRELAXED_DIR) / "graphene_pristine.vasp"

    if pristine_relaxed:
        structures['pristine'] = pristine_relaxed
        using_relaxed['pristine'] = True
        print(f"✓ Pristine: Using RELAXED structure from {pristine_relaxed}")
    elif pristine_unrelaxed.exists():
        structures['pristine'] = str(pristine_unrelaxed)
        using_relaxed['pristine'] = False
        print(f"⚠ Pristine: Using UNRELAXED structure (relaxed not found)")
    else:
        print(f"✗ Pristine: Not found")

    # Look for doped structures (relaxed or unrelaxed)
    unrelaxed_dir = Path(UNRELAXED_DIR)
    if unrelaxed_dir.exists():
        for vasp_file in unrelaxed_dir.glob("graphene_*_doped.vasp"):
            # Extract dopant name
            dopant = vasp_file.stem.replace('graphene_', '').replace('_doped', '')
            structure_name = f"graphene_{dopant}_doped"

            # Try to find relaxed version
            relaxed_path = find_relaxed_structure(CALC_DIR_DOPED, structure_name)

            if relaxed_path:
                structures[dopant] = relaxed_path
                using_relaxed[dopant] = True
                print(f"✓ {dopant:>3s}: Using RELAXED structure")
            else:
                structures[dopant] = str(vasp_file)
                using_relaxed[dopant] = False
                print(f"⚠ {dopant:>3s}: Using UNRELAXED structure (relaxed not found)")

    if not structures:
        print("\n✗ Error: No structure files found!")
        print("Please run 01_generate_doped_graphene.py first.")
        return

    # Summary of structure sources
    relaxed_count = sum(1 for v in using_relaxed.values() if v)
    unrelaxed_count = sum(1 for v in using_relaxed.values() if not v)

    print("\n" + "-" * 80)
    print(f"Structure summary: {len(structures)} total ({relaxed_count} relaxed, {unrelaxed_count} unrelaxed)")
    print("-" * 80)

    if unrelaxed_count > 0:
        print("\n⚠ WARNING: Some structures are unrelaxed!")
        print("  For best accuracy, run relaxation calculations first:")
        print("  ./02_relax_doped_structures.sh")
        print("  Then re-run this script to use relaxed structures.")
        print()

    # Initialize generator (use OUTPUT_DIR for output, structures dict has input paths)
    generator = LiAdsorptionGenerator(".", OUTPUT_DIR, ADSORPTION_HEIGHT)

    # Generate adsorption structures
    all_files = generator.process_all_structures(structures)

    # Save metadata (include relaxation status)
    for meta in generator.metadata:
        substrate_key = meta.get('dopant') if meta.get('dopant') else 'pristine'
        meta['using_relaxed_structure'] = using_relaxed.get(substrate_key, False)

    generator.save_metadata()

    print("\n" + "=" * 80)
    print(f"Total Li adsorption structures generated: {len(all_files)}")
    print("=" * 80)

    # Count by substrate type
    pristine_count = len([m for m in generator.metadata if m['substrate'] == 'pristine'])
    doped_count = len([m for m in generator.metadata if m['substrate'] == 'doped'])

    print("\nStructure breakdown:")
    print(f"  Pristine + Li: {pristine_count}")
    print(f"  Doped + Li: {doped_count}")

    # Count by site type
    site_counts = {}
    for m in generator.metadata:
        site = m['adsorption_site']
        site_counts[site] = site_counts.get(site, 0) + 1

    print("\nAdsorption sites:")
    for site, count in sorted(site_counts.items()):
        print(f"  {site}: {count}")

    # Relaxation status summary
    print(f"\nStructure source:")
    print(f"  Based on relaxed structures: {relaxed_count}")
    print(f"  Based on unrelaxed structures: {unrelaxed_count}")

    print("=" * 80)
    print("\nNext steps:")
    print("  1. Submit adsorption calculations: ./04_submit_adsorption_jobs.sh")
    print("  2. After completion, analyze results: python3 05_analyze_results.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
