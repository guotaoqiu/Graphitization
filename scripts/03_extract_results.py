#!/usr/bin/env python3
"""
Script to extract and analyze results from high-throughput calculations
Extracts: lattice parameters, interlayer spacing, energies, formation energies
"""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from pymatgen.core import Structure
from pymatgen.io.vasp.outputs import Vasprun, Outcar
import warnings
warnings.filterwarnings('ignore')


class GraphiteResultsAnalyzer:
    """Extract and analyze results from doped graphite calculations"""

    def __init__(self, calc_dir, metadata_file=None):
        """
        Initialize the results analyzer

        Args:
            calc_dir: Directory containing calculation results
            metadata_file: Path to structure metadata JSON file
        """
        self.calc_dir = Path(calc_dir)
        self.results = []
        self.metadata = {}

        # Load metadata if available
        if metadata_file and os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                meta_list = json.load(f)
                self.metadata = {m['filename'].replace('.vasp', ''): m
                               for m in meta_list}
            print(f"Loaded metadata for {len(self.metadata)} structures")

    def extract_lattice_parameters(self, structure):
        """Extract lattice parameters from structure"""
        lattice = structure.lattice
        return {
            'a': lattice.a,
            'b': lattice.b,
            'c': lattice.c,
            'alpha': lattice.alpha,
            'beta': lattice.beta,
            'gamma': lattice.gamma,
            'volume': lattice.volume,
        }

    def calculate_interlayer_spacing(self, structure):
        """
        Calculate interlayer spacing for graphite
        Assumes layers are perpendicular to c-axis
        """
        # Get all z-coordinates in fractional coordinates
        z_coords = [site.frac_coords[2] for site in structure]
        z_coords_sorted = sorted(set([round(z, 4) for z in z_coords]))

        if len(z_coords_sorted) >= 2:
            # Calculate spacing between adjacent layers
            spacings = []
            for i in range(len(z_coords_sorted) - 1):
                spacing = abs(z_coords_sorted[i+1] - z_coords_sorted[i])
                # Convert fractional to Cartesian (multiply by c)
                spacing_angstrom = spacing * structure.lattice.c
                spacings.append(spacing_angstrom)

            # Also check spacing across periodic boundary
            boundary_spacing = (1.0 - z_coords_sorted[-1] + z_coords_sorted[0])
            boundary_spacing_angstrom = boundary_spacing * structure.lattice.c
            spacings.append(boundary_spacing_angstrom)

            return {
                'avg_interlayer_spacing': np.mean(spacings),
                'min_interlayer_spacing': np.min(spacings),
                'max_interlayer_spacing': np.max(spacings),
                'num_layers': len(z_coords_sorted),
            }
        else:
            return {
                'avg_interlayer_spacing': None,
                'min_interlayer_spacing': None,
                'max_interlayer_spacing': None,
                'num_layers': len(z_coords_sorted),
            }

    def extract_energy_data(self, vasprun_path, outcar_path):
        """Extract energy data from VASP output files"""
        energy_data = {}

        try:
            # Try to read from vasprun.xml (more reliable)
            if os.path.exists(vasprun_path):
                vasprun = Vasprun(vasprun_path, parse_dos=False, parse_eigen=False)
                energy_data['final_energy'] = vasprun.final_energy
                energy_data['energy_per_atom'] = vasprun.final_energy / len(vasprun.final_structure)

            # Also try OUTCAR
            elif os.path.exists(outcar_path):
                outcar = Outcar(outcar_path)
                energy_data['final_energy'] = outcar.final_energy
                # Get number of atoms from CONTCAR in same directory
                contcar_path = os.path.join(os.path.dirname(outcar_path), 'CONTCAR')
                if os.path.exists(contcar_path):
                    structure = Structure.from_file(contcar_path)
                    energy_data['energy_per_atom'] = outcar.final_energy / len(structure)

        except Exception as e:
            print(f"Warning: Could not extract energy from {vasprun_path}: {e}")
            energy_data['final_energy'] = None
            energy_data['energy_per_atom'] = None

        return energy_data

    def check_calculation_status(self, job_dir):
        """Check if calculation completed successfully"""
        outcar_path = job_dir / 'OUTCAR'

        if not outcar_path.exists():
            return 'not_started'

        try:
            with open(outcar_path, 'r') as f:
                content = f.read()

            if 'reached required accuracy' in content:
                return 'completed'
            elif 'ZBRENT: fatal error' in content or 'ERROR' in content:
                return 'failed'
            else:
                return 'running'
        except Exception as e:
            print(f"Warning: Could not read {outcar_path}: {e}")
            return 'unknown'

    def analyze_single_job(self, job_dir):
        """Analyze results from a single calculation job"""
        job_name = job_dir.name
        print(f"Analyzing: {job_name}")

        result = {
            'job_name': job_name,
            'status': self.check_calculation_status(job_dir),
        }

        # Add metadata if available
        if job_name in self.metadata:
            result.update(self.metadata[job_name])

        # Only extract data from completed calculations
        if result['status'] != 'completed':
            print(f"  Skipping {job_name}: Status = {result['status']}")
            return result

        # Paths to output files
        contcar_path = job_dir / 'CONTCAR'
        vasprun_path = job_dir / 'vasprun.xml'
        outcar_path = job_dir / 'OUTCAR'

        try:
            # Extract structure information
            if contcar_path.exists():
                structure = Structure.from_file(str(contcar_path))

                # Lattice parameters
                lattice_params = self.extract_lattice_parameters(structure)
                result.update(lattice_params)

                # Interlayer spacing
                interlayer_data = self.calculate_interlayer_spacing(structure)
                result.update(interlayer_data)

                # Composition
                result['formula'] = structure.composition.formula
                result['num_atoms'] = len(structure)

            # Extract energy data
            energy_data = self.extract_energy_data(str(vasprun_path), str(outcar_path))
            result.update(energy_data)

            print(f"  ✓ Successfully extracted data")

        except Exception as e:
            print(f"  ✗ Error analyzing {job_name}: {e}")
            result['error'] = str(e)

        return result

    def analyze_all_jobs(self):
        """Analyze all calculation jobs in the directory"""
        print("="*70)
        print("Analyzing All Calculation Results")
        print("="*70)
        print()

        # Find all job directories
        job_dirs = [d for d in self.calc_dir.iterdir() if d.is_dir()]
        print(f"Found {len(job_dirs)} job directories")
        print()

        # Analyze each job
        for job_dir in job_dirs:
            result = self.analyze_single_job(job_dir)
            self.results.append(result)
            print()

        print("="*70)
        print(f"Analysis complete: {len(self.results)} jobs processed")
        print("="*70)

    def calculate_formation_energies(self, pristine_energy_per_atom):
        """
        Calculate formation energies relative to pristine graphite

        Args:
            pristine_energy_per_atom: Energy per atom of pristine graphite
        """
        print("\nCalculating formation energies...")

        for result in self.results:
            if result.get('energy_per_atom') is not None:
                # Simple formation energy (difference from pristine)
                # This is approximate - for more accuracy, need to account for
                # chemical potentials of dopant elements
                result['formation_energy_per_atom'] = (
                    result['energy_per_atom'] - pristine_energy_per_atom
                )

    def export_results(self, output_dir='../03_analysis'):
        """Export results to various formats"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Convert to DataFrame
        df = pd.DataFrame(self.results)

        # Save as CSV
        csv_path = output_dir / 'results_summary.csv'
        df.to_csv(csv_path, index=False)
        print(f"\n✓ Results saved to: {csv_path}")

        # Save as JSON (more complete)
        json_path = output_dir / 'results_complete.json'
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"✓ Complete results saved to: {json_path}")

        # Save summary statistics
        self.generate_summary_report(output_dir)

        return df

    def generate_summary_report(self, output_dir):
        """Generate a summary report of key findings"""
        report_path = output_dir / 'summary_report.txt'

        with open(report_path, 'w') as f:
            f.write("="*70 + "\n")
            f.write("High-Throughput Graphite Doping Study - Summary Report\n")
            f.write("="*70 + "\n\n")

            # Overall statistics
            df = pd.DataFrame(self.results)
            total = len(df)
            completed = len(df[df['status'] == 'completed'])

            f.write(f"Total calculations: {total}\n")
            f.write(f"Completed: {completed}\n")
            f.write(f"Completion rate: {completed/total*100:.1f}%\n\n")

            # Analysis by doping type
            if 'doping_type' in df.columns:
                f.write("Results by doping type:\n")
                f.write("-"*70 + "\n")
                for doping_type in df['doping_type'].unique():
                    if pd.isna(doping_type):
                        continue
                    subset = df[df['doping_type'] == doping_type]
                    completed_subset = subset[subset['status'] == 'completed']

                    f.write(f"\n{doping_type.capitalize()}:\n")
                    f.write(f"  Total: {len(subset)}\n")
                    f.write(f"  Completed: {len(completed_subset)}\n")

                    if len(completed_subset) > 0 and 'avg_interlayer_spacing' in completed_subset.columns:
                        avg_spacing = completed_subset['avg_interlayer_spacing'].mean()
                        f.write(f"  Avg interlayer spacing: {avg_spacing:.4f} Å\n")

            # Analysis by dopant
            if 'dopant' in df.columns:
                f.write("\n\nResults by dopant element:\n")
                f.write("-"*70 + "\n")
                completed_df = df[df['status'] == 'completed']

                if len(completed_df) > 0:
                    for dopant in sorted(df['dopant'].unique()):
                        if pd.isna(dopant):
                            continue
                        subset = completed_df[completed_df['dopant'] == dopant]

                        if len(subset) > 0:
                            f.write(f"\n{dopant}:\n")
                            f.write(f"  Number of structures: {len(subset)}\n")

                            if 'avg_interlayer_spacing' in subset.columns:
                                mean_spacing = subset['avg_interlayer_spacing'].mean()
                                std_spacing = subset['avg_interlayer_spacing'].std()
                                f.write(f"  Interlayer spacing: {mean_spacing:.4f} ± {std_spacing:.4f} Å\n")

                            if 'c' in subset.columns:
                                mean_c = subset['c'].mean()
                                std_c = subset['c'].std()
                                f.write(f"  c parameter: {mean_c:.4f} ± {std_c:.4f} Å\n")

                            if 'energy_per_atom' in subset.columns:
                                mean_energy = subset['energy_per_atom'].mean()
                                f.write(f"  Avg energy per atom: {mean_energy:.4f} eV\n")

            f.write("\n" + "="*70 + "\n")

        print(f"✓ Summary report saved to: {report_path}")


def main():
    """Main function"""
    CALC_DIR = "../02_calculations"
    METADATA_FILE = "../01_structure_generation/doped_structures/structure_metadata.json"
    OUTPUT_DIR = "../03_analysis"

    print("="*70)
    print("Graphite Doping Results Extraction and Analysis")
    print("="*70)
    print()

    # Initialize analyzer
    analyzer = GraphiteResultsAnalyzer(CALC_DIR, METADATA_FILE)

    # Analyze all jobs
    analyzer.analyze_all_jobs()

    # Calculate formation energies (optional - need pristine energy)
    # To use this, first run pristine graphite calculation and get energy
    # PRISTINE_ENERGY_PER_ATOM = -9.XXX  # Replace with actual value
    # analyzer.calculate_formation_energies(PRISTINE_ENERGY_PER_ATOM)

    # Export results
    df = analyzer.export_results(OUTPUT_DIR)

    # Display quick summary
    print("\nQuick Summary:")
    print("-"*70)
    print(f"Total jobs: {len(df)}")
    print(f"Completed: {len(df[df['status'] == 'completed'])}")
    print(f"Failed: {len(df[df['status'] == 'failed'])}")
    print(f"Running: {len(df[df['status'] == 'running'])}")


if __name__ == "__main__":
    main()
