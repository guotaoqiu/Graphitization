#!/usr/bin/env python3
"""
Export doped graphite calculation results to structured JSON format
Prepares data for MongoDB database upload
"""

import os
import json
import pandas as pd
from pathlib import Path
from pymatgen.core import Structure, Composition
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from datetime import datetime


class GraphiteResultsExporter:
    """Export calculation results to structured JSON format"""

    def __init__(self, results_csv, calc_dir):
        """
        Initialize the exporter

        Args:
            results_csv: Path to results CSV file from 03_extract_results.py
            calc_dir: Directory containing calculation results
        """
        self.results_csv = Path(results_csv)
        self.calc_dir = Path(calc_dir)
        self.export_data = []

    def load_results(self):
        """Load results from CSV"""
        df = pd.read_csv(self.results_csv)
        # Filter only completed calculations
        df_completed = df[df['status'] == 'completed'].copy()
        print(f"Loaded {len(df_completed)} completed calculations")
        return df_completed

    def create_document(self, row):
        """
        Create a structured document for a single calculation

        Args:
            row: DataFrame row with calculation results

        Returns:
            Dictionary with structured data
        """
        # Load final structure
        job_name = row['job_name']
        contcar_path = self.calc_dir / job_name / 'CONTCAR'

        if not contcar_path.exists():
            print(f"Warning: CONTCAR not found for {job_name}")
            return None

        try:
            structure = Structure.from_file(str(contcar_path))
        except Exception as e:
            print(f"Error loading structure for {job_name}: {e}")
            return None

        # Basic composition information
        formula = structure.composition.formula.replace(' ', '')
        composition = Composition(formula)
        reduced_formula = composition.reduced_formula
        formula_anonymous = composition.anonymized_formula
        chemsys = composition.chemical_system

        # Structure information
        nsites = structure.num_sites
        elements = [str(el) for el in composition.elements]
        nelements = len(elements)
        composition_dict = composition.as_dict()
        composition_reduced = composition.reduced_composition.as_dict()

        # Volume and density
        volume = structure.volume
        density = structure.density
        density_atomic = volume / nsites

        # Symmetry information
        try:
            symmetry = SpacegroupAnalyzer(structure)
            symmetry_dict = {
                'crystal_system': symmetry.get_crystal_system(),
                'lattice_system': symmetry.get_lattice_type(),
                'hall_number': symmetry.get_hall(),
                'international_number': structure.get_space_group_info()[1],
                'symbol': symmetry.get_space_group_symbol(),
                'point_group': symmetry.get_point_group_symbol()
            }
        except Exception as e:
            print(f"Warning: Could not get symmetry for {job_name}: {e}")
            symmetry_dict = None

        # Lattice parameters
        lattice = structure.lattice
        lattice_dict = {
            'a': lattice.a,
            'b': lattice.b,
            'c': lattice.c,
            'alpha': lattice.alpha,
            'beta': lattice.beta,
            'gamma': lattice.gamma,
            'volume': lattice.volume,
        }

        # Energy information
        energy_per_atom = row.get('energy_per_atom')
        final_energy = row.get('final_energy')
        formation_energy_per_atom = row.get('formation_energy_per_atom')
        formation_energy = row.get('formation_energy')

        # Doping information
        doping_type = row.get('doping_type')
        dopant = row.get('dopant')
        doping_concentration = row.get('doping_concentration_percent')

        # Interlayer spacing (graphite-specific)
        avg_interlayer_spacing = row.get('avg_interlayer_spacing')

        # Create document
        doc = {
            # Basic identification
            'job_name': job_name,
            'import_time': datetime.utcnow().isoformat(),

            # Composition
            'formula': formula,
            'reduced_formula': reduced_formula,
            'formula_anonymous': formula_anonymous,
            'chemsys': chemsys,

            # Structure counts
            'nsites': nsites,
            'elements': elements,
            'nelements': nelements,
            'composition': composition_dict,
            'composition_reduced': composition_reduced,

            # Physical properties
            'volume': volume,
            'density': density,
            'density_atomic': density_atomic,

            # Lattice parameters
            'lattice_parameters': lattice_dict,

            # Symmetry
            'symmetry': symmetry_dict,

            # Structure
            'structure': structure.as_dict(),

            # Energy
            'energy_per_atom': float(energy_per_atom) if pd.notna(energy_per_atom) else None,
            'final_energy': float(final_energy) if pd.notna(final_energy) else None,
            'formation_energy_per_atom': float(formation_energy_per_atom) if pd.notna(formation_energy_per_atom) else None,
            'formation_energy': float(formation_energy) if pd.notna(formation_energy) else None,

            # Doping information
            'doping_type': doping_type if pd.notna(doping_type) else None,
            'dopant': dopant if pd.notna(dopant) else None,
            'doping_concentration_percent': float(doping_concentration) if pd.notna(doping_concentration) else None,

            # Graphite-specific properties
            'avg_interlayer_spacing': float(avg_interlayer_spacing) if pd.notna(avg_interlayer_spacing) else None,

            # Supercell info
            'supercell': row.get('supercell') if pd.notna(row.get('supercell')) else '1x1x1',

            # Metadata
            'calculation_status': 'completed',
            'source': 'high_throughput_graphite_doping_study',
        }

        return doc

    def export_to_json(self, output_path='../03_analysis/results_database.json'):
        """
        Export all results to JSON file

        Args:
            output_path: Path to output JSON file
        """
        print("\n" + "="*70)
        print("Exporting Results to JSON")
        print("="*70)

        # Load results
        df = self.load_results()

        # Create documents
        print("\nCreating documents...")
        for idx, row in df.iterrows():
            doc = self.create_document(row)
            if doc is not None:
                self.export_data.append(doc)
                if (idx + 1) % 10 == 0:
                    print(f"  Processed {idx + 1}/{len(df)} calculations")

        print(f"\nCreated {len(self.export_data)} documents")

        # Save to JSON
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(self.export_data, f, indent=2)

        print(f"\n✓ Results exported to: {output_path}")
        print(f"  Total documents: {len(self.export_data)}")

        # Print summary
        self.print_summary()

        return self.export_data

    def print_summary(self):
        """Print summary of exported data"""
        print("\n" + "="*70)
        print("Export Summary")
        print("="*70)

        # Count by doping type
        doping_types = {}
        dopants = {}
        for doc in self.export_data:
            dt = doc.get('doping_type', 'unknown')
            doping_types[dt] = doping_types.get(dt, 0) + 1

            if dt != 'pure':
                dopant = doc.get('dopant', 'unknown')
                dopants[dopant] = dopants.get(dopant, 0) + 1

        print("\nBy doping type:")
        for dt, count in sorted(doping_types.items()):
            print(f"  {dt}: {count}")

        print("\nBy dopant element:")
        for dopant, count in sorted(dopants.items()):
            print(f"  {dopant}: {count}")

        print("\n" + "="*70)


def main():
    """Main function"""
    RESULTS_CSV = "../03_analysis/results_summary.csv"
    CALC_DIR = "../02_calculations"
    OUTPUT_JSON = "../03_analysis/results_database.json"

    print("="*70)
    print("Graphite Doping Results - JSON Export")
    print("="*70)

    # Check if results file exists
    if not os.path.exists(RESULTS_CSV):
        print(f"\nError: Results file not found: {RESULTS_CSV}")
        print("Please run 03_extract_results.py first")
        return

    # Initialize exporter
    exporter = GraphiteResultsExporter(RESULTS_CSV, CALC_DIR)

    # Export to JSON
    exporter.export_to_json(OUTPUT_JSON)

    print("\n" + "="*70)
    print("Export Complete")
    print("="*70)
    print(f"\nJSON file ready for database upload: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
