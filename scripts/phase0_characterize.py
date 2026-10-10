"""Phase 0: generate the machine/environment JSON record.

Usage:
    python scripts/phase0_characterize.py
"""
from caosched.phase0.env_record import write_environment_record


def main() -> None:
    path = write_environment_record()
    print(f"Wrote environment record to {path}")


if __name__ == "__main__":
    main()
