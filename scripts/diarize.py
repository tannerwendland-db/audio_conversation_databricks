#!/usr/bin/env python3
"""Send a .wav file to Databricks model serving for diarization."""

import argparse
import base64
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient


def read_and_encode_wav(file_path: Path) -> str:
    """Read a .wav file and return its base64-encoded content."""
    with open(file_path, "rb") as f:
        audio_bytes = f.read()
    return base64.b64encode(audio_bytes).decode("utf-8")


def diarize(client: WorkspaceClient, endpoint: str, audio_b64: str) -> str:
    """Send base64-encoded audio to the model serving endpoint and return the diarization text."""
    response = client.serving_endpoints.query(
        name=endpoint,
        inputs={"audio_base64": audio_b64},
    )
    
    # Extract text from response - adjust based on actual model output format
    if hasattr(response, "predictions") and response.predictions:
        return response.predictions[0]
    
    # Fallback for different response formats
    return str(response)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diarize a .wav file using Databricks model serving"
    )
    parser.add_argument(
        "wav_file",
        type=Path,
        help="Path to the local .wav file",
    )
    parser.add_argument(
        "--endpoint",
        "-e",
        default="audio-transcription-diarization-endpoint",
        help="Model serving endpoint name (default: audio-transcription-diarization-endpoint)",
    )
    args = parser.parse_args()

    # Validate file exists
    if not args.wav_file.exists():
        print(f"Error: File not found: {args.wav_file}", file=sys.stderr)
        return 1

    # Validate file extension
    if args.wav_file.suffix.lower() != ".wav":
        print(f"Error: File must be a .wav file, got: {args.wav_file.suffix}", file=sys.stderr)
        return 1

    # Read and encode the audio file
    print(f"Reading and encoding: {args.wav_file}")
    try:
        audio_b64 = read_and_encode_wav(args.wav_file)
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    # Initialize Databricks client (uses standard auth: env vars, .databrickscfg, or OAuth)
    print(f"Connecting to Databricks and calling endpoint: {args.endpoint}")
    try:
        client = WorkspaceClient()
        result = diarize(client, args.endpoint, audio_b64)
    except Exception as e:
        print(f"Error calling model endpoint: {e}", file=sys.stderr)
        return 1

    # Output the diarization result
    print("\n--- Diarization Result ---")
    print(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())

