import sounddevice as sd
import soundfile as sf
import numpy as np
import tempfile
import os
from groq import Groq


class STT:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.sample_rate = 16000
        self.silence_threshold = 0.01
        self.silence_duration = 1.2
        self.max_duration = 20

    def record(self) -> np.ndarray:
        block_duration = 0.1
        block_size = int(self.sample_rate * block_duration)
        silence_blocks_needed = int(self.silence_duration / block_duration)
        max_blocks = int(self.max_duration / block_duration)

        buffer = []
        silence_count = 0
        has_spoken = False

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=block_size
        ) as stream:
            for _ in range(max_blocks):
                block, _ = stream.read(block_size)
                buffer.append(block.copy())

                volume = np.abs(block).mean()

                if volume > self.silence_threshold:
                    has_spoken = True
                    silence_count = 0
                elif has_spoken:
                    silence_count += 1

                if has_spoken and silence_count >= silence_blocks_needed:
                    break

        if not buffer:
            return np.array([], dtype="float32")

        return np.concatenate(buffer)

    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) == 0:
            return ""

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            sf.write(path, audio, self.sample_rate)
            with open(path, "rb") as f:
                result = self.client.audio.transcriptions.create(
                    file=f,
                    model="whisper-large-v3-turbo",
                    language="fr"
                )
        finally:
            os.unlink(path)

        return result.text.strip()