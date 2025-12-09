from collections import deque
from typing import Deque, Dict

EMOTION_KEYS = [
    "Anger",
    "Contempt",
    "Disgust",
    "Fear",
    "Happiness",
    "Neutral",
    "Sadness",
    "Surprise",
]


class StatsAggregator:
    """
    Manages statistics for Age, Gender, and Emotions.
    """

    def __init__(self, maxlen: int = 2000):
        self._ages: Deque[int] = deque(maxlen=maxlen)
        self._age_sum: int = 0

        self._gender_counts: Dict[str, int] = {"Male": 0, "Female": 0}
        self._emotion_counts: Dict[str, int] = {k: 0 for k in EMOTION_KEYS}

        self._total_gender = 0
        self._total_emotions = 0

    def add(self, age: int, gender: str, emotion: str) -> None:
        if len(self._ages) == self._ages.maxlen:
            dropped = self._ages[0]
        else:
            dropped = None

        self._ages.append(age)
        self._age_sum += age
        if dropped is not None:
            self._age_sum -= dropped

        if gender in self._gender_counts:
            self._gender_counts[gender] += 1
            self._total_gender += 1

        if emotion in self._emotion_counts:
            self._emotion_counts[emotion] += 1
            self._total_emotions += 1

    def get_stats(self) -> Dict:
        """Returns the current statistics."""
        avg_age = self._age_sum / len(self._ages) if self._ages else 0.0

        return {
            "age": avg_age,
            "males": self._percentage(self._gender_counts["Male"], self._total_gender),
            "females": self._percentage(
                self._gender_counts["Female"], self._total_gender
            ),
            "emotions": {
                k: self._percentage(v, self._total_emotions)
                for k, v in self._emotion_counts.items()
            },
        }

    @staticmethod
    def _percentage(val: int, total: int) -> float:
        return (val / total * 100.0) if total > 0 else 0.0

    def empty_stats(self) -> Dict:
        return {
            "age": 0.0,
            "males": 0.0,
            "females": 0.0,
            "emotions": {k: 0.0 for k in EMOTION_KEYS},
        }
