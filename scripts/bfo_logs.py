#!/usr/bin/env python3
"""
BFO-Structured Log Stream Parser
Applies Basic Formal Ontology 7 Buckets to distributed system logs
Uses Nexus graph UI color scheme for visual consistency
"""

import re
import sys
from datetime import datetime
from typing import Dict, Optional

# BFO 7 Buckets → Nexus Graph UI Colors
BFO_COLORS = {
    'TIME': '\033[38;2;168;85;247m',        # Purple (Temporal Region) #a855f7
    'SPACE': '\033[38;2;249;115;22m',       # Orange (Site) #f97316
    'PROCESS': '\033[38;2;34;197;94m',      # Green (Process) #22c55e
    'MATERIAL': '\033[38;2;59;130;246m',    # Blue (Material Entity) #3b82f6
    'DATA': '\033[38;2;6;182;212m',         # Cyan (GDC) #06b6d4
    'QUALITIES': '\033[38;2;236;72;153m',   # Pink (Quality) #ec4899
    'DISPOSITION': '\033[38;2;234;179;8m',  # Yellow (Disposition) #eab308
}

# Service colors (from previous implementation)
SERVICE_COLORS = {
    'CORE': '\033[0;34m',   # Blue
    'API': '\033[0;32m',    # Green
    'WEB': '\033[0;33m',    # Yellow
}

# Log level colors
LEVEL_COLORS = {
    'ERROR': '\033[0;31m',  # Red
    'WARN': '\033[0;33m',   # Yellow
    'INFO': '\033[0;32m',   # Green
    'DEBUG': '\033[0;90m',  # Gray
}

RESET = '\033[0m'

# BFO 7 Buckets Classification
class BFOLogEntry:
    def __init__(self, raw_line: str, service: str):
        self.raw = raw_line
        self.service = service
        
        # 1. TIME - Temporal location
        self.time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.duration = self._extract_duration(raw_line)
        
        # 2. SPACE - Spatial/topological location
        self.space = {
            "service": service,  # core/api/web
            "host": self._extract_host(raw_line),
            "endpoint": self._extract_endpoint(raw_line),
        }
        
        # 3. PROCESS - Occurrent (what's happening)
        self.process = self._classify_process(raw_line)
        
        # 4. MATERIAL ENTITIES - Computational resources
        self.material = {
            "pid": self._extract_pid(raw_line),
            "memory": self._extract_memory(raw_line),
            "connections": self._extract_connections(raw_line),
        }
        
        # 5. GENERICALLY DEPENDENT CONTINUANTS - Information/data
        self.data = {
            "request_id": self._extract_request_id(raw_line),
            "payload_size": self._extract_payload_size(raw_line),
        }
        
        # 6. QUALITIES - Properties/attributes
        self.qualities = {
            "level": self._extract_level(raw_line),  # INFO/ERROR/WARN
            "status": self._extract_status(raw_line),  # 200/500/healthy
            "latency": self._extract_latency(raw_line),
        }
        
        # 7. DISPOSITIONS - Capabilities/potentials
        self.dispositions = {
            "state": self._extract_state(raw_line),  # starting/ready/failed
            "intention": self._extract_intention(raw_line),  # retry/shutdown
        }
    
    def _extract_duration(self, line: str) -> Optional[str]:
        match = re.search(r'(\d+\.?\d*)(ms|s|m)', line)
        return match.group(0) if match else None
    
    def _extract_host(self, line: str) -> Optional[str]:
        match = re.search(r'(\d+\.\d+\.\d+\.\d+):(\d+)', line)
        return match.group(0) if match else None
    
    def _extract_endpoint(self, line: str) -> Optional[str]:
        match = re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+([^\s]+)', line)
        return match.group(2) if match else None
    
    def _classify_process(self, line: str) -> str:
        """Classify the occurrent process type"""
        line_lower = line.lower()
        if 'startup' in line_lower or 'starting' in line_lower:
            return 'startup'
        elif 'shutdown' in line_lower or 'stopping' in line_lower:
            return 'shutdown'
        elif 'get' in line_lower or 'post' in line_lower:
            return 'request'
        elif 'error' in line_lower or 'exception' in line_lower:
            return 'error'
        elif 'compiling' in line_lower:
            return 'compilation'
        elif 'websocket' in line_lower or 'ws' in line_lower:
            return 'websocket'
        else:
            return 'operation'
    
    def _extract_pid(self, line: str) -> Optional[str]:
        match = re.search(r'pid[:\s]+(\d+)', line, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_memory(self, line: str) -> Optional[str]:
        match = re.search(r'(\d+\.?\d*)\s*(MB|GB|memory)', line, re.IGNORECASE)
        return match.group(0) if match else None
    
    def _extract_connections(self, line: str) -> Optional[str]:
        match = re.search(r'(\d+)\s*connections?', line, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_request_id(self, line: str) -> Optional[str]:
        match = re.search(r'request[_-]?id[:\s]+([a-zA-Z0-9-]+)', line, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_payload_size(self, line: str) -> Optional[str]:
        match = re.search(r'(\d+)\s*bytes', line, re.IGNORECASE)
        return match.group(0) if match else None
    
    def _extract_level(self, line: str) -> str:
        """Extract log level"""
        if 'ERROR' in line or 'Exception' in line:
            return 'ERROR'
        elif 'WARNING' in line or 'WARN' in line:
            return 'WARN'
        elif 'INFO' in line:
            return 'INFO'
        elif 'DEBUG' in line:
            return 'DEBUG'
        return 'INFO'
    
    def _extract_status(self, line: str) -> Optional[str]:
        match = re.search(r'\b([2-5]\d{2})\b', line)
        if match:
            return match.group(1)
        if 'healthy' in line.lower():
            return 'healthy'
        if 'ready' in line.lower():
            return 'ready'
        return None
    
    def _extract_latency(self, line: str) -> Optional[str]:
        match = re.search(r'(\d+\.?\d*)\s*ms', line)
        return match.group(0) if match else None
    
    def _extract_state(self, line: str) -> Optional[str]:
        """Dispositional state"""
        line_lower = line.lower()
        if 'starting' in line_lower:
            return 'starting'
        elif 'ready' in line_lower or 'complete' in line_lower:
            return 'ready'
        elif 'failed' in line_lower or 'error' in line_lower:
            return 'failed'
        elif 'stopping' in line_lower:
            return 'stopping'
        return None
    
    def _extract_intention(self, line: str) -> Optional[str]:
        """Dispositional intention"""
        line_lower = line.lower()
        if 'retry' in line_lower or 'retrying' in line_lower:
            return 'retry'
        elif 'shutdown' in line_lower or 'cleanup' in line_lower:
            return 'cleanup'
        elif 'waiting' in line_lower:
            return 'waiting'
        return None
    
    def format_compact(self) -> str:
        """Compact format with BFO bucket prefixes and Nexus colors"""
        level_color = LEVEL_COLORS.get(self.qualities['level'], '')
        service_color = SERVICE_COLORS.get(self.service.upper(), '')
        
        # Build BFO prefix string with colors
        bfo_parts = []
        
        # T: TIME (Purple)
        time_str = f"{BFO_COLORS['TIME']}T:{self.time}{RESET}"
        bfo_parts.append(time_str)
        
        # S: SPACE (Orange)
        space_str = f"{BFO_COLORS['SPACE']}S:{service_color}{self.service.upper():4}{RESET}"
        bfo_parts.append(space_str)
        
        # P: PROCESS (Green)
        process_str = f"{BFO_COLORS['PROCESS']}P:{self.process:12}{RESET}"
        bfo_parts.append(process_str)
        
        # M: MATERIAL (Blue) - only if relevant
        if self.material['pid']:
            material_str = f"{BFO_COLORS['MATERIAL']}M:pid{self.material['pid']}{RESET}"
            bfo_parts.append(material_str)
        
        # D: DATA (Cyan) - only if relevant
        if self.data['request_id']:
            data_str = f"{BFO_COLORS['DATA']}D:{self.data['request_id']}{RESET}"
            bfo_parts.append(data_str)
        
        # Q: QUALITIES (Pink)
        quality_parts = []
        if self.qualities['status']:
            quality_parts.append(self.qualities['status'])
        if self.qualities['latency']:
            quality_parts.append(f"({self.qualities['latency']})")
        if quality_parts:
            quality_str = f"{BFO_COLORS['QUALITIES']}Q:{' '.join(quality_parts)}{RESET}"
            bfo_parts.append(quality_str)
        
        # R: DISPOSITION (Yellow) - only if relevant
        disposition_parts = []
        if self.dispositions['state']:
            disposition_parts.append(self.dispositions['state'])
        if self.dispositions['intention']:
            disposition_parts.append(f"→{self.dispositions['intention']}")
        if disposition_parts:
            disp_str = f"{BFO_COLORS['DISPOSITION']}R:{' '.join(disposition_parts)}{RESET}"
            bfo_parts.append(disp_str)
        
        # Assemble final string
        return f"{' '.join(bfo_parts)} {level_color}{self.raw.strip()}{RESET}"
    
    def format_bfo(self) -> str:
        """Full BFO structured format"""
        return f"""
━━━ BFO LOG ENTRY ━━━
{BFO_COLORS['TIME']}TIME:{RESET}       {self.time} {f"(duration: {self.duration})" if self.duration else ""}
{BFO_COLORS['SPACE']}SPACE:{RESET}      {self.space['service']} @ {self.space.get('host', 'local')} → {self.space.get('endpoint', 'n/a')}
{BFO_COLORS['PROCESS']}PROCESS:{RESET}    {self.process} [{self.qualities['level']}]
{BFO_COLORS['MATERIAL']}MATERIAL:{RESET}   PID:{self.material.get('pid', 'n/a')} MEM:{self.material.get('memory', 'n/a')}
{BFO_COLORS['DATA']}DATA:{RESET}       {self.data.get('request_id', 'n/a')} ({self.data.get('payload_size', 'n/a')})
{BFO_COLORS['QUALITIES']}QUALITIES:{RESET}  {self.qualities['status'] or 'n/a'} latency:{self.qualities['latency'] or 'n/a'}
{BFO_COLORS['DISPOSITION']}DISPOSITION:{RESET} {self.dispositions['state'] or 'idle'} {f"→ {self.dispositions['intention']}" if self.dispositions['intention'] else ""}
RAW:        {self.raw.strip()}
"""

def main():
    import sys
    
    service = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    
    try:
        for line in sys.stdin:
            entry = BFOLogEntry(line, service)
            print(entry.format_compact(), flush=True)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
