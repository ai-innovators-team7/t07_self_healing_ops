"""Wrapper that delegates deterministic data generation to the pack's generate.py."""

from __future__ import annotations

from seed_packs.t07_self_healing_ops.generate import generate_all

if __name__ == "__main__":
    generate_all()
