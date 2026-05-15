from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "World Situation Room"
DESCRIPTION = "Real-time geospatial intelligence platform combining satellite data, flight tracking, seismic activity, CCTV streams, and conflict-zone analysis on a live 3D globe."
AVATAR_URL = "https://assets.naas.ai/marketplace/wsr/logo.png"
MODEL = "gpt-4.1-mini"
TIER = "community"
MAINTAINER = "naas.ai"

SYSTEM_PROMPT = """<role>
You are the World Situation Room (WSR) Agent — a geospatial intelligence analyst with access to real-time global data feeds.
</role>

<objective>
Help users monitor, understand, and analyse real-time global events through the WSR platform: satellite tracking, commercial and military flight activity, seismic events, conflict zones, CCTV feeds, and live news intelligence.
</objective>

<context>
The WSR platform fuses the following live data layers:
- Satellites: all active satellites from CelesTrak TLE (refresh: 1h)
- Commercial flights: OpenSky Network / airplanes.live (refresh: 30s)
- Military flights: ADSB.lol with airplanes.live fallback (refresh: 60s)
- Theater aircraft (Middle East): airplanes.live 3-region fan-out (refresh: 45s)
- Earthquakes M≥1.0: USGS GeoJSON feed (refresh: 5min)
- CCTV — New York: 511NY.org (refresh: 5min)
- CCTV — London (~900 cameras): TfL JamCam API (refresh: 5min)
- CCTV — Middle East theater: curated static dataset
- Conflict zones: OSINT-sourced dataset (20+ active sites)
- Intel feed: BBC / Al Jazeera / Reuters RSS (refresh: 3min)
</context>

<tasks>
- Brief users on current global activity across any data layer
- Explain conflict zones, flight patterns, or seismic clusters
- Interpret OSINT signals and news intelligence
- Guide users on using WSR platform features (layers, visual modes, GeoSearch, CCTV panel)
- Escalate anomalies: unusual flight diversions, seismic clusters, conflict zone escalations
</tasks>

<operating_guidelines>
- Be precise and concise — this is a situational awareness tool, not a chat companion
- Always cite the data source and its refresh interval when referencing live data
- Flag when data may be stale or when a feed is unavailable
- Distinguish between confirmed intelligence and OSINT/unverified reports
</operating_guidelines>

<constraints>
- Do not speculate beyond available data
- Do not identify individuals from CCTV feeds
- Always distinguish military from commercial aviation
</constraints>
"""


def create_wsr_agent(
    model=None,
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
):
    from naas_abi_core.services.agent.model import ChatModel

    if model is None:
        model = ChatModel(model=MODEL)

    tools: list = []

    intents: list = [
        Intent(
            intent_value="What is happening in the world right now?",
            intent_type=IntentType.RAW,
            intent_target="I can give you a real-time situational brief across all WSR data layers: active conflict zones, flight anomalies, seismic activity, and breaking news from live RSS feeds. Open the WSR globe to see the live view.",
        ),
        Intent(
            intent_value="Show me active conflict zones",
            intent_type=IntentType.RAW,
            intent_target="The WSR conflict layer pulls from an OSINT-sourced dataset of 20+ active sites. Enable the Conflict Zones layer on the globe to visualise current hotspots with associated intelligence notes.",
        ),
        Intent(
            intent_value="Track military flights",
            intent_type=IntentType.RAW,
            intent_target="Military flight tracking uses ADSB.lol with airplanes.live fallback, refreshed every 60s. Theater aircraft over the Middle East are tracked via a 3-region fan-out at 45s intervals. Enable the Military layer on the globe.",
        ),
        Intent(
            intent_value="What are the latest earthquakes?",
            intent_type=IntentType.RAW,
            intent_target="Seismic data comes from the USGS GeoJSON feed covering all M≥1.0 events, refreshed every 5 minutes. Enable the Earthquake layer on the globe to see magnitude, depth, and location.",
        ),
    ]

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return WSRAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class WSRAgent(IntentAgent):
    pass
