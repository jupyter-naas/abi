#!/usr/bin/env python3
"""Simple script to get log level from config.yaml"""
import yaml

try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    level = config.get("logging", {}).get("level", "INFO")
    print(f"LOG_LEVEL={level}")
except:
    print("LOG_LEVEL=INFO")
