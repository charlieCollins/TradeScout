#!/usr/bin/env python3
"""
Default Universe Bootstrap Script

Populates the default universe from existing ticker data using strict filtering criteria.
This should be run after ticker bootstrapping to create the filtered trading universe.

Usage:
    python -m tradescout.scripts.bootstrap_default_universe --help
    python -m tradescout.scripts.bootstrap_default_universe --stats-only
    python -m tradescout.scripts.bootstrap_default_universe --dry-run
    python -m tradescout.scripts.bootstrap_default_universe
"""

from ..bootstrapping.default_universe_bootstrapper import main

if __name__ == '__main__':
    main()