from __future__ import annotations


class SignalClassifier:
    def classify(self, sentiment_score: float) -> str:
        if sentiment_score >= 0.2:
            return "BUY"
        if sentiment_score <= -0.2:
            return "SELL"
        return "HOLD"

    def sentiment_label(self, sentiment_score: float) -> str:
        if sentiment_score >= 0.2:
            return "Positive"
        if sentiment_score <= -0.2:
            return "Negative"
        return "Neutral"
