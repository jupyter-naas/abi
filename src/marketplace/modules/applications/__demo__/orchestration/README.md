# Demo Orchestration - Global News Intelligence

## Overview

Strategic global news monitoring system that collects real-time news from major outlets across the United States, France, and United Kingdom. This demo showcases ABI's orchestration capabilities while providing valuable market intelligence and current events awareness.

## Purpose

**GLOBAL NEWS INTELLIGENCE**: This orchestration system provides comprehensive news monitoring across three major markets:

- **United States**: CNN, BBC US, Reuters, AP News, NPR, ABC News, WSJ, Bloomberg, CNBC, Forbes, TechCrunch, Wired, Ars Technica
- **France**: Le Monde, Le Figaro, Libération, France24, RFI, Les Échos, La Tribune, 01net, Numerama  
- **United Kingdom**: BBC, The Guardian, The Telegraph, The Times, Sky News, Financial Times, Reuters UK, The Register

## Architecture

### Code-Data Symmetry
```
Code Structure:                           Data Structure:
src/marketplace/modules/applications/     storage/datastore/marketplace/modules/applications/
__demo__/orchestration/                   __demo__/orchestration/global_news/
├── definitions.py                        ├── us/
├── __init__.py                           │   ├── mainstream/     # CNN, BBC US, Reuters, AP, NPR, ABC
└── README.md                             │   ├── business/       # WSJ, Bloomberg, CNBC, Forbes
                                          │   └── tech/           # TechCrunch, Wired, Ars Technica
                                          ├── france/
                                          │   ├── mainstream/     # Le Monde, Le Figaro, Libération, France24, RFI
                                          │   ├── business/       # Les Échos, La Tribune
                                          │   └── tech/           # 01net, Numerama
                                          └── uk/
                                              ├── mainstream/     # BBC, Guardian, Telegraph, Times, Sky News
                                              ├── business/       # Financial Times, Reuters UK
                                              └── tech/           # The Register
```

### Intelligence Categories

**1. Mainstream News**
- **US**: CNN, BBC US, Reuters, AP News, NPR, ABC News
- **France**: Le Monde, Le Figaro, Libération, France24, RFI
- **UK**: BBC, The Guardian, The Telegraph, The Times, Sky News

**2. Business News**
- **US**: Wall Street Journal, Bloomberg, CNBC, Forbes
- **France**: Les Échos, La Tribune
- **UK**: Financial Times, Reuters UK

**3. Technology News**
- **US**: TechCrunch, Wired, Ars Technica
- **France**: 01net, Numerama
- **UK**: The Register

## Sensors & Monitoring

**30+ Strategic News Sensors** monitoring RSS feeds every 15 minutes:
- **13 US outlets** across mainstream, business, and tech
- **9 French outlets** covering major news categories
- **7 UK outlets** from leading British media

Each sensor processes up to 10 most recent entries to capture breaking news and major stories.

## Data Structure

Each collected news item includes:

```json
{
  "metadata": {
    "collected_at": "2025-09-02T09:45:00",
    "country": "us|france|uk",
    "outlet_type": "mainstream|business|tech", 
    "outlet_name": "CNN",
    "intelligence_type": "global_news"
  },
  "content": {
    "title": "Article title",
    "summary": "Article summary",
    "published": "Publication date",
    "link": "Source URL",
    // ... full RSS entry data
  }
}
```

## Usage

### Start Global News Monitoring
```bash
# Via Docker (recommended) - discovers both ABI and Demo orchestration
make dagster-up

# Or directly
export DAGSTER_HOME=/Users/jrvmac/abi/.dagster
uv run python scripts/generate_dagster_command.py | xargs uv run

# Web interface
open http://localhost:3000
```

### Monitor Global News
```bash
# Check collected news by country
ls storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/us/mainstream/
ls storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/france/business/
ls storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/uk/tech/

# Count news by category
find storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/us -name "*.json" | wc -l
find storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/france -name "*.json" | wc -l
find storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/uk -name "*.json" | wc -l
```

### Search Global News
```bash
# Search for specific topics across all countries
grep -r "inflation" storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/
grep -r "election" storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/
grep -r "AI" storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/

# Search by country
grep -r "Brexit" storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/uk/
grep -r "Macron" storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/france/
grep -r "Trump" storage/datastore/marketplace/modules/applications/__demo__/orchestration/global_news/us/
```

## Strategic Value

**MARKET INTELLIGENCE**:
- Real-time monitoring of global economic and political developments
- Cross-country news analysis and trend identification
- Early detection of market-moving events
- Geopolitical risk assessment

**CURRENT EVENTS AWARENESS**:
- Comprehensive coverage of major news across three key markets
- Business and technology trend monitoring
- Political development tracking
- Cultural and social trend analysis

**COMPETITIVE INTELLIGENCE**:
- Media sentiment analysis across different countries
- Breaking news detection and alert capabilities
- Cross-border story correlation and analysis
- Market reaction prediction based on news flow

## Integration with ABI

This demo orchestration works alongside ABI's strategic AI intelligence:

1. **ABI Module** → AI industry intelligence (labs, models, research, funding)
2. **Demo Module** → Global news intelligence (US, France, UK across mainstream, business, tech)
3. **Combined Intelligence** → Comprehensive market and technology landscape monitoring

## Modular Architecture Benefits

**AUTOMATIC DISCOVERY**: The system automatically discovers and loads both orchestration modules:
- `src/core/modules/abi/orchestration/` - AI industry intelligence
- `src/marketplace/modules/applications/__demo__/orchestration/` - Global news intelligence

**SCALABLE DESIGN**: Any module can add orchestration by creating the standard structure:
```
src/{path}/orchestration/
├── __init__.py
├── definitions.py  
└── README.md
```

**ZERO CONFIGURATION**: New orchestration modules work immediately without system changes.

## Future Enhancements

**SEMANTIC INTEGRATION**:
- Connect news data to ABI semantic pipelines
- Store news intelligence in knowledge graph as RDF triples
- Enable SPARQL queries for complex cross-country news analysis
- Create AI agent workflows for automated news analysis and summarization

**ADVANCED ANALYTICS**:
- Sentiment analysis across countries and outlets
- Topic modeling and trend detection
- Cross-border story correlation
- Real-time news alert system based on keywords and importance

This demo showcases ABI's orchestration capabilities while providing real strategic value through comprehensive global news monitoring across major markets.
