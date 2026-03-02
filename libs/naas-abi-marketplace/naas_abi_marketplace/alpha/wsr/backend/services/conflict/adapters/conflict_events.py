"""
Conflict events adapter — fully static OSINT-sourced dataset.

20 named sites: Iranian nuclear sites, Israeli military, US CENTCOM bases,
and regional flashpoints.

Source basis: IAEA public records, US DoD public releases, OSINT.
"""

from ports.models import ConflictEvent
from services.conflict.ConflictPort import IConflictAdapter

_EVENTS: list[ConflictEvent] = [
    # ── Iran nuclear program ───────────────────────────────────────────────────
    ConflictEvent(id="natanz", name="Natanz Enrichment Complex", lat=33.724, lon=51.727, type="nuclear", country="Iran", description="Primary uranium enrichment facility. Underground centrifuge halls. IAEA monitored.", severity="critical"),
    ConflictEvent(id="fordow", name="Fordow Fuel Enrichment Plant", lat=34.884, lon=50.997, type="nuclear", country="Iran", description="Deep underground enrichment site near Qom. Highly hardened, 80m below rock.", severity="critical"),
    ConflictEvent(id="isfahan", name="Isfahan Nuclear Technology Centre", lat=32.607, lon=51.649, type="nuclear", country="Iran", description="Uranium conversion facility (UCF). Produces UF6 feed for centrifuges.", severity="high"),
    ConflictEvent(id="arak", name="Arak Heavy Water Reactor", lat=34.320, lon=49.166, type="nuclear", country="Iran", description="IR-40 heavy water reactor site. Modified under JCPOA. Plutonium production capability.", severity="high"),
    ConflictEvent(id="bushehr", name="Bushehr Nuclear Power Plant", lat=28.829, lon=50.888, type="nuclear", country="Iran", description="Russian-built civilian nuclear power station on the Persian Gulf coast.", severity="medium"),
    # ── Iran military / government ─────────────────────────────────────────────
    ConflictEvent(id="tehran", name="Tehran — Iranian Capital", lat=35.689, lon=51.389, type="capital", country="Iran", description="Seat of the Supreme Leader and IRGC command. IRGC HQ located in NE Tehran.", severity="critical"),
    ConflictEvent(id="irgc-aerospace", name="IRGC Aerospace Force HQ", lat=35.750, lon=51.450, type="base", country="Iran", description="Commands Iranian ballistic missile and drone programs. Shaheed / Shahed UAVs.", severity="critical"),
    # ── Israel ────────────────────────────────────────────────────────────────
    ConflictEvent(id="tel-aviv", name="Tel Aviv / IDF HQ", lat=32.085, lon=34.782, type="capital", country="Israel", description="Israeli military HQ (Kirya). Financial and population center. Iron Dome batteries active.", severity="critical"),
    ConflictEvent(id="dimona", name="Negev Nuclear Research Centre (Dimona)", lat=30.973, lon=35.143, type="nuclear", country="Israel", description="Undeclared Israeli nuclear weapons research facility. Not under IAEA safeguards.", severity="high"),
    ConflictEvent(id="nevatim", name="Nevatim Air Base", lat=31.208, lon=35.012, type="base", country="Israel", description="Home of IAF F-35I Adir squadrons. Primary long-range strike platform.", severity="high"),
    ConflictEvent(id="ramat-david", name="Ramat David Air Base", lat=32.665, lon=35.180, type="base", country="Israel", description="Northern IAF base. F-16I squadrons. Key role in northern theater operations.", severity="medium"),
    ConflictEvent(id="haifa", name="Haifa — Naval Base & Industry", lat=32.794, lon=34.990, type="naval", country="Israel", description="Israeli Navy HQ. Rafael Advanced Defense Systems nearby. Critical port infrastructure.", severity="high"),
    # ── US CENTCOM forward bases ───────────────────────────────────────────────
    ConflictEvent(id="udeid", name="Al Udeid Air Base (Qatar)", lat=25.117, lon=51.314, type="base", country="Qatar (US CENTCOM)", description="Largest US air base in Middle East. CENTCOM forward HQ. B-52, KC-135 operations.", severity="high"),
    ConflictEvent(id="dhafra", name="Al Dhafra Air Base (UAE)", lat=24.248, lon=54.548, type="base", country="UAE (US Air Force)", description="F-35A, U-2 reconnaissance, KC-10 tankers. Key ISR and strike enabler.", severity="high"),
    ConflictEvent(id="ali-al-salem", name="Ali Al Salem Air Base (Kuwait)", lat=29.347, lon=47.521, type="base", country="Kuwait (US)", description="US Army and Air Force hub near Iraq border. Critical logistics node.", severity="medium"),
    ConflictEvent(id="carrier-strike", name="Persian Gulf — Carrier Strike Group AO", lat=26.500, lon=56.200, type="naval", country="US Navy", description="Approximate operating area for CSG. Strait of Hormuz chokepoint. Iranian IRGC fast-boat threat.", severity="critical"),
    ConflictEvent(id="hormuz", name="Strait of Hormuz", lat=26.594, lon=56.451, type="zone", country="International Waters", description="~20% of global oil transit. Iranian mining threat. IRGC naval patrol zone.", severity="critical"),
    # ── Regional flashpoints ───────────────────────────────────────────────────
    ConflictEvent(id="beirut", name="Beirut — Hezbollah Presence", lat=33.888, lon=35.495, type="zone", country="Lebanon", description="Hezbollah political and military HQ in southern suburbs (Dahiyeh). Active front.", severity="high"),
    ConflictEvent(id="damascus", name="Damascus — Syrian Regime Axis", lat=33.510, lon=36.291, type="zone", country="Syria", description="IRGC and Hezbollah logistics corridor. Repeated IAF interdiction strikes.", severity="high"),
    ConflictEvent(id="baghdad", name="Baghdad — Iraqi PMF Militia", lat=33.338, lon=44.394, type="zone", country="Iraq", description="Iran-aligned Popular Mobilization Forces (PMF) HQ. Proxy activity against US interests.", severity="medium"),
]


class ConflictEventsAdapter(IConflictAdapter):
    def fetch(self) -> list[ConflictEvent]:
        return _EVENTS
