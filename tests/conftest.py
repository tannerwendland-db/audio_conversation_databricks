"""Pytest fixtures for Audio Conversation RAG System tests.

This module provides shared fixtures for testing database models,
Databricks client interactions, and sample data creation.
"""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import Settings
from src.models import Base, ProcessingStatus, Recording, Transcript


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create a mock Settings object with test environment variables.

    Returns:
        Settings: A Settings instance configured for testing with
        mock database credentials and Databricks endpoints.
    """
    with patch.dict(
        "os.environ",
        {
            "POSTGRES_HOST": "localhost",
            "POSTGRES_USER": "test_user",
            "POSTGRES_PASSWORD": "test_password",
            "POSTGRES_DB": "test_audio_rag",
            "POSTGRES_PORT": "5432",
            "VOLUME_PATH": "/Volumes/test/default/audio-recordings",
            "DIARIZATION_ENDPOINT": "test-diarization-endpoint",
            "LLM_ENDPOINT": "test-llm-endpoint",
            "EMBEDDING_ENDPOINT": "test-embedding-endpoint",
            "DEBUG": "true",
        },
    ):
        # Clear the lru_cache to ensure fresh settings are created
        from src.config import get_settings

        get_settings.cache_clear()
        settings = Settings()
        yield settings
        # Clear cache again after test session
        get_settings.cache_clear()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key support for SQLite connections.

    SQLite does not enforce foreign keys by default. This event listener
    enables foreign key constraints for all SQLite connections.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create an in-memory SQLite database session for testing.

    Creates all tables from the Base metadata, yields a session for
    test use, and performs cleanup (rollback, close, drop tables)
    after each test function.

    Yields:
        Session: A SQLAlchemy session connected to an in-memory SQLite database.
    """
    # Create in-memory SQLite engine for testing
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session factory and session
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestSessionLocal()

    try:
        yield session
    finally:
        # Cleanup: rollback any uncommitted changes
        session.rollback()
        session.close()
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def mock_databricks_client() -> MagicMock:
    """Create a mock Databricks WorkspaceClient for testing.

    Returns:
        MagicMock: A mock WorkspaceClient with commonly used methods mocked:
            - files.upload: Returns a mock upload response
            - files.download: Returns mock file content
            - serving_endpoints.query: Returns a mock inference response
    """
    mock_client = MagicMock()

    # Mock files.upload method
    mock_upload_response = MagicMock()
    mock_upload_response.path = "/Volumes/test/default/audio-recordings/test-file.wav"
    mock_client.files.upload.return_value = mock_upload_response

    # Mock files.download method
    mock_download_response = MagicMock()
    mock_download_response.read.return_value = b"mock audio content"
    mock_client.files.download.return_value = mock_download_response

    # Mock serving_endpoints.query method
    mock_query_response = MagicMock()
    mock_query_response.predictions = [
        {
            "transcript": "Hello, this is a test transcript.",
            "speakers": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.5, "text": "Hello,"},
                {
                    "speaker": "SPEAKER_01",
                    "start": 2.5,
                    "end": 5.0,
                    "text": "this is a test transcript.",
                },
            ],
        }
    ]
    mock_client.serving_endpoints.query.return_value = mock_query_response

    return mock_client


@pytest.fixture
def sample_recording(db_session: Session) -> Recording:
    """Create and return a sample Recording object for testing.

    Args:
        db_session: The test database session.

    Returns:
        Recording: A persisted Recording instance with realistic test data.
    """
    recording = Recording(
        id=str(uuid4()),
        title="Test Meeting Recording",
        original_filename="test_meeting_2024-01-15.wav",
        volume_path="/Volumes/test/default/audio-recordings/test_meeting_2024-01-15.wav",
        duration_seconds=3600.5,  # 1 hour recording
        processing_status=ProcessingStatus.COMPLETED.value,
        uploaded_by="test_user@example.com",
        created_at=datetime(2024, 1, 15, 10, 30, 0),
    )
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)
    return recording


@pytest.fixture
def sample_transcript(db_session: Session, sample_recording: Recording) -> Transcript:
    """Create and return a sample Transcript linked to a sample_recording.

    Args:
        db_session: The test database session.
        sample_recording: The parent Recording instance.

    Returns:
        Transcript: A persisted Transcript instance with realistic test data
            linked to the sample_recording.
    """
    diarized_content = """[SPEAKER_00 0:00:00]
Hello everyone, welcome to the meeting.

[SPEAKER_01 0:00:05]
Thanks for having us. Let's discuss the project updates.

[SPEAKER_00 0:00:12]
Sure, let me share the progress we've made this week.

[SPEAKER_02 0:00:20]
I have some questions about the timeline."""

    full_text = (
        "Hello everyone, welcome to the meeting. "
        "Thanks for having us. Let's discuss the project updates. "
        "Sure, let me share the progress we've made this week. "
        "I have some questions about the timeline."
    )

    transcript = Transcript(
        id=str(uuid4()),
        recording_id=sample_recording.id,
        full_text=full_text,
        language="en",
        diarized_text=diarized_content,
        summary="Meeting discussing project updates and timeline questions.",
        created_at=datetime(2024, 1, 15, 11, 0, 0),
    )
    db_session.add(transcript)
    db_session.commit()
    db_session.refresh(transcript)
    return transcript


@pytest.fixture
def sample_recording_pending(db_session: Session) -> Recording:
    """Create a sample Recording with PENDING status for testing processing flows.

    Args:
        db_session: The test database session.

    Returns:
        Recording: A persisted Recording instance in PENDING status.
    """
    recording = Recording(
        id=str(uuid4()),
        title="Pending Upload Recording",
        original_filename="new_recording.mp3",
        volume_path="/Volumes/test/default/audio-recordings/new_recording.mp3",
        duration_seconds=None,  # Duration not yet determined
        processing_status=ProcessingStatus.PENDING.value,
        uploaded_by="uploader@example.com",
        created_at=datetime.utcnow(),
    )
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)
    return recording


@pytest.fixture
def mock_databricks_workspace_client_patch():
    """Provide a context manager patch for WorkspaceClient.

    Use this fixture to patch the WorkspaceClient import in modules
    that create their own client instances.

    Yields:
        MagicMock: The patched WorkspaceClient class.
    """
    with patch("databricks.sdk.WorkspaceClient") as mock_workspace_client:
        mock_instance = MagicMock()

        # Configure default mock behaviors
        mock_upload_response = MagicMock()
        mock_upload_response.path = "/Volumes/test/default/audio-recordings/uploaded.wav"
        mock_instance.files.upload.return_value = mock_upload_response

        mock_download_response = MagicMock()
        mock_download_response.read.return_value = b"mock audio bytes"
        mock_instance.files.download.return_value = mock_download_response

        mock_workspace_client.return_value = mock_instance
        yield mock_workspace_client
