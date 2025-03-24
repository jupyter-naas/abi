from src.custom.modules.bitcoin.models import BitcoinModel 
from src.custom.modules.bitcoin.pipeline.BitcoinPricePipeline import BitcoinPricePipeline
from typing import Dict, Any

class BitcoinTransactionWorkflow:
    def get_price_analysis(self, days: int = 7) -> Dict[str, Any]:
        """Get Bitcoin price analysis.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict with price analysis
        """
        pipeline = BitcoinPricePipeline()
        return pipeline.run(days=days) 