# ccoli Server API Map

This document describes the current runtime entrypoints and key server modules.

## Runtime Entry

- `server/server.py`
  - Main TCP server process
  - Handles ESP32 packet I/O, STT pipeline, Agent mode orchestration

## CLI Entry

- `ccoli/cli.py`
  - `ccoli start`
  - `ccoli config wifi <WiFi Name> password <password> port <port>`

## Core Modules (`server/src`)

- `server/src/protocol.py`
  - Packet type constants
  - Packet encode/decode helpers
  - CMD/AUDIO_OUT send helpers
- `server/src/connection_manager.py`
  - TCP listen/accept loop
- `server/src/stt_engine.py`
  - Whisper model load + transcription wrapper
- `server/src/audio_processor.py`
  - Audio quality checks, trim, normalization
- `server/src/agent_mode.py`
  - Agent response orchestration (LLM/TTS/services)
- `server/src/robot_mode.py`
  - Robot command parser (currently gated by feature flag)
- `server/src/llm_client.py`
  - Ollama HTTP client wrapper
- `server/src/input_gate.py`
  - Stream gating for turn-based processing
- `server/src/job_queue.py`
  - Queue utility for STT/TTS command flows

## Configuration Sources

- `server/config.yaml` (primary)
- `server/.env` (optional overrides, see `server/env.example`)

## Mode Availability

- Agent mode: enabled
- Robot mode: disabled by default via `features.robot_mode_enabled: false`
