## Real-Time Multilingual Voice Appointment Agent

### Overview
This repository implements a **real-time voice agent** for clinical appointment booking, rescheduling, and cancellation.  
The agent supports **English, Hindi, and Tamil**, maintains **session and cross-session context**, and exposes an **outbound campaign mode** for reminders and follow‑ups.

The backend is built to keep **end-to-end response latency under ~450 ms from speech end to first audio**, with explicit timing and logging.

### High-level architecture
- **Frontend**: Next.js (TypeScript) Web UI for capturing microphone audio and playing back TTS.
- **Backend**: FastAPI (`backend/main.py`) providing:
  - `/ws/voice` — bidirectional WebSocket for raw audio, transcription, reasoning traces, and TTS audio.
  - `/campaign/trigger` — trigger outbound reminder/follow‑up flows.
  - `/health` — basic health probe.
- **STT**: Deepgram Nova‑2 via streaming WebSocket (`backend/pipeline/stt.py`).
- **LLM + tools**: Anthropic Claude 3 Haiku, streaming, with function‑calling style tools (`backend/pipeline/llm.py`, `backend/services/tools.py`).
- **TTS**: Deepgram Aura streaming (`backend/pipeline/tts.py`).
- **Scheduling logic**: In‑memory appointment engine (`backend/services/appointment.py`) with:
  - Doctors catalogue.
  - Slot generation and conflict checks.
  - Book, cancel, reschedule, and list‑appointments tools.
- **Memory**: `backend/memory/manager.py`
  - Redis‑backed session history with TTL (`session:{session_id}`).
  - Patient language preference and profile persisted across sessions (`patient:{id}`).
  - In‑memory fallback if Redis is unavailable.
- **Outbound campaigns**: `backend/services/campaign.py` wired to FastAPI via `CampaignManager` and `outbound_callback`, simulating agent‑initiated reminder/follow‑up calls.

### Memory design
- **Session memory (short‑term)**
  - Stored under `session:{session_id}` in Redis (or in‑process fallback).
  - Contains full LLM conversation history: system prompt, user turns, assistant/tool messages.
  - TTL is configurable (default 1 hour).
- **Patient memory (cross‑session)**
  - `MemoryManager` exposes `save_patient_profile` / `get_patient_profile` plus `set_patient_preference` / `get_patient_preference`.
  - Profiles can include: name, phone number, preferred language, preferred doctor, and lightweight history.
  - Language choice is reused across sessions so returning patients hear the agent in their preferred language immediately.

### Appointment & conflict management
Implemented in `backend/services/appointment.py`:

- **Doctors**
  - Static in‑memory list (can be swapped for DB):
    - `d1` — Dr. Sharma (General Physician)
    - `d2` — Dr. Priya (Pediatrician)
    - `d3` — Dr. Karthik (Cardiologist)
  - Tool: `list_doctors` for disambiguation and UI display.

- **Slot generation**
  - `get_available_slots(doctor_id, date)` returns 30‑minute slots between 09:00–17:00 that are not yet booked for that doctor on that date.

- **Booking**
  - `book_appointment(patient_id, doctor_id, date, time, mode="in_person")`
  - Rejects:
    - Past times.
    - Double‑booking on the same doctor/date/time.

- **Finding and rescheduling**
  - `find_patient_appointments(patient_id)` returns upcoming confirmed appointments.
  - `reschedule_appointment(appointment_id, new_date, new_time)`:
    - Validates not in the past.
    - Prevents conflicts on the new slot for the same doctor.

- **Cancellation**
  - `cancel_appointment(appointment_id)` removes the appointment if found.

These functions are all exposed as tools to the LLM in `backend/services/tools.py`, and dispatched from `LLMService.run_tool`.

### Tools & agentic reasoning
The LLM is configured with a multilingual system prompt and a set of tools:

- `list_doctors`
- `get_available_slots`
- `book_appointment`
- `cancel_appointment`
- `find_patient_appointments`
- `reschedule_appointment`

The backend surfaces **reasoning traces** to the frontend:

- When a tool is about to be called: `"Thinking: Calling tool {name}..."`.
- After tool completion: `"Tool Result: {result}"`.

This makes it easy to demonstrate agentic orchestration and conflict handling in a live demo.

### Latency measurement
Latency from **speech end to first audio** is measured inside `llm_callback` in `backend/main.py`:

- When STT emits a final transcript, `wrapped_callback` records a `start_time`.
- `llm_callback`:
  - Starts the LLM stream and pipes chunks into TTS.
  - The TTS handler invokes `on_audio_start` as soon as the **first audio bytes** are ready to send.
  - `on_audio_start` computes:
    - `latency_ms = (now - start_time) * 1000`
  - Sends a JSON metrics event over WebSocket:
    - `{"type": "metrics", "latency": latency_ms, "confidence": stt_confidence}`

You can log and aggregate these metrics to show that typical turns stay under the **450 ms** goal on a reasonably provisioned machine.

### Outbound campaign mode
The outbound path is implemented but intentionally minimal so you can plug in real telephony:

- `CampaignManager` in `backend/services/campaign.py`:
  - `trigger_outbound_call(patient_id, topic)`:
    - Generates a `call_id`.
    - Looks up a small mock `campaign_context` (sample patients with language preference).
    - Builds a `system_msg` instructing the agent to run a reminder/follow‑up flow.
    - Calls a pluggable `callback` with `patient_context`, `topic`, `system_message`, and `call_id`.

- In `backend/main.py`:
  - `outbound_callback` currently logs an informational line for each outbound intent.  
    In a real deployment this is where you would:
    - Create or join a LiveKit/telephony room.
    - Seed the conversation with `system_message` and the patient profile.
    - Reuse the same STT/LLM/TTS loop as inbound calls.
  - `/campaign/trigger` calls into `campaign_manager.trigger_outbound_call`, returning `{"status": "triggered", "patient_id", "call_id"}`.

### Setup
1. **Environment variables**

   Create a `.env` file at the repo root with at least:

   ```bash
   ANTHROPIC_API_KEY=your_anthropic_key
   DEEPGRAM_API_KEY=your_deepgram_key
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```

   > Important: never commit real API keys to version control. Rotate any keys that have been exposed.

2. **Backend**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt   # or your preferred dependency file
   python -m backend.main
   ```

3. **Frontend**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Known limitations
- Appointment storage and patient profiles are currently in‑memory plus Redis, not a relational DB.
- Outbound calling is wired up logically but does not yet hit a real telephony provider; it logs intent via `outbound_callback`.
- Barge‑in / interruption is handled at the session/task level on the backend, with additional UX logic on the frontend.

# Real-Time Multilingual Voice AI Agent

## Overview
A real-time voice AI agent for clinical appointment booking. The agent operates in English, Hindi, and Tamil, maintains contextual memory across sessions, and handles complex scheduling logic autonomously.

## Architecture
- **STT**: Deepgram (Nova-2) [Streaming WebSocket]
- **LLM**: OpenAI (GPT-4o-mini) [Tool Orchestration]
- **TTS**: Cartesia (Sonic) [Ultra-low latency streaming]
- **Backend**: FastAPI (Python)
- **Frontend**: Next.js (TypeScript) + Tailwind CSS
- **Memory**: Redis (Session/Short-term) + Mock Patient DB (Long-term)

## Memory Design
1. **Session Memory**: Managed via Redis. Stores current conversation turn and pending intents.
2. **Context Persistence**: Patient language preference and past interaction history are retrieved on session start and injected into the system prompt.

## Latency Breakdown
- **Target**: < 450ms
- **Optimization**: 
    - Full WebSocket pipeline (no HTTP overhead).
    - Streaming LLM tokens directly to TTS.
    - Nova-2 model for fast speech detection.

## Setup Instructions
1. **Environment Variables**: Create a `.env` file with:
   ```
   DEEPGRAM_API_KEY=your_key
   OPENAI_API_KEY=your_key
   CARTESIA_API_KEY=your_key
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```
2. **Backend**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python -m backend.main
   ```
3. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Known Limitations
- Barge-in handling is currently client-side.
- Outbound calling is simulated via manual trigger endpoint.
