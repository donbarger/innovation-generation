import os
from typing import Optional

from predictionguard import PredictionGuard


def initialize_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> PredictionGuard:
    """
    Initialize and return a PredictionGuard client.

    Priority order for configuration:
    1. Explicit function arguments
    2. Environment variables:
       - PREDICTIONGUARD_API_KEY
       - PREDICTIONGUARD_URL
    """
    api_key = api_key or os.environ.get("PREDICTIONGUARD_API_KEY")
    base_url = base_url or os.environ.get("PREDICTIONGUARD_URL")

    if not api_key:
        raise RuntimeError(
            "Missing Prediction Guard API key. "
            "Set PREDICTIONGUARD_API_KEY or pass api_key to initialize_client()."
        )

    if not base_url:
        raise RuntimeError(
            "Missing Prediction Guard base URL. "
            "Set PREDICTIONGUARD_URL or pass base_url to initialize_client()."
        )

    return PredictionGuard(url=base_url, api_key=api_key)


def simple_chat_completion_example() -> str:
    """
    Run a minimal chat.completions request against the gpt-oss-120b model.

    Returns the model's reply as a string.
    """
    client = initialize_client()

    response = client.chat.completions.create(
        model="gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Answer clearly and concisely."
                ),
            },
            {
                "role": "user",
                "content": "Give me a one-sentence description of Prediction Guard.",
            },
        ],
        temperature=0.2,
        max_completion_tokens=256,
    )

    # The General_Translator app accesses the content like this:
    # response['choices'][0]['message']['content']
    reply = response["choices"][0]["message"]["content"].strip()
    return reply


if __name__ == "__main__":
    # Example usage when running this file directly:
    try:
        answer = simple_chat_completion_example()
        print("Model reply:")
        print(answer)
    except Exception as e:
        print(f"Error calling Prediction Guard: {e}")
 