"""Rerun independent closure inputs in a new directory, preserving prior evidence."""
from pathlib import Path
import audit_round2

if __name__=='__main__':
    audit_round2.OUT=Path(__file__).resolve().parent/'round3'
    audit_round2.OUT.mkdir(exist_ok=True)
    audit_round2.main()
