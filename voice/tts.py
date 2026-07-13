import pyttsx3


class TTS:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 165)
        self.engine.setProperty("volume", 1.0)
        self._set_french_voice()

    def _set_french_voice(self):
        voices = self.engine.getProperty("voices")
        for voice in voices:
            if "french" in voice.name.lower() or "fr" in voice.id.lower():
                self.engine.setProperty("voice", voice.id)
                break

    def speak(self, text: str):
        self.engine.say(text)
        self.engine.runAndWait()