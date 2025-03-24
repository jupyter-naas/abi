from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from src.marketplace.modules.trading.integrations.YahooFinanceIntegration import YahooFinanceIntegration, YahooFinanceIntegrationConfiguration
from abi.utils.Graph import ABIGraph, ABI, BFO, CCO
from rdflib import Graph, Literal, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, XSD
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src import secret, config
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import pandas as pd
from typing import List, Optional, Dict
from datetime import datetime
import re
from pydantic import Field
from abi import logger
import io

@dataclass
class YahooFinanceEarningsCallPipelineConfiguration(PipelineConfiguration):
    """Configuration for YahooFinanceEarningsCallPipeline.
    
    Attributes:
        integration (YahooFinanceIntegration): The Yahoo Finance integration instance to use
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use. Defaults to "stocktrading"
    """
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "trading"

class YahooFinanceEarningsCallPipelineParameters(PipelineParameters):
    """Parameters for YahooFinanceEarningsCallPipeline execution.
    
    Attributes:
        data (List[Dict]): Dictionary containing earnings call data
    """
    data: bytes = Field(..., description="Dictionary containing earnings call data")

class YahooFinanceEarningsCallPipeline(Pipeline):
    """Pipeline for mapping Yahoo Finance earnings call data to the ontology.
    
    This pipeline extracts earnings call data from Yahoo Finance and maps it to
    the trading ontology, creating relationships between companies, stocks,
    earnings calls, and financial metrics.
    """
    __configuration: YahooFinanceEarningsCallPipelineConfiguration
    
    def __init__(self, configuration: YahooFinanceEarningsCallPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: YahooFinanceEarningsCallPipelineParameters) -> Graph:  
        # Initialize graph from existing store if available
        try:    
            existing_graph = self.__configuration.ontology_store.get(self.__configuration.ontology_store_name)
            graph = ABIGraph()
            for triple in existing_graph:
                graph.add(triple)
            logger.info(f"Retrieved existing graph from {self.__configuration.ontology_store_name} with {len(existing_graph)} triples")
        except Exception as e:
            logger.info(f"Error getting graph: {e}")
            graph = ABIGraph()
            logger.info(f"Created new graph for {self.__configuration.ontology_store_name}")

        # Process each earnings call entry
        df = pd.read_csv(io.BytesIO(parameters.data))
        for _, row in df.iterrows():
            if pd.isna(row['Symbol']) or pd.isna(row['Earnings Date']):
                continue
                
            symbol = row['Symbol']
            company = row['Company']
            earnings_date_str = row['Earnings Date']
            eps_estimate = row['EPS Estimate'] if not pd.isna(row['EPS Estimate']) else None
            reported_eps = row['Reported EPS'] if not pd.isna(row['Reported EPS']) else None
            surprise_pct = row['Surprise (%)'] if not pd.isna(row['Surprise (%)']) else None
            
            # Parse the date and time
            date_str = earnings_date_str.split('at')[0].strip()
            time_str = earnings_date_str.split('at')[1].strip()
            try:
                call_date = datetime.strptime(date_str, "%B %d, %Y").strftime("%Y-%m-%d")
                logger.debug(f"Processing earnings call for {company} on {call_date}")
                
                # Create organization with legal name and ticker
                company_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=f"company-{symbol}",
                    label=company,
                    is_a=CCO.ont00000443  # Commercial Organization
                )
                
                # Add legal name
                legal_name_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=f"legal-name-{symbol}",
                    label=company,
                    is_a=CCO.ont00001331  # Legal Name
                )
                graph.add((company_uri, ABI.hasLegalName, legal_name_uri))
                graph.add((legal_name_uri, ABI.isLegalNameOf, company_uri))
                
                # Add ticker symbol
                ticker_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=f"ticker-{symbol}",
                    label=symbol,
                    is_a=ABI.Ticker
                )
                graph.add((company_uri, ABI.hasTickerSymbol, ticker_uri))
                graph.add((ticker_uri, ABI.isTickerSymbolOf, company_uri))
                
                # Create earnings call entity
                earnings_call_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=f"earnings-call-{symbol}-{call_date.replace('-', '')}",
                    label=f"{company} Earnings Call on {call_date}",
                    is_a=ABI.EarningsCall
                )
                
                # Link earnings call to company
                graph.add((earnings_call_uri, ABI.hostedByOrganization, company_uri))
                graph.add((company_uri, ABI.hostsEarningsCall, earnings_call_uri))
                
                # Add temporal information
                try:
                    logger.debug(f"Processing earnings call for {company} on {call_date} at {time_str}")
                    call_datetime = datetime.strptime(f"{call_date} {time_str}", "%Y-%m-%d %I %p %Z")
                except ValueError:
                    call_datetime = datetime.strptime(f"{call_date}", "%Y-%m-%d")
                
                temporal_region_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=f"time-{int(call_datetime.timestamp())}",
                    label=int(call_datetime.timestamp()),
                    is_a=CCO.ont00001116,  # TemporalRegion
                    alt_label=earnings_date_str
                )
                graph.add((earnings_call_uri, ABI.occursAtTime, temporal_region_uri))
                
                # Add EPS data if available
                if eps_estimate is not None or reported_eps is not None or surprise_pct is not None:
                    eps_uri = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=f"eps-{symbol}-{call_date.replace('-', '')}",
                        label=f"{company} EPS Data for {call_date}",
                        is_a=ABI.EarningsPerShare
                    )
                    
                    # Link EPS data to earnings call
                    graph.add((earnings_call_uri, ABI.hasEarningsPerShareData, eps_uri))
                    graph.add((eps_uri, ABI.isEarningsPerShareDataFor, earnings_call_uri))
                    
                    # Add EPS values as data properties
                    if eps_estimate is not None and eps_estimate != '-':
                        graph.add((eps_uri, ABI.estimated_earnings_per_share, Literal(float(eps_estimate), datatype=XSD.decimal)))
                    
                    if reported_eps is not None and reported_eps != '-':
                        graph.add((eps_uri, ABI.reported_earnings_per_share, Literal(float(reported_eps), datatype=XSD.decimal)))
                    
                    if surprise_pct is not None and surprise_pct != '-':
                        if isinstance(surprise_pct, str) and surprise_pct.startswith('+'):
                            surprise_pct = surprise_pct[1:]
                        graph.add((eps_uri, ABI.earnings_per_share_surprise_percentage, Literal(float(surprise_pct), datatype=XSD.decimal)))
            
            except Exception as e:
                logger.error(f"Error processing row: {e}")
        
        # Store the graph
        logger.info(f"Storing graph with {len(graph)} triples to {self.__configuration.ontology_store_name}")
        self.__configuration.ontology_store.store(self.__configuration.ontology_store_name, graph)
        
        return graph
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[StructuredTool]: List containing the pipeline tool
        """
        return [
                StructuredTool(
                name="yahoo_finance_earnings_call_pipeline",
                description="Maps Yahoo Finance earnings call data to the ontology",
                func=lambda **kwargs: self.run(YahooFinanceEarningsCallPipelineParameters(**kwargs)),
                args_schema=YahooFinanceEarningsCallPipelineParameters
            )
        ]

    def as_api(self) -> None:
        pass