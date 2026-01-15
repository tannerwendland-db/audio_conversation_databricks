# Databricks notebook source
# MAGIC %md
# MAGIC # Audio Diarization Notebook
# MAGIC
# MAGIC ## Compute
# MAGIC
# MAGIC Serverless GPU: A10
# MAGIC
# MAGIC ## Before you run
# MAGIC You need a huggingface access token set up in databricks secrets!
# MAGIC
# MAGIC ### Pyannote Usage
# MAGIC You need to agree to the usage policy of Pyannote in Huggingface to get access to the models.
# MAGIC * [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
# MAGIC * [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
# MAGIC * [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
# MAGIC * [pyannote/embedding](https://huggingface.co/pyannote/embedding)
# MAGIC
# MAGIC ## Parameters
# MAGIC
# MAGIC * catalog: Working catalog to use, created if it doesn't exist
# MAGIC * schema: Working schema to use, created if it doesn't exist
# MAGIC * volume: Wolume to use for audio recordings, created in the above catalog & schema
# MAGIC * audio_path: File location in volume to use for testing
# MAGIC * secret_scope: Secret scope for huggingface access token
# MAGIC * secret_name: Secret name for huggingface access token
# MAGIC
# MAGIC ### Optional Parameters
# MAGIC * unity_artifacts: Use UC for experiment artifacts, **only required for serverless only workspaces**, disabled by default.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## PyFunc Model Definition and Registration

# COMMAND ----------

# Install necessary libraries
%pip install numpy==2.2.2 torch==2.8.0 torchvision==0.23.0 ffmpeg-binaries==1.0.1 pyannote.audio==4.0.3 omegaconf openai-whisper librosa hf_transfer
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Widgets

# COMMAND ----------

dbutils.widgets.text("catalog", "tanner_wendland_workspace")
dbutils.widgets.text("schema", "default")
dbutils.widgets.text("volume", "audio_recordings")
dbutils.widgets.text("audio_path", "lemonaid_stand_short.wav")
dbutils.widgets.dropdown("unity_artifacts", "False", ["True", "False"], "Use UC for experiment artifacts?")
dbutils.widgets.text("secret_scope", "tanner")
dbutils.widgets.text("secret_name", "huggingface")
dbutils.widgets.dropdown("scale_to_zero", "False", ["True", "False"], "Enable scale to zero?")
dbutils.widgets.dropdown("workload_size", "Small", ["Small", "Medium"], "Workload size")
dbutils.widgets.dropdown("test_with_recording", "False", ["True", "False"], "Test with recording?")
dbutils.widgets.dropdown("init_catalog", "False", ["True", "False"], "Initialize catalog resources?")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Define the PyFunc Model Class

# COMMAND ----------

import mlflow
from mlflow.pyfunc import PythonModel
from mlflow.models.signature import ModelSignature
from mlflow.types.schema import Schema, ColSpec
import pandas as pd
import numpy as np
import base64
import io


class AudioTranscriptionDiarizationModel(PythonModel):
    """
    MLflow PyFunc model for audio transcription with speaker diarization.
    
    This model accepts audio data as base64-encoded strings and returns
    transcriptions with speaker labels.
    """
    
    def load_context(self, context):
        """
        Load models when the PyFunc is loaded.
        Called once when the model is loaded for serving.
        """
        import whisper
        from pyannote.audio import Pipeline, Model
        import torch
        import os

        # Load Whisper model
        self.whisper_model = whisper.load_model("base")

        # Get HuggingFace token from environment or model config
        # For serving, you'll need to set this as an environment variable
        hf_token = os.environ.get("HF_AUTH_TOKEN", context.model_config.get("hf_auth_token", ""))

        # Set device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Using device: {self.device}")

        # Load speaker diarization pipeline
        try:
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=hf_token
            ).to(self.device)
            print("Speaker diarization pipeline loaded successfully")
        except Exception as e:
            print(f"Error loading speaker diarization pipeline: {str(e)}")
            self.pipeline = None
            raise e

        # Load pyannote embedding model for cross-chunk speaker matching
        try:
            self.embedding_model = Model.from_pretrained(
                "pyannote/embedding",
                token=hf_token
            ).to(self.device)
            print("Speaker embedding model loaded successfully")
        except Exception as e:
            print(f"Error loading speaker embedding model: {str(e)}")
            self.embedding_model = None
            raise e

        # Cosine similarity threshold for speaker matching (0.75 per spec)
        self.similarity_threshold = 0.75

        if not torch.cuda.is_available():
            self.whisper_model.to(torch.device('cpu'))

    def _extract_speaker_embeddings(
        self,
        audio_np: np.ndarray,
        sample_rate: int,
        diarization,
        speaker_order: dict[str, int],
    ) -> dict[str, list[float]]:
        """
        Extract voice embeddings for each speaker based on diarization segments.

        For each speaker, concatenates audio from their segments (>1 second)
        and computes an embedding using the pyannote embedding model.

        Args:
            audio_np: Audio data as numpy array.
            sample_rate: Sample rate of the audio (should be 16000).
            diarization: Pyannote diarization result with speaker_diarization attribute.
            speaker_order: Mapping of speaker IDs to their display labels.

        Returns:
            Dict mapping speaker labels (Interviewer, Respondent, etc.) to 512-dim embeddings.
        """
        import torch
        from pyannote.audio import Inference

        if self.embedding_model is None:
            return {}

        embeddings = {}

        # Group segments by speaker
        speaker_segments: dict[str, list[tuple[float, float]]] = {}
        for turn, speaker in diarization.speaker_diarization:
            segment_duration = turn.end - turn.start
            # Only use segments > 1 second for reliable embeddings (per spec FR-007)
            if segment_duration >= 1.0:
                if speaker not in speaker_segments:
                    speaker_segments[speaker] = []
                speaker_segments[speaker].append((turn.start, turn.end))

        # Extract embedding for each speaker
        for speaker_id, segments in speaker_segments.items():
            # Get the human-readable label for this speaker
            speaker_idx = speaker_order.get(speaker_id, 0)
            if speaker_idx == 0:
                label = "Interviewer"
            elif speaker_idx == 1:
                label = "Respondent"
            else:
                label = f"Respondent{speaker_idx}"

            try:
                # Concatenate audio from all segments for this speaker
                speaker_audio_chunks = []
                for start, end in segments:
                    start_sample = int(start * sample_rate)
                    end_sample = int(end * sample_rate)
                    speaker_audio_chunks.append(audio_np[start_sample:end_sample])

                if not speaker_audio_chunks:
                    continue

                speaker_audio = np.concatenate(speaker_audio_chunks)

                # Create waveform tensor for embedding model
                waveform = torch.from_numpy(speaker_audio).unsqueeze(0).to(self.device)

                # Run embedding inference
                inference = Inference(self.embedding_model, window="whole")
                embedding = inference({"waveform": waveform, "sample_rate": sample_rate})

                # Convert to list for JSON serialization
                embeddings[label] = embedding.tolist()
                del waveform

            except Exception as e:
                print(f"Warning: Failed to extract embedding for {label}: {str(e)}")
                continue

        return embeddings

    def _compute_cosine_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """
        Compute cosine similarity between two embedding vectors.

        Args:
            embedding1: First embedding vector (512 floats).
            embedding2: Second embedding vector (512 floats).

        Returns:
            Cosine similarity score between 0 and 1.
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Handle edge cases
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def _cleanup_gpu_memory(self):
        """Release GPU memory after processing."""
        import torch
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _match_speakers(
        self,
        current_embeddings: dict[str, list[float]],
        reference_embeddings: dict[str, list[float]],
    ) -> tuple[dict[str, str], dict[str, list[float]]]:
        """
        Match speakers from current chunk to reference embeddings using cosine similarity.

        For each speaker in the current chunk:
        - If similarity > threshold with a reference speaker: remap to that label
        - If no match: keep as new speaker, add to updated embeddings

        Args:
            current_embeddings: Embeddings from current chunk (label -> vector).
            reference_embeddings: Reference embeddings from previous chunks (label -> vector).

        Returns:
            Tuple of:
            - label_mapping: Dict mapping current labels to reference labels (or keeping original)
            - updated_embeddings: Reference embeddings updated with any new speakers
        """
        label_mapping: dict[str, str] = {}
        updated_embeddings = dict(reference_embeddings)

        # Track which reference labels have been matched to avoid double-matching
        matched_reference_labels: set[str] = set()

        # Find the next available Respondent number for new speakers
        existing_respondent_nums = []
        for label in reference_embeddings.keys():
            if label == "Respondent":
                existing_respondent_nums.append(1)
            elif label.startswith("Respondent") and label[10:].isdigit():
                existing_respondent_nums.append(int(label[10:]))
        next_respondent_num = max(existing_respondent_nums, default=0) + 1

        for current_label, current_embedding in current_embeddings.items():
            best_match_label = None
            best_similarity = 0.0

            # Find best matching reference speaker
            for ref_label, ref_embedding in reference_embeddings.items():
                if ref_label in matched_reference_labels:
                    continue

                similarity = self._compute_cosine_similarity(
                    current_embedding, ref_embedding
                )

                print(
                    f"Similarity between {current_label} and {ref_label}: {similarity:.4f}"
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_label = ref_label

            # Check if best match exceeds threshold
            if best_match_label and best_similarity >= self.similarity_threshold:
                label_mapping[current_label] = best_match_label
                matched_reference_labels.add(best_match_label)
                print(
                    f"Matched {current_label} -> {best_match_label} "
                    f"(similarity: {best_similarity:.4f})"
                )
            else:
                # No match - this is a new speaker
                # Assign a new sequential label
                if current_label == "Interviewer" and "Interviewer" not in reference_embeddings:
                    # Keep Interviewer label if not already taken
                    new_label = "Interviewer"
                else:
                    new_label = f"Respondent{next_respondent_num}"
                    next_respondent_num += 1

                label_mapping[current_label] = new_label
                updated_embeddings[new_label] = current_embedding
                print(
                    f"New speaker detected: {current_label} -> {new_label} "
                    f"(best similarity: {best_similarity:.4f})"
                )

        return label_mapping, updated_embeddings

    def _decode_audio(self, audio_base64: str) -> tuple:
        """
        Decode base64 audio and convert to numpy array.
        Returns (audio_np, sample_rate)
        """
        import soundfile as sf
        import librosa
        
        # Decode base64 to bytes
        audio_bytes = base64.b64decode(audio_base64)
        audio_buffer = io.BytesIO(audio_bytes)
        
        # Load audio
        audio_np, sample_rate = sf.read(audio_buffer)
        
        # Convert to mono if stereo
        if len(audio_np.shape) > 1:
            audio_np = audio_np.mean(axis=1)
        
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            audio_np = librosa.resample(audio_np, orig_sr=sample_rate, target_sr=16000)
            sample_rate = 16000
        
        audio_np = audio_np.astype(np.float32)
        return audio_np, sample_rate

    def _get_speaker_at_time(self, diarization, timestamp: float) -> str | None:
        """
        Find which speaker is active at a given timestamp.

        Args:
            diarization: Pyannote diarization result
            timestamp: Time in seconds to check

        Returns:
            Speaker label (e.g., 'SPEAKER_00') or None if no speaker at that time
        """
        for turn, speaker in diarization.speaker_diarization:
            if turn.start <= timestamp <= turn.end:
                return speaker

        # If no exact match, find nearest segment
        min_distance = float('inf')
        nearest_speaker = None
        for turn, speaker in diarization.speaker_diarization:
            # Distance to segment (0 if inside)
            if timestamp < turn.start:
                distance = turn.start - timestamp
            elif timestamp > turn.end:
                distance = timestamp - turn.end
            else:
                distance = 0

            if distance < min_distance:
                min_distance = distance
                nearest_speaker = speaker

        return nearest_speaker

    def _group_words_into_turns(
        self,
        speaker_words: list[dict],
        speaker_order: dict[str, int]
    ) -> list[str]:
        """
        Group consecutive same-speaker words into turns with speaker labels.

        Args:
            speaker_words: List of dicts with 'speaker' and 'word' keys
            speaker_order: Mapping of speaker IDs to their order of appearance

        Returns:
            List of formatted turn strings like "Interviewer: Hello how are you"
        """
        if not speaker_words:
            return []

        turns = []
        current_speaker = speaker_words[0]["speaker"]
        current_words = []

        for item in speaker_words:
            if item["speaker"] == current_speaker:
                current_words.append(item["word"])
            else:
                # Speaker changed - save current turn
                if current_words and current_speaker is not None:
                    speaker_idx = speaker_order.get(current_speaker, 0)
                    if speaker_idx == 0:
                        label = "Interviewer"
                    elif speaker_idx == 1:
                        label = "Respondent"
                    else:
                        label = f"Respondent{speaker_idx - 1}"

                    text = "".join(current_words).strip()
                    if text:
                        turns.append(f"{label}: {text}")

                # Start new turn
                current_speaker = item["speaker"]
                current_words = [item["word"]]

        # Don't forget the last turn
        if current_words and current_speaker is not None:
            speaker_idx = speaker_order.get(current_speaker, 0)
            if speaker_idx == 0:
                label = "Interviewer"
            elif speaker_idx == 1:
                label = "Respondent"
            else:
                label = f"Respondent{speaker_idx - 1}"

            text = "".join(current_words).strip()
            if text:
                turns.append(f"{label}: {text}")

        return turns

    def _transcribe_with_speakers(
        self,
        audio_np: np.ndarray,
        sample_rate: int,
        reference_embeddings: dict[str, list[float]] | None = None,
        chunk_index: int = 0,
    ) -> tuple[str, str, dict[str, list[float]]]:
        """
        Transcribe audio and add speaker diarization using word-level alignment.

        Uses Whisper's word-level timestamps to accurately assign words to speakers
        based on when each word was spoken, rather than naive character interpolation.

        For cross-chunk matching:
        - Extracts speaker embeddings from this chunk
        - If reference_embeddings provided, matches speakers to reference set
        - Remaps speaker labels to maintain consistency across chunks

        Args:
            audio_np: Audio data as numpy array.
            sample_rate: Sample rate (should be 16000).
            reference_embeddings: Optional dict of label -> embedding from previous chunks.
            chunk_index: 0-based index of this chunk (for logging).

        Returns:
            Tuple of (dialog, transcription, speaker_embeddings).
        """
        import torch

        # Transcribe with Whisper using word-level timestamps
        result = self.whisper_model.transcribe(audio=audio_np, word_timestamps=True)
        transcription = result["text"]

        if self.pipeline is not None:
            try:
                # Perform speaker diarization
                waveform_tensor = torch.from_numpy(audio_np).unsqueeze(0)
                diarization = self.pipeline({
                    'waveform': waveform_tensor,
                    'sample_rate': sample_rate
                })
                del waveform_tensor

                # Extract words with timing from Whisper result
                words_with_timing = []
                for segment in result.get("segments", []):
                    for word_info in segment.get("words", []):
                        words_with_timing.append({
                            "word": word_info.get("word", ""),
                            "start": word_info.get("start", 0),
                            "end": word_info.get("end", 0)
                        })

                # Build speaker order based on first appearance in diarization
                speaker_order = {}
                speaker_count = 0
                for turn, speaker in diarization.speaker_diarization:
                    if speaker not in speaker_order:
                        speaker_order[speaker] = speaker_count
                        speaker_count += 1

                # Extract speaker embeddings for this chunk
                current_embeddings = self._extract_speaker_embeddings(
                    audio_np, sample_rate, diarization, speaker_order
                )

                print(f"Chunk {chunk_index}: Extracted embeddings for {list(current_embeddings.keys())}")

                # Determine label mapping and final embeddings
                label_mapping: dict[str, str] = {}
                final_embeddings: dict[str, list[float]] = {}

                if reference_embeddings and chunk_index > 0:
                    # Match speakers to reference set and remap labels
                    label_mapping, final_embeddings = self._match_speakers(
                        current_embeddings, reference_embeddings
                    )
                else:
                    # First chunk or no reference - use current labels as-is
                    label_mapping = {label: label for label in current_embeddings.keys()}
                    final_embeddings = current_embeddings

                # Build a mapping from pyannote speaker IDs to final labels
                # speaker_order maps pyannote ID -> index, we need to reverse this
                # and apply the label_mapping
                pyannote_to_final_label: dict[str, str] = {}
                for pyannote_id, idx in speaker_order.items():
                    if idx == 0:
                        original_label = "Interviewer"
                    elif idx == 1:
                        original_label = "Respondent"
                    else:
                        original_label = f"Respondent{idx}"

                    # Apply remapping if available
                    pyannote_to_final_label[pyannote_id] = label_mapping.get(
                        original_label, original_label
                    )

                # Assign each word to a speaker based on word midpoint
                speaker_words = []
                for word_info in words_with_timing:
                    word_midpoint = (word_info["start"] + word_info["end"]) / 2
                    pyannote_speaker = self._get_speaker_at_time(diarization, word_midpoint)
                    speaker_words.append({
                        "speaker": pyannote_speaker,
                        "word": word_info["word"]
                    })

                # Group consecutive same-speaker words into turns using remapped labels
                turns = self._group_words_into_turns_with_mapping(
                    speaker_words, pyannote_to_final_label
                )

                dialog = "\n".join(turns) if turns else transcription
                return (dialog, transcription, final_embeddings)

            except Exception as e:
                raise Exception(f"Error performing speaker diarization: {str(e)}")
        else:
            raise Exception("Speaker diarization pipeline not loaded!")

    def _group_words_into_turns_with_mapping(
        self,
        speaker_words: list[dict],
        pyannote_to_label: dict[str, str],
    ) -> list[str]:
        """
        Group consecutive same-speaker words into turns using a label mapping.

        Args:
            speaker_words: List of dicts with 'speaker' (pyannote ID) and 'word' keys.
            pyannote_to_label: Mapping from pyannote speaker IDs to final labels.

        Returns:
            List of formatted turn strings like "Interviewer: Hello how are you".
        """
        if not speaker_words:
            return []

        turns = []
        current_speaker = speaker_words[0]["speaker"]
        current_words = []

        for item in speaker_words:
            if item["speaker"] == current_speaker:
                current_words.append(item["word"])
            else:
                # Speaker changed - save current turn
                if current_words and current_speaker is not None:
                    label = pyannote_to_label.get(current_speaker, "Unknown")
                    text = "".join(current_words).strip()
                    if text:
                        turns.append(f"{label}: {text}")

                # Start new turn
                current_speaker = item["speaker"]
                current_words = [item["word"]]

        # Don't forget the last turn
        if current_words and current_speaker is not None:
            label = pyannote_to_label.get(current_speaker, "Unknown")
            text = "".join(current_words).strip()
            if text:
                turns.append(f"{label}: {text}")

        return turns
    
    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        """
        Main prediction method called by MLflow serving.

        Args:
            context: MLflow context (contains artifacts, config, etc.)
            model_input: DataFrame with columns:
                - audio_base64 (required): Base64-encoded audio data
                - reference_embeddings (optional): JSON dict of label -> embedding
                - chunk_index (optional): 0-based chunk index for logging

        Returns:
            DataFrame with columns: dialog, transcription, speaker_embeddings, status, error
        """
        import json

        results = []

        for idx, row in model_input.iterrows():
            try:
                audio_base64 = row['audio_base64']

                # Parse optional reference_embeddings (JSON string or None)
                reference_embeddings = None
                if 'reference_embeddings' in row and pd.notna(row['reference_embeddings']):
                    ref_str = row['reference_embeddings']
                    if ref_str and ref_str.strip():
                        try:
                            reference_embeddings = json.loads(ref_str)
                            # Validate embedding dimensions
                            for label, emb in reference_embeddings.items():
                                if len(emb) != 512:
                                    raise ValueError(
                                        f"Reference embedding dimension mismatch for {label}: "
                                        f"expected 512, got {len(emb)}"
                                    )
                        except json.JSONDecodeError as e:
                            raise ValueError(
                                f"Failed to parse reference_embeddings: invalid JSON - {str(e)}"
                            )

                # Parse optional chunk_index (default 0)
                chunk_index = 0
                if 'chunk_index' in row and pd.notna(row['chunk_index']):
                    chunk_index = int(row['chunk_index'])

                # Decode audio
                audio_np, sample_rate = self._decode_audio(audio_base64)

                # Transcribe with speaker diarization and embedding extraction
                dialog, transcription, speaker_embeddings = self._transcribe_with_speakers(
                    audio_np,
                    sample_rate,
                    reference_embeddings=reference_embeddings,
                    chunk_index=chunk_index,
                )

                # Serialize speaker_embeddings to JSON for output
                embeddings_json = json.dumps(speaker_embeddings) if speaker_embeddings else None

                results.append({
                    'dialog': dialog,
                    'transcription': transcription,
                    'speaker_embeddings': embeddings_json,
                    'status': 'success',
                    'error': None
                })
                self._cleanup_gpu_memory()
            except Exception as e:
                results.append({
                    'dialog': None,
                    'transcription': None,
                    'speaker_embeddings': None,
                    'status': 'error',
                    'error': str(e)
                })
                self._cleanup_gpu_memory()

        return pd.DataFrame(results)


# COMMAND ----------

# MAGIC %md
# MAGIC ### Create Input/Output Signature

# COMMAND ----------

# Define the model signature
input_schema = Schema([
    ColSpec("string", "audio_base64"),       # Base64-encoded audio data (required)
    ColSpec("string", "reference_embeddings", required=False),  # JSON dict of label -> embedding (optional)
    ColSpec("integer", "chunk_index", required=False),        # 0-based chunk index (optional, default 0)
])

output_schema = Schema([
    ColSpec("string", "dialog"),
    ColSpec("string", "transcription"),
    ColSpec("string", "speaker_embeddings"),  # JSON dict of label -> embedding
    ColSpec("string", "status"),
    ColSpec("string", "error"),
])

signature = ModelSignature(inputs=input_schema, outputs=output_schema)

# Create an input example (small placeholder - actual audio would be larger)
input_example = pd.DataFrame({
    "audio_base64": ["<base64_encoded_audio_placeholder>"]
})

# COMMAND ----------

# MAGIC %md
# MAGIC ### Log and Register the Model

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import base64
import os
from mlflow import MlflowClient

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
volume = dbutils.widgets.get("volume")
audio_path = dbutils.widgets.get("audio_path")
use_uc_artifacts = dbutils.widgets.get("unity_artifacts").lower() == "true"
secret_scope = dbutils.widgets.get("secret_scope")
secret_name = dbutils.widgets.get("secret_name")
scale_to_zero = dbutils.widgets.get("scale_to_zero").lower() == "true"
workload_size = dbutils.widgets.get("workload_size")
test_with_recording = dbutils.widgets.get("test_with_recording").lower() == "true"
init_catalog = dbutils.widgets.get("init_catalog").lower() == "true"

# In Serverless GPU dbutils is broken due to some stupid regression
def get_huggingface_token() -> str:
    w = WorkspaceClient()
    tf_auth_token_base64 = w.secrets.get_secret(scope=secret_scope, key=secret_name).value
    tf_auth_token = base64.b64decode(tf_auth_token_base64).decode("utf-8")
    return tf_auth_token

if init_catalog:
    spark.sql(f'CREATE CATALOG IF NOT EXISTS {catalog}')
    spark.sql(f'CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}')
    spark.sql(f'CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{volume}')
    if use_uc_artifacts:
        spark.sql(f'CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.artifacts')

# COMMAND ----------

# Define pip requirements with specific versions for reproducibility
pip_requirements = [
    "numpy==2.2.2",
    "torch==2.8.0",
    "torchvision==0.23.0",
    "ffmpeg-binaries==1.0.1",
    "pyannote.audio==4.0.3",
    "openai-whisper",
    "librosa",
    "soundfile",
    "pandas",
    'omegaconf',
]

# Model configuration - HF token will be set via environment variable in serving
model_config = {
    "hf_auth_token": ""  # Will be overridden by HF_AUTH_TOKEN env var in serving
}

os.environ['HF_AUTH_TOKEN'] = get_huggingface_token()
os.environ["MLFLOW_ARTIFACT_UPLOAD_DOWNLOAD_TIMEOUT"] = "1800"

experiment_name = f"/Users/{dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()}/speaker_diarization_model"
artifact_path = f'dbfs:/Volumes/{catalog}/{schema}/artifacts/speaker_diarization'

if mlflow.get_experiment_by_name(experiment_name) is None:
    if use_uc_artifacts:
        mlflow.create_experiment(name=experiment_name, artifact_location=artifact_path)
mlflow.set_experiment(experiment_name)

mlflow_client = MlflowClient()

model_name = f'{catalog}.{schema}.audio_transcription_diarization'

# Log the model
with mlflow.start_run() as run:
    model_info = mlflow.pyfunc.log_model(
        artifact_path=model_name,
        python_model=AudioTranscriptionDiarizationModel(),
        signature=signature,
        input_example=input_example,
        pip_requirements=pip_requirements,
        model_config=model_config,
        registered_model_name=model_name
    )
    mlflow_client.set_registered_model_alias(model_name, "recent", model_info.registered_model_version)
    
    # Log additional parameters
    mlflow.log_params({
        "whisper_model": "base",
        "speaker_diarization_model": "pyannote/speaker-diarization-3.1",
        "target_sample_rate": 16000
    })
    
    run_id = run.info.run_id
    print(f"Model logged with run_id: {run_id}")
    print(f"Model URI: {model_info.model_uri}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Register to Unity Catalog (Optional)

# COMMAND ----------

# Uncomment and modify the following to register to Unity Catalog
# 
# mlflow.set_registry_uri("databricks-uc")
# 
# catalog = "your_catalog"
# schema = "your_schema"
# model_name = "audio_transcription_diarization"
# 
# registered_model = mlflow.register_model(
#     model_uri=model_info.model_uri,
#     name=f"{catalog}.{schema}.{model_name}"
# )
# 
# print(f"Model registered: {registered_model.name} version {registered_model.version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Test the Logged Model Locally

# COMMAND ----------

if test_with_recording:
    # Load the model back for testing
    loaded_model = mlflow.pyfunc.load_model(model_info.model_uri)

    # Test with your existing audio file
    # First, convert your audio to base64
    def file_to_base64(file_path: str) -> str:
        """Convert a file from Spark to base64 string."""
        df = spark.read.format("binaryFile").load(file_path)
        file_bytes = df.first().content
        return base64.b64encode(file_bytes).decode('utf-8')

    # Get the audio as base64
    full_path = f'/Volumes/{catalog}/{schema}/{volume}/{audio_path}'
    audio_base64 = file_to_base64(full_path)

    # Create test input DataFrame
    test_input = pd.DataFrame({
        "audio_base64": [audio_base64]
    })

    # Run prediction
    prediction_result = loaded_model.predict(test_input)
    print("Prediction Result:")
    print(prediction_result)
    print("\nDialog:")
    print(prediction_result['dialog'].iloc[0])

    print("\nTranscription:")
    print(prediction_result['transcription'].iloc[0])

    print("\nSpeaker Embeddings:")
    embeddings_str = prediction_result['speaker_embeddings'].iloc[0]
    if embeddings_str:
        import json
        embeddings = json.loads(embeddings_str)
        for label, emb in embeddings.items():
            print(f"  {label}: [{emb[0]:.4f}, {emb[1]:.4f}, ... ({len(emb)} dims)]")
    else:
        print("  None")

    print("\nStatus:")
    print(prediction_result['status'].iloc[0])
    print("\nError:")
    print(prediction_result['error'].iloc[0])
else:
    print("Skipping model test (test_with_recording=False)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deploying to Databricks Model Serving
# MAGIC
# MAGIC After registering your model to Unity Catalog, you can deploy it to Model Serving:
# MAGIC
# MAGIC 1. Navigate to **Serving** in your Databricks workspace
# MAGIC 2. Click **Create serving endpoint**
# MAGIC 3. Select your registered model from Unity Catalog
# MAGIC 4. Configure compute (GPU recommended for faster inference)
# MAGIC 5. **Important**: Set the `HF_AUTH_TOKEN` environment variable in the endpoint configuration
# MAGIC 6. Deploy and test your endpoint
# MAGIC
# MAGIC ### Example API Call to the Serving Endpoint
# MAGIC
# MAGIC ```python
# MAGIC import requests
# MAGIC import json
# MAGIC import base64
# MAGIC
# MAGIC # Your Databricks workspace URL and token
# MAGIC DATABRICKS_URL = "https://your-workspace.databricks.com"
# MAGIC DATABRICKS_TOKEN = "your-token"
# MAGIC ENDPOINT_NAME = "audio-transcription-diarization-endpoint"
# MAGIC
# MAGIC # Read and encode your audio file
# MAGIC with open("your_audio.wav", "rb") as f:
# MAGIC     audio_base64 = base64.b64encode(f.read()).decode('utf-8')
# MAGIC
# MAGIC # Prepare the request
# MAGIC headers = {
# MAGIC     "Authorization": f"Bearer {DATABRICKS_TOKEN}",
# MAGIC     "Content-Type": "application/json"
# MAGIC }
# MAGIC
# MAGIC data = {
# MAGIC     "dataframe_records": [
# MAGIC         {"audio_base64": audio_base64}
# MAGIC     ]
# MAGIC }
# MAGIC
# MAGIC # Make the request
# MAGIC response = requests.post(
# MAGIC     f"{DATABRICKS_URL}/serving-endpoints/{ENDPOINT_NAME}/invocations",
# MAGIC     headers=headers,
# MAGIC     json=data
# MAGIC )
# MAGIC
# MAGIC print(response.json())
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## End MLflow Run

# COMMAND ----------

mlflow.end_run()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deploy to Model Serving

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput,
    ServedEntityInput,
    ServedModelInputWorkloadType
)
from databricks.sdk.errors import ResourceDoesNotExist
import time

mlflow.set_registry_uri("databricks-uc")

w = WorkspaceClient()
# Configuration
endpoint_name = "audio-transcription-diarization-endpoint"
model_version = w.model_versions.get_by_alias(model_name, "recent").version

# Define the served entity with GPU configuration
served_entities = [
    ServedEntityInput(
        entity_name=model_name,
        entity_version=model_version,
        name="audio-transcription-model",
        workload_type=ServedModelInputWorkloadType.GPU_MEDIUM,
        workload_size=workload_size,
        scale_to_zero_enabled=scale_to_zero,
        environment_vars={
            "HF_AUTH_TOKEN": f"{{{{secrets/{secret_scope}/{secret_name}}}}}"  # Reference to Databricks secret
        }
    )
]

try:
    # Try to update existing endpoint
    print(f"Attempting to update existing endpoint '{endpoint_name}'...")
    w.serving_endpoints.update_config(
        name=endpoint_name,
        served_entities=served_entities
    )
    print(f"Endpoint '{endpoint_name}' configuration updated successfully!")
    
except ResourceDoesNotExist:
    # Create new endpoint if it doesn't exist
    print(f"Endpoint '{endpoint_name}' not found. Creating new endpoint...")
    
    endpoint_config = EndpointCoreConfigInput(
        served_entities=served_entities
    )
    
    w.serving_endpoints.create(
        name=endpoint_name,
        config=endpoint_config
    )
    print(f"Endpoint '{endpoint_name}' creation initiated!")

except Exception as e:
    print(f"Error: {str(e)}")
    raise