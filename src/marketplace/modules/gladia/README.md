# Gladia Speech-to-Text Module

## Overview

### Description

The Gladia Module provides comprehensive integration with Gladia's state-of-the-art speech-to-text API platform. This module enables enterprise-grade audio transcription with industry-leading accuracy, speed, and multilingual support.

This module enables:
- **Real-time transcription** with <300ms latency across 100+ languages
- **Asynchronous transcription** with audio intelligence add-ons
- **Advanced audio analysis** including speaker diarization, sentiment analysis, and named entity recognition
- **Enterprise-grade security** with GDPR, HIPAA, and SOC 2 compliance
- **Multilingual support** with native-level accuracy and accent handling

### Requirements

API Key Setup:
1. Obtain an API key from [Gladia Platform](https://app.gladia.io/)
2. Configure your `GLADIA_API_KEY` in your .env file

### TL;DR

To get started with the Gladia module:

1. Obtain an API key from [Gladia Platform](https://app.gladia.io/)
2. Configure your `GLADIA_API_KEY` in your .env file

Start chatting using this command:
```bash
make chat agent=GladiaAgent
```

### Structure

```
src/marketplace/modules/gladia/
├── agents/                         
│   ├── GladiaAgent_test.py               
│   └── GladiaAgent.py          
├── integrations/                    
│   ├── GladiaIntegration_test.py          
│   └── GladiaIntegration.py     
├── models/                         
│   ├── solaria.py                
│   └── whisper_zero.py                
├── ontologies/                     
│   ├── GladiaOntology.ttl            
│   └── GladiaSparqlQueries.py           
├── pipelines/                     
│   ├── AudioTranscriptionPipeline_test.py          
│   └── AudioTranscriptionPipeline.py           
├── workflows/   
│   ├── RealTimeTranscriptionWorkflow_test.py                      
│   ├── RealTimeTranscriptionWorkflow.py      
│   ├── AsyncTranscriptionWorkflow_test.py      
│   └── AsyncTranscriptionWorkflow.py      
└── README.md                       
```

## Core Components

### Agents

#### Gladia Agent
Intelligent speech-to-text agent that provides real-time and asynchronous audio transcription with advanced analysis capabilities.

**Capabilities:**
- Real-time audio transcription with sub-300ms latency
- Asynchronous transcription with detailed metadata
- Speaker diarization and sentiment analysis
- Named entity recognition and summarization
- Multilingual support across 100+ languages
- Custom vocabulary and domain-specific models

**Command:**
```bash
make chat agent=GladiaAgent
```

**Use Cases:**
- Customer support call transcription and analysis
- Meeting transcription with speaker identification
- Content creation with automatic subtitles
- Voice agent development with real-time processing
- Compliance recording analysis

#### Testing
```bash
uv run python -m pytest src/marketplace/modules/gladia/agents/GladiaAgent_test.py
```

### Integrations

#### Gladia Integration
Core integration class providing comprehensive access to Gladia's speech-to-text API platform.

**Functions:**
- `transcribe_audio_async()`: Asynchronous audio transcription with full feature set
- `transcribe_audio_realtime()`: Real-time streaming transcription
- `get_transcription_status()`: Check transcription job status
- `get_transcription_result()`: Retrieve completed transcription
- `list_supported_languages()`: Get available languages and models
- `configure_audio_intelligence()`: Enable advanced analysis features

##### Configuration

```python
from src.marketplace.modules.gladia.integrations.GladiaIntegration import (
    GladiaIntegration,
    GladiaIntegrationConfiguration
)

# Create configuration
config = GladiaIntegrationConfiguration(
    api_key="your_gladia_api_key_here",
    base_url="https://api.gladia.io",
    enable_diarization=True,
    enable_sentiment_analysis=True,
    language_preference="auto-detect"
)

# Initialize integration
integration = GladiaIntegration(config)
```

#### Run
```bash
# Transcribe audio file
uv run python -c "
from src.marketplace.modules.gladia.integrations.GladiaIntegration import *
config = GladiaIntegrationConfiguration(api_key='your_key')
integration = GladiaIntegration(config)
result = integration.transcribe_audio_async('path/to/audio.wav')
print(result)
"
```

#### Testing
```bash
uv run python -m pytest src/marketplace/modules/gladia/integrations/GladiaIntegration_test.py
```

### Models

#### Solaria Model
Gladia's flagship universal speech-to-text model with industry-leading accuracy across 100+ languages.

**Features:**
- Real-time processing with <300ms latency
- Native-level accuracy across all supported languages
- Advanced handling of accents and dialects
- Code-switching detection and processing
- Optimized for production environments

#### Whisper-Zero Model
Open-weight transcription model with near-zero hallucinations for production use.

**Features:**
- Reduced hallucination rates for critical applications
- Open-weight architecture for transparency
- Optimized for accuracy over speed
- Ideal for compliance and legal applications

### Ontologies

#### Gladia Ontology
RDF ontology defining audio transcription entities, relationships, and metadata structures for knowledge graph integration.

**Core Entities:**
- `AudioFile`: Source audio file with metadata
- `TranscriptionJob`: Processing job with status and configuration
- `Transcript`: Text output with timing and confidence scores
- `Speaker`: Identified speaker with segments
- `AudioSegment`: Time-bounded audio portion with analysis

#### Gladia SPARQL Queries
Pre-defined SPARQL queries for common transcription analysis tasks.

### Pipelines

#### Audio Transcription Pipeline
Comprehensive pipeline for processing audio files through Gladia's transcription engine with metadata extraction and storage.

**Process:**
1. Audio file validation and preprocessing
2. Transcription job submission to Gladia API
3. Status monitoring and result retrieval
4. Metadata extraction and enrichment
5. Knowledge graph storage in RDF format

### Workflows

#### Real-Time Transcription Workflow
WebSocket-based workflow for live audio streaming and real-time transcription processing.

**Features:**
- Live audio stream handling
- Real-time text output with timing
- Speaker change detection
- Confidence scoring and quality metrics

#### Async Transcription Workflow
Batch processing workflow for high-volume audio transcription with advanced analysis features.

**Features:**
- Bulk audio file processing
- Advanced audio intelligence features
- Metadata enrichment and analysis
- Export to multiple formats (JSON, SRT, VTT)

## Performance Specifications

### Latency Benchmarks
- **Real-time transcription**: <300ms first response
- **Streaming processing**: Sub-second continuous updates
- **Batch processing**: Optimized for throughput over latency

### Accuracy Metrics
- **General speech**: 95%+ accuracy across major languages
- **Technical content**: 90%+ with custom vocabulary
- **Accented speech**: Native-level performance
- **Multi-speaker**: 90%+ speaker identification accuracy

### Language Support
**Tier 1 Languages** (Premium accuracy):
- English, Spanish, French, German, Italian, Portuguese, Dutch, Russian, Japanese, Chinese (Mandarin), Korean, Arabic

**Tier 2 Languages** (High accuracy):
- 88+ additional languages with regional accent support

### Enterprise Features

#### Security & Compliance
- **GDPR Compliant**: EU data residency and privacy controls
- **HIPAA Compliant**: Healthcare data protection standards
- **SOC 2 Type 2**: Enterprise security certification
- **ISO 27001**: Information security management

#### Scalability
- **Concurrent streams**: Unlimited real-time sessions
- **Batch processing**: High-throughput async processing
- **Global infrastructure**: Multi-region deployment options
- **SLA guarantees**: 99.9% uptime commitment

## Dependencies

### Python Libraries
- `abi.integration`: Base integration framework
- `abi.services.agent`: Agent framework
- `langchain_core`: Tool integration for AI agents
- `fastapi`: API router for agent endpoints
- `pydantic`: Data validation and serialization
- `requests`: HTTP client for API calls
- `websockets`: Real-time streaming support
- `asyncio`: Asynchronous processing
- `json`: Response parsing
- `base64`: Audio encoding utilities

### Audio Processing
- `librosa`: Audio analysis and preprocessing
- `soundfile`: Audio file I/O operations
- `numpy`: Numerical audio processing
- `scipy`: Signal processing utilities

### External Services
- **Gladia API**: Core transcription service
- **WebSocket endpoints**: Real-time streaming
- **Object storage**: Audio file management (optional)

## Advanced Use Cases

### Customer Experience Enhancement
```python
# Real-time call center transcription
workflow = RealTimeTranscriptionWorkflow(
    enable_sentiment_analysis=True,
    enable_intent_detection=True,
    custom_vocabulary=["product_name", "service_term"]
)
```

### Meeting Intelligence
```python
# Multi-speaker meeting analysis
pipeline = AudioTranscriptionPipeline(
    enable_diarization=True,
    enable_summarization=True,
    speaker_labels=True,
    action_item_extraction=True
)
```

### Content Production
```python
# Media transcription with subtitles
result = integration.transcribe_audio_async(
    audio_url="video_file.mp4",
    output_format="srt",
    enable_timestamps=True,
    enable_chapters=True
)
```

### Voice Agent Development
```python
# Real-time voice bot integration
agent = GladiaAgent(
    streaming_mode=True,
    response_latency="minimal",
    intent_detection=True,
    conversation_context=True
)
```

## Getting Started Examples

### Basic Transcription
```python
from src.marketplace.modules.gladia.integrations.GladiaIntegration import GladiaIntegration, GladiaIntegrationConfiguration

# Configure integration
config = GladiaIntegrationConfiguration(
    api_key="your_api_key",
    language="en"
)
integration = GladiaIntegration(config)

# Transcribe audio
result = integration.transcribe_audio_async("audio_file.wav")
print(result["transcription"]["full_transcript"])
```

### Real-time Streaming
```python
from src.marketplace.modules.gladia.workflows.RealTimeTranscriptionWorkflow import RealTimeTranscriptionWorkflow

# Start real-time session
workflow = RealTimeTranscriptionWorkflow(
    api_key="your_api_key",
    language="auto"
)

# Stream audio and get real-time text
async for transcript in workflow.stream_transcription(audio_stream):
    print(f"Speaker {transcript.speaker}: {transcript.text}")
```

### Advanced Analysis
```python
# Enable all audio intelligence features
config = GladiaIntegrationConfiguration(
    api_key="your_api_key",
    enable_diarization=True,
    enable_sentiment_analysis=True,
    enable_named_entity_recognition=True,
    enable_summarization=True,
    custom_vocabulary=["technical", "terms"]
)

integration = GladiaIntegration(config)
result = integration.transcribe_audio_async("meeting.mp3")

# Access advanced features
print("Speakers:", result["speakers"])
print("Sentiment:", result["sentiment_analysis"])
print("Entities:", result["named_entities"])
print("Summary:", result["summary"])
```

## Support & Resources

- **API Documentation**: [Gladia Developer Docs](https://docs.gladia.io)
- **Playground**: [Interactive API Testing](https://app.gladia.io/playground)
- **Community**: [Discord Server](https://discord.gg/gladia)
- **Status Page**: [Service Status](https://status.gladia.io)
- **Support**: [Contact Support](mailto:support@gladia.io)
