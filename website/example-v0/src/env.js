import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';

export const GEMINI_API_KEY = 'AIzaSyDtHcvQLCbRALUNmQR4R9zqdtmAKaWQzj0';

// For backward compatibility
if (ExecutionEnvironment.canUseDOM) {
  window.ENV = {
    GEMINI_API_KEY: GEMINI_API_KEY,
  };
} 