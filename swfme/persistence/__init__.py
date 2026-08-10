"""Persistence-Backend layer for sWFME.

Pluggable storage for workflow runs, steps, outbox entries, and dead-letter
records. The Engine defaults to InMemoryBackend (no external dependencies);
swfme-api uses PostgresBackend for crash-recovery and audit.
"""

from swfme.persistence.base import PersistenceBackend
from swfme.persistence.inmemory import InMemoryBackend

__all__ = ["PersistenceBackend", "InMemoryBackend"]
