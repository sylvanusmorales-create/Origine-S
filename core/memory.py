import json
import os
from datetime import datetime

MEMORY_FILE = "memory.json"

class Memory:
    def __init__(self):
        self.file = MEMORY_FILE
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.file):
            with open(self.file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"interactions": [], "facts": []}

    def _save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add(self, message: str):
        self.data["interactions"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
        self.data["interactions"] = self.data["interactions"][-50:]
        self._save()

    def get_context(self) -> str:
        if not self.data["interactions"]:
            return "Première interaction avec l'utilisateur."
        recent = self.data["interactions"][-10:]
        lines = [f"- {i['timestamp'][:10]} : {i['message'][:100]}" for i in recent]
        return "Interactions récentes :\n" + "\n".join(lines)