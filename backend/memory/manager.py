import redis
import json
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self):
        self._memory_fallback = {
            "sessions": {},
            "patients": {},
        }
        try:
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=0,
                decode_responses=True,
                socket_connect_timeout=2
            )
            self.redis_client.ping()
            self._use_redis = True
            logger.info("Connected to Redis")
        except Exception as e:
            self._use_redis = False
            logger.warning(f"Redis not available, using in-memory fallback: {e}")

    def save_session(self, session_id, history, ttl=3600):
        if self._use_redis:
            key = f"session:{session_id}"
            try:
                self.redis_client.set(key, json.dumps(history), ex=ttl)
                return
            except Exception as e:
                logger.error(f"Redis save error: {e}")
        # Fallback: store in-memory with simple namespacing
        self._memory_fallback["sessions"][session_id] = history

    def get_session(self, session_id):
        if self._use_redis:
            try:
                data = self.redis_client.get(f"session:{session_id}")
                return json.loads(data) if data else []
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        return self._memory_fallback["sessions"].get(session_id, [])

    def set_patient_preference(self, patient_id, language):
        """
        Persist the patient's preferred language across sessions.
        """
        if self._use_redis:
            try:
                self.redis_client.hset(f"patient:{patient_id}", "language", language)
                return
            except Exception as e:
                logger.error(f"Redis hset error: {e}")
        patient = self._memory_fallback["patients"].setdefault(patient_id, {})
        patient["language"] = language

    def get_patient_preference(self, patient_id):
        if self._use_redis:
            try:
                val = self.redis_client.hget(f"patient:{patient_id}", "language")
                if val: return val
            except Exception as e:
                logger.error(f"Redis hget error: {e}")
        patient = self._memory_fallback["patients"].get(patient_id, {})
        # Default to English if nothing is stored
        return patient.get("language", "en")
        
    def add_to_history(self, session_id, role, content):
        history = self.get_session(session_id)
        history.append({"role": role, "content": content})
        self.save_session(session_id, history)
        return history

    def save_patient_profile(self, patient_id, profile: dict):
        """
        Store or update a patient profile (name, phone, preferences, etc.).
        Uses Redis hash when available, otherwise in-memory fallback.
        """
        if self._use_redis:
            try:
                key = f"patient:{patient_id}"
                # Flatten JSON as a string field for flexibility
                self.redis_client.hset(key, "profile", json.dumps(profile))
                return
            except Exception as e:
                logger.error(f"Redis patient save error: {e}")
        self._memory_fallback["patients"][patient_id] = profile

    def get_patient_profile(self, patient_id) -> dict:
        """
        Retrieve a stored patient profile, or {} if none exists.
        """
        if self._use_redis:
            try:
                key = f"patient:{patient_id}"
                raw = self.redis_client.hget(key, "profile")
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.error(f"Redis patient get error: {e}")
        return self._memory_fallback["patients"].get(patient_id, {})
