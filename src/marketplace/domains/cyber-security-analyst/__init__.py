"""
Cyber Security Analyst Domain Module

Competency-question-driven cyber security analysis using D3FEND-CCO ontology.
"""

from .agents.CyberSecurityAgent import (
    CyberSecurityAgent,
    create_agent,
    NAME,
    DESCRIPTION,
    AVATAR_URL
)

__all__ = [
    "CyberSecurityAgent",
    "create_agent",
    "NAME",
    "DESCRIPTION",
    "AVATAR_URL",
    "on_initialized"
]


def on_initialized():
    """
    Module initialization hook - loads events.yaml into Oxigraph on startup.
    
    Called automatically by the module loading system after all ontologies are loaded.
    """
    from pathlib import Path
    from abi import logger
    from src import services
    from .pipelines import load_events_to_triplestore
    
    # Load events data into triplestore
    module_dir = Path(__file__).parent
    events_file = module_dir / "samples" / "events.yaml"
    
    if events_file.exists():
        logger.info("📊 Loading cyber security events data...")
        triples_loaded = load_events_to_triplestore(str(events_file), services.triple_store_service)
        if triples_loaded > 0:
            logger.info(f"✅ Cyber security data loaded: {triples_loaded} triples")
        else:
            logger.warning("⚠️ No cyber security data loaded")
    else:
        logger.error(f"❌ Events file not found: {events_file}")