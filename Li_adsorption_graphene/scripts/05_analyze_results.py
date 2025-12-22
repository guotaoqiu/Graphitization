#!/usr/bin/env python3
"""
Script to analyze Li adsorption on doped/pristine graphene
Calculates:
1. Formation energy for doped structures: Ef = Edoped - Epure + EC - Esub
2. Adsorption energy for Li: Eads = Etotal - Eslab - ELi
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


# Chemical potential table for elements (DFT calculated)
# Imported from the main workflow
CHEMICAL_POTENTIALS = {
    'Cl': -1.84853666, 'Ir': -8.83843418, 'Tm': -4.475835423333334, 'Li': -1.9089228666666667,
    'Hf': -9.95718903, 'Sb': -4.12900124, 'Mg': -1.60028005, 'Dy': -4.60678684, 'Ho': -4.58240887,
    'Pa': -9.51466466, 'Cd': -0.92288976, 'As': -4.659118405, 'Ne': -0.02593678, 'Tc': -10.360638945,
    'Np': -12.94777968125, 'Tb': -4.6343661, 'Sn': -4.009571855, 'Rb': -0.9805340725, 'Er': -4.56771881,
    'Cs': -0.8954023720689656, 'In': -2.75168373, 'Hg': -0.303680365, 'K': -1.110398947,
    'Na': -1.3225252934482759, 'Sr': -1.6894934533333332, 'Y': -6.466471113333333,
    'P': -5.413302506666667, 'Ba': -1.91897494, 'Nd': -4.7681474325, 'Pt': -6.07113332,
    'Mo': -10.84565011, 'Fe': -8.47002121, 'Zr': -8.54770063, 'Al': -3.74557583, 'Ga': -3.0280960225,
    'Lu': -4.52095052, 'V': -9.08390607, 'Si': -5.42531803, 'Gd': -14.07612224, 'B': -6.679391770833334,
    'Te': -3.1433058933333338, 'Pd': -5.17988181, 'Pb': -3.71264707, 'Ni': -5.78013668,
    'Ar': -0.06880822, 'He': -0.00905951, 'H': -3.392726045, 'N': -8.336494925, 'C': -9.2286654925,
    'La': -4.936007105, 'Cu': -4.09920667, 'Ge': -4.623027855, 'Ru': -9.27440254,
    'Mn': -9.162015292068965, 'Th': -7.41385825, 'Pr': -4.780905755, 'U': -11.29141001,
    'Ca': -2.00559988, 'Os': -11.22736743, 'Ta': -11.85777763, 'Co': -7.108317795, 'F': -1.9114789675,
    'Ce': -5.933089155, 'Bi': -3.84048913, 'Se': -3.49591147765625, 'Pu': -14.26783833,
    'Kr': -0.05671467, 'Eu': -10.2570018, 'I': -1.47336635, 'Sc': -6.332469105, 'Sm': -4.718586135,
    'Ti': -7.895492016666666, 'O': -4.94668871125, 'Rh': -7.36430787, 'Nb': -10.10130504,
    'Zn': -1.25974361, 'Re': -12.444527185, 'Au': -3.273882, 'Ac': -4.1211750075, 'Pm': -4.7505423225,
    'Be': -3.739412865, 'Cr': -9.65304747, 'W': -12.95813023, 'S': -4.136449866875, 'Xe': -0.03617417,
    'Yb': -1.5396082800000002, 'Tl': -2.3626431466666666, 'Ag': -2.8325560033333335, 'Br': -1.55302833
}


class LiAdsorptionAnalyzer:
    """Analyze Li adsorption on doped/pristine graphene"""

    def __init__(self, calc_dir_doped, calc_dir_adsorption, output_dir):
        """
        Initialize the analyzer

        Args:
            calc_dir_doped: Directory with doped structure calculations
            calc_dir_adsorption: Directory with adsorption calculations
            output_dir: Directory to save analysis results
        """
        self.calc_dir_doped = Path(calc_dir_doped)
        self.calc_dir_adsorption = Path(calc_dir_adsorption)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results = {
            'doped_structures': [],
            'adsorption_structures': [],
        }

        # Reference energies
        self.E_pristine = None  # Will be set when pristine structure is analyzed
        self.E_C = CHEMICAL_POTENTIALS.get('C', -9.2286654925)
        self.E_Li = CHEMICAL_POTENTIALS.get('Li', -1.9089228666666667)

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
            return 'unknown'

    def extract_energy(self, job_dir):
        """Extract final energy from VASP output"""
        vasprun_path = job_dir / 'vasprun.xml'
        outcar_path = job_dir / 'OUTCAR'

        try:
            if vasprun_path.exists():
                vasprun = Vasprun(str(vasprun_path), parse_dos=False, parse_eigen=False)
                return vasprun.final_energy
            elif outcar_path.exists():
                outcar = Outcar(str(outcar_path))
                return outcar.final_energy
        except Exception as e:
            print(f"  Warning: Could not extract energy from {job_dir}: {e}")
            return None

        return None

    def analyze_doped_structures(self):
        """
        Analyze relaxed doped structures
        Extract energies and calculate formation energies
        """
        print("\n" + "=" * 80)
        print("Analyzing Doped Structures")
        print("=" * 80)

        if not self.calc_dir_doped.exists():
            print(f"Warning: {self.calc_dir_doped} does not exist")
            return

        # Find all calculation directories
        calc_dirs = [d for d in self.calc_dir_doped.iterdir() if d.is_dir()]

        print(f"Found {len(calc_dirs)} calculation directories\n")

        for calc_dir in sorted(calc_dirs):
            structure_name = calc_dir.name
            print(f"Analyzing: {structure_name}")

            status = self.check_calculation_status(calc_dir)
            print(f"  Status: {status}")

            result = {
                'structure_name': structure_name,
                'status': status,
                'energy': None,
                'formation_energy': None,
            }

            if status != 'completed':
                self.results['doped_structures'].append(result)
                print()
                continue

            # Extract energy
            energy = self.extract_energy(calc_dir)
            result['energy'] = energy

            if energy is not None:
                print(f"  Energy: {energy:.6f} eV")

                # Determine if pristine or doped
                if 'pristine' in structure_name:
                    result['dopant'] = None
                    result['formation_energy'] = 0.0
                    self.E_pristine = energy  # Store pristine energy
                    print(f"  This is pristine structure (reference)")
                else:
                    # Extract dopant from filename: graphene_X_doped
                    parts = structure_name.split('_')
                    if len(parts) >= 2:
                        dopant = parts[1]
                        result['dopant'] = dopant

                        # Calculate formation energy if we have pristine energy
                        if self.E_pristine is not None:
                            if dopant in CHEMICAL_POTENTIALS:
                                E_dopant = CHEMICAL_POTENTIALS[dopant]

                                # Formation energy: Ef = Edoped - Epure + EC - Esub
                                Ef = energy - self.E_pristine + self.E_C - E_dopant
                                result['formation_energy'] = Ef

                                print(f"  Dopant: {dopant}")
                                print(f"  Formation energy: {Ef:.6f} eV")
                                print(f"    (Edoped={energy:.4f}, Epure={self.E_pristine:.4f}, "
                                      f"EC={self.E_C:.4f}, E{dopant}={E_dopant:.4f})")
                            else:
                                print(f"  Warning: No chemical potential for {dopant}")
                        else:
                            print(f"  Warning: Pristine energy not available yet")

            self.results['doped_structures'].append(result)
            print()

    def analyze_adsorption_structures(self):
        """
        Analyze Li adsorption structures
        Calculate adsorption energies
        """
        print("\n" + "=" * 80)
        print("Analyzing Li Adsorption Structures")
        print("=" * 80)

        if not self.calc_dir_adsorption.exists():
            print(f"Warning: {self.calc_dir_adsorption} does not exist")
            return

        # Build slab energy dictionary from doped structure results
        slab_energies = {}
        for result in self.results['doped_structures']:
            if result['status'] == 'completed' and result['energy'] is not None:
                if result.get('dopant') is None:
                    slab_energies['pristine'] = result['energy']
                else:
                    slab_energies[result['dopant']] = result['energy']

        print(f"Available slab energies: {list(slab_energies.keys())}\n")

        # Find all calculation directories
        calc_dirs = [d for d in self.calc_dir_adsorption.iterdir() if d.is_dir()]

        print(f"Found {len(calc_dirs)} calculation directories\n")

        for calc_dir in sorted(calc_dirs):
            structure_name = calc_dir.name
            print(f"Analyzing: {structure_name}")

            status = self.check_calculation_status(calc_dir)
            print(f"  Status: {status}")

            # Parse structure name: graphene_[dopant]_Li_[site] or graphene_pristine_Li_[site]
            parts = structure_name.split('_')

            result = {
                'structure_name': structure_name,
                'status': status,
                'energy': None,
                'adsorption_energy': None,
            }

            # Determine substrate type and site
            if 'pristine' in structure_name:
                result['substrate'] = 'pristine'
                result['dopant'] = None
                # Extract site: graphene_pristine_Li_[site]
                if len(parts) >= 4:
                    result['adsorption_site'] = '_'.join(parts[3:])
            else:
                # Extract dopant: graphene_[dopant]_Li_[site]
                if len(parts) >= 4:
                    result['dopant'] = parts[1]
                    result['substrate'] = 'doped'
                    result['adsorption_site'] = '_'.join(parts[3:])

            if status != 'completed':
                self.results['adsorption_structures'].append(result)
                print()
                continue

            # Extract energy
            energy = self.extract_energy(calc_dir)
            result['energy'] = energy

            if energy is not None:
                print(f"  Energy: {energy:.6f} eV")
                print(f"  Substrate: {result.get('substrate', 'unknown')}")
                print(f"  Adsorption site: {result.get('adsorption_site', 'unknown')}")

                # Calculate adsorption energy: Eads = Etotal - Eslab - ELi
                slab_key = result.get('dopant') if result.get('dopant') else 'pristine'

                if slab_key in slab_energies:
                    E_slab = slab_energies[slab_key]
                    E_ads = energy - E_slab - self.E_Li

                    result['adsorption_energy'] = E_ads
                    result['slab_energy'] = E_slab

                    print(f"  Adsorption energy: {E_ads:.6f} eV")
                    print(f"    (Etotal={energy:.4f}, Eslab={E_slab:.4f}, ELi={self.E_Li:.4f})")
                else:
                    print(f"  Warning: No slab energy for {slab_key}")

            self.results['adsorption_structures'].append(result)
            print()

    def export_results(self):
        """Export results to CSV and JSON files"""
        print("\n" + "=" * 80)
        print("Exporting Results")
        print("=" * 80)

        # Export doped structures
        if self.results['doped_structures']:
            df_doped = pd.DataFrame(self.results['doped_structures'])
            csv_path = self.output_dir / 'doped_structures_results.csv'
            df_doped.to_csv(csv_path, index=False)
            print(f"✓ Doped structures results: {csv_path}")

        # Export adsorption structures
        if self.results['adsorption_structures']:
            df_ads = pd.DataFrame(self.results['adsorption_structures'])
            csv_path = self.output_dir / 'adsorption_results.csv'
            df_ads.to_csv(csv_path, index=False)
            print(f"✓ Adsorption results: {csv_path}")

        # Export complete results as JSON
        json_path = self.output_dir / 'complete_results.json'
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"✓ Complete results (JSON): {json_path}")

        # Generate summary report
        self.generate_summary_report()

    def generate_summary_report(self):
        """Generate a summary report of key findings"""
        report_path = self.output_dir / 'summary_report.txt'

        with open(report_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("Li Adsorption on Doped Graphene - Summary Report\n")
            f.write("=" * 80 + "\n\n")

            # Doped structures summary
            f.write("DOPED STRUCTURES\n")
            f.write("-" * 80 + "\n")
            doped_df = pd.DataFrame(self.results['doped_structures'])

            if len(doped_df) > 0:
                completed = doped_df[doped_df['status'] == 'completed']
                f.write(f"Total: {len(doped_df)}\n")
                f.write(f"Completed: {len(completed)}\n\n")

                if len(completed) > 0:
                    # Formation energies
                    f.write("Formation Energies:\n")
                    formation_data = completed[completed['formation_energy'].notna()].copy()
                    if len(formation_data) > 0:
                        formation_data = formation_data.sort_values('formation_energy')
                        for _, row in formation_data.iterrows():
                            dopant = row.get('dopant', 'Unknown')
                            Ef = row['formation_energy']
                            f.write(f"  {dopant:>3s}: {Ef:>8.4f} eV\n")
                    f.write("\n")

            # Adsorption structures summary
            f.write("\nLI ADSORPTION\n")
            f.write("-" * 80 + "\n")
            ads_df = pd.DataFrame(self.results['adsorption_structures'])

            if len(ads_df) > 0:
                completed_ads = ads_df[ads_df['status'] == 'completed']
                f.write(f"Total: {len(ads_df)}\n")
                f.write(f"Completed: {len(completed_ads)}\n\n")

                if len(completed_ads) > 0:
                    # Group by substrate
                    f.write("Adsorption Energies by Substrate:\n\n")

                    # Pristine
                    pristine = completed_ads[completed_ads['substrate'] == 'pristine']
                    if len(pristine) > 0:
                        f.write("  Pristine Graphene:\n")
                        for _, row in pristine.iterrows():
                            site = row.get('adsorption_site', 'unknown')
                            E_ads = row.get('adsorption_energy')
                            if E_ads is not None:
                                f.write(f"    {site:>20s}: {E_ads:>8.4f} eV\n")
                        f.write("\n")

                    # Doped substrates
                    doped_ads = completed_ads[completed_ads['substrate'] == 'doped']
                    if len(doped_ads) > 0:
                        # Group by dopant
                        dopants = sorted(doped_ads['dopant'].unique())
                        for dopant in dopants:
                            if pd.isna(dopant):
                                continue
                            f.write(f"  {dopant}-doped Graphene:\n")
                            dopant_data = doped_ads[doped_ads['dopant'] == dopant]
                            for _, row in dopant_data.iterrows():
                                site = row.get('adsorption_site', 'unknown')
                                E_ads = row.get('adsorption_energy')
                                if E_ads is not None:
                                    f.write(f"    {site:>20s}: {E_ads:>8.4f} eV\n")
                            f.write("\n")

                    # Find strongest binding sites
                    f.write("\nStrongest Li Binding Sites (most negative Eads):\n")
                    binding_data = completed_ads[completed_ads['adsorption_energy'].notna()].copy()
                    if len(binding_data) > 0:
                        binding_data = binding_data.sort_values('adsorption_energy')
                        f.write(f"{'Rank':<6}{'Substrate':<25}{'Site':<25}{'Eads (eV)':<12}\n")
                        f.write("-" * 80 + "\n")
                        for i, (_, row) in enumerate(binding_data.head(10).iterrows(), 1):
                            substrate = row.get('dopant', 'pristine')
                            if substrate is None or pd.isna(substrate):
                                substrate = 'pristine'
                            site = row.get('adsorption_site', 'unknown')
                            E_ads = row['adsorption_energy']
                            f.write(f"{i:<6}{substrate:<25}{site:<25}{E_ads:<12.4f}\n")

            f.write("\n" + "=" * 80 + "\n")

        print(f"✓ Summary report: {report_path}")


def main():
    """Main function"""
    CALC_DIR_DOPED = "../03_calculations/doped_relaxation"
    CALC_DIR_ADSORPTION = "../03_calculations/adsorption"
    OUTPUT_DIR = "../04_analysis"

    print("=" * 80)
    print("Li Adsorption on Doped Graphene - Results Analysis")
    print("=" * 80)
    print(f"Doped structures directory: {CALC_DIR_DOPED}")
    print(f"Adsorption structures directory: {CALC_DIR_ADSORPTION}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 80)

    # Initialize analyzer
    analyzer = LiAdsorptionAnalyzer(CALC_DIR_DOPED, CALC_DIR_ADSORPTION, OUTPUT_DIR)

    # Analyze doped structures (calculate formation energies)
    analyzer.analyze_doped_structures()

    # Analyze adsorption structures (calculate adsorption energies)
    analyzer.analyze_adsorption_structures()

    # Export results
    analyzer.export_results()

    print("\n" + "=" * 80)
    print("Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
