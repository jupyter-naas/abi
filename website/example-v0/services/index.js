// API Services
export { generateResponse as generateNaasResponse } from './naasService.js';
export { generateResponse as generateGeminiResponse } from './geminiService.js';

// Re-export the main service for backward compatibility
export { generateResponse } from './naasService.js'; 