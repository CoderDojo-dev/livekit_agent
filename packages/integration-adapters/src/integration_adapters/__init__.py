"""Adapters: one module per legacy system, each implementing exactly one port.

A vendor API change has a one-module blast radius (Blueprint ADR section 5.4).
These are scaffolds with real signatures; concrete I/O lands in Phases 4-9.
"""