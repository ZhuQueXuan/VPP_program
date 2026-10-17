"""Run the three storage examples; inputs are constructed format demonstrations."""
import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys

BASE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=None)
    args=parser.parse_args()
    output=args.output_dir or BASE/'outputs'/datetime.now().strftime('example_%Y%m%d_%H%M%S_%f')
    output.mkdir(parents=True,exist_ok=False)
    for script,example,name in [('conversion.py','conversion_input.csv','conversion.csv'),
                                 ('log_power_forecast.py','log_power_input.csv','log_power.csv'),
                                 ('voltage_model.py','voltage_current.csv','voltage.csv')]:
        subprocess.run([sys.executable,str(BASE/'code'/script),'--input',str(BASE/'examples'/example),
                        '--output',str(output/name)],check=True)
    print('Example outputs: '+str(output))


if __name__=='__main__':
    main()
