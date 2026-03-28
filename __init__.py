"""
HAOS Genesis v0.1 — Persistence Engine
Self-contained subsystem extracted from HAOS-IIP
Implements constrained evolution and measurable survival
"""

from .birth_certificate import BirthCertificate
from .generator import generate_universe

__all__ = ["BirthCertificate", "generate_universe"]
