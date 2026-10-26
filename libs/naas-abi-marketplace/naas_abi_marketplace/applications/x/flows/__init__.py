"""Durable NATS flows of the X module.

``search``, ``mapping``, ``reprocess`` and ``count`` are the bodies of the
workflows the module declares (``ABIModule``); ``common``, ``envelopes`` and
``maintenance`` are the pieces the Dagster orchestrations call too. Nothing here
imports Dagster. See AGENTS.md.
"""
