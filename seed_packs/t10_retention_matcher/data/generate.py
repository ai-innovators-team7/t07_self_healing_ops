"""Wrapper that delegates deterministic data generation to the pack's generate.py."""

from __future__ import annotations

from seed_packs.t10_retention_matcher.generate import generate_all

if __name__ == "__main__":
    generate_all()
