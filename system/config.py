"""Centralized configuration loader for Tokymon."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIGS_DIR = BASE_DIR / "configs"
MAC_ROOT = Path("/Users/ankursharma/Documents/Dev Projects/tokymon")
PI_ROOT = Path("/home/ankursharma/Projects/tokymon")


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            base[key] = _deep_merge(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_env_files() -> None:
    for candidate in (BASE_DIR / ".env", BASE_DIR / ".env.local"):
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=True)


def _detect_root_path() -> Path:
    forced = os.getenv("TOKY_ROOT")
    if forced:
        return Path(forced).resolve()
    if os.getenv("TOKY_ENV") == "dev":
        return MAC_ROOT
    system_name = os.uname().sysname.lower()
    if system_name == "linux":
        return PI_ROOT
    return MAC_ROOT


def _build_config() -> Dict[str, Any]:
    _load_env_files()
    config: Dict[str, Any] = {
        "pinmap": _load_yaml(CONFIGS_DIR / "pinmap_pi.yaml"),
        "services": _load_yaml(CONFIGS_DIR / "services.yaml"),
        "env": {},
    }

    env_name = os.getenv("TOKY_ENV")
    if env_name:
        override_path = CONFIGS_DIR / f"env.{env_name}.yaml"
        if override_path.exists():
            config["services"] = _deep_merge(
                dict(config["services"]), _load_yaml(override_path)
            )
        config["env"]["active"] = env_name

    config["env"].update(
        {
            "MQTT_BROKER_HOST": os.getenv("MQTT_BROKER_HOST", "localhost"),
            "MQTT_BROKER_PORT": int(os.getenv("MQTT_BROKER_PORT", "1883")),
        }
    )
    root_path = _detect_root_path()
    config["paths"] = {
        "pi_root": str(PI_ROOT),
        "mac_root": str(MAC_ROOT),
    }
    config["runtime"] = {"root_path": str(root_path)}
    return config


CONFIG = _build_config()
