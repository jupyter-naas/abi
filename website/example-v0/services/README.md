# API Services

This directory contains all external API integrations and services for the application.

## Structure

```
api/
├── services/          # Individual API service modules
│   ├── naasService.js    # Naas AI API integration
│   └── geminiService.js  # Google Gemini API integration
├── index.js          # Centralized exports
└── README.md         # This file
```

## Usage

### Import Services

```javascript
// Import the main service (defaults to Naas)
import { generateResponse } from '../../../api';

// Import specific services
import { generateNaasResponse, generateGeminiResponse } from '../../../api';
```

### Adding New Services

1. Create a new service file in `services/`
2. Export your functions
3. Add exports to `index.js`
4. Update this README

## Services

### Naas Service
- **File**: `services/naasService.js`
- **Purpose**: AI chat completion via Naas platform
- **Main Function**: `generateResponse(message, onChunk, threadId)`

### Gemini Service
- **File**: `services/geminiService.js`
- **Purpose**: Google Gemini AI integration (placeholder)
- **Main Function**: `generateResponse(message, onChunk)`

## Architecture Benefits

- **Separation of Concerns**: API logic separated from UI components
- **Reusability**: Services can be used by any component
- **Maintainability**: All API logic centralized
- **Testability**: Services can be tested independently
- **Scalability**: Easy to add new API integrations 