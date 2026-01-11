#!/usr/bin/env python3
"""
Table Selector - Dynamic table selection for Schema-Aware RAG
Part of Schema-Aware RAG System for Admin Chatbot

This module implements intelligent table selection:
1. Analyzes user questions to identify required data domains
2. Selects only relevant tables to include in the LLM prompt
3. Reduces context size while maintaining accuracy
"""

import re
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import json

# Import schema extractor
from .schema_extractor import schema_extractor, TableInfo


@dataclass
class TableMatch:
    """Represents a matched table with relevance score"""
    table_name: str
    relevance_score: float
    match_reasons: List[str]
    required_joins: List[str]  # Other tables needed for joins


class TableSelector:
    """
    Intelligent table selector for Schema-Aware RAG
    
    Analyzes user questions to determine which tables are relevant,
    reducing the schema context sent to the LLM while ensuring
    all necessary tables for accurate SQL generation are included.
    """
    
    # Keyword to table mappings
    KEYWORD_TABLE_MAP = {
        # Clinical domain
        'disease': ['diagnoses', 'service_summaries', 'claims'],
        'diagnosis': ['diagnoses', 'service_summaries', 'claims'],
        'diagnoses': ['diagnoses', 'service_summaries', 'claims'],
        'patient': ['users', 'claims', 'health_records'],
        'patients': ['users', 'claims', 'health_records'],
        'claim': ['claims', 'service_summaries'],
        'claims': ['claims', 'service_summaries'],
        'service': ['services', 'claims_services', 'claims'],
        'services': ['services', 'claims_services', 'claims'],
        'treatment': ['service_summaries', 'claims', 'services'],
        'health': ['health_records', 'users'],
        'medical': ['diagnoses', 'services', 'claims'],
        'illness': ['diagnoses', 'service_summaries'],
        'condition': ['diagnoses', 'service_summaries'],
        'malaria': ['diagnoses', 'service_summaries', 'claims'],
        'typhoid': ['diagnoses', 'service_summaries', 'claims'],
        'hypertension': ['diagnoses', 'service_summaries', 'claims'],
        
        # Provider domain
        'provider': ['providers', 'claims'],
        'providers': ['providers', 'claims'],
        'hospital': ['providers', 'facility_accreditations'],
        'hospitals': ['providers', 'facility_accreditations'],
        'clinic': ['providers'],
        'clinics': ['providers'],
        'facility': ['providers', 'facility_accreditations'],
        'facilities': ['providers', 'facility_accreditations'],
        'accreditation': ['facility_accreditations', 'providers'],
        'quality': ['quality_assurances', 'providers'],
        
        # Geographic domain
        'state': ['states', 'users'],
        'states': ['states', 'users'],
        'lga': ['lgas', 'users'],
        'location': ['states', 'lgas', 'users'],
        'region': ['states', 'users'],
        'zamfara': ['states', 'users', 'claims'],
        'kogi': ['states', 'users', 'claims'],
        'lagos': ['states', 'users', 'claims'],
        'abuja': ['states', 'users', 'claims'],
        
        # User domain
        'user': ['users'],
        'users': ['users'],
        'enrollee': ['users', 'dependants'],
        'enrollees': ['users', 'dependants'],
        'dependent': ['dependants', 'users'],
        'dependants': ['dependants', 'users'],
        'beneficiary': ['users', 'dependants'],
        
        # Financial domain
        'cost': ['claims', 'transactions'],
        'payment': ['transactions', 'claims'],
        'amount': ['claims', 'transactions'],
        'total': ['claims'],
        'authorization': ['authorization_codes', 'claims'],
        
        # Drug domain
        'drug': ['drugs', 'services'],
        'drugs': ['drugs', 'services'],
        'medication': ['drugs'],
        'prescription': ['drugs', 'claims'],
    }
    
    # Query pattern to domain mappings
    QUERY_PATTERNS = {
        # Clinical patterns
        r'(disease|diagnosis|diagnoses).*(highest|most|top)': {
            'tables': ['diagnoses', 'service_summaries', 'claims'],
            'joins': ['claims_to_diagnosis'],
            'priority': 100
        },
        r'(highest|most|top).*(disease|diagnosis|diagnoses)': {
            'tables': ['diagnoses', 'service_summaries', 'claims'],
            'joins': ['claims_to_diagnosis'],
            'priority': 100
        },
        r'patient.*(disease|diagnosis|diagnoses)': {
            'tables': ['diagnoses', 'service_summaries', 'claims', 'users'],
            'joins': ['claims_to_diagnosis', 'claims_to_user'],
            'priority': 95
        },
        r'(disease|diagnosis).*(state|region)': {
            'tables': ['diagnoses', 'service_summaries', 'claims', 'users', 'states'],
            'joins': ['claims_to_diagnosis', 'claims_to_state'],
            'priority': 100
        },
        r'state.*(disease|diagnosis)': {
            'tables': ['diagnoses', 'service_summaries', 'claims', 'users', 'states'],
            'joins': ['claims_to_diagnosis', 'claims_to_state'],
            'priority': 100
        },
        
        # Provider patterns
        r'provider.*(claim|handled|processed)': {
            'tables': ['providers', 'claims'],
            'joins': ['claims_to_provider'],
            'priority': 90
        },
        r'(hospital|facility).*(claim|patient)': {
            'tables': ['providers', 'claims', 'users'],
            'joins': ['claims_to_provider'],
            'priority': 85
        },
        
        # Service patterns
        r'service.*(used|common|popular)': {
            'tables': ['services', 'claims_services', 'claims'],
            'joins': ['claims_to_services'],
            'priority': 85
        },
        
        # Geographic patterns
        r'(state|region).*(patient|enrollee|user)': {
            'tables': ['states', 'users', 'claims'],
            'joins': ['user_to_state'],
            'priority': 80
        },
        r'(patient|enrollee).*(state|region)': {
            'tables': ['users', 'states', 'claims'],
            'joins': ['user_to_state'],
            'priority': 80
        },
        
        # Count/aggregation patterns
        r'(how many|count|total|number of).*(claim)': {
            'tables': ['claims'],
            'joins': [],
            'priority': 70
        },
        r'(how many|count|total|number of).*(patient|user|enrollee)': {
            'tables': ['users', 'claims'],
            'joins': [],
            'priority': 70
        },
    }
    
    # Required join dependencies (if table A is included, table B must also be included)
    JOIN_DEPENDENCIES = {
        'diagnoses': {
            'requires': ['service_summaries'],
            'join_path': 'claims → service_summaries → diagnoses'
        },
        'service_summaries': {
            'requires': ['claims'],
            'join_path': 'claims → service_summaries'
        },
        'claims_services': {
            'requires': ['claims', 'services'],
            'join_path': 'claims → claims_services → services'
        },
        'states': {
            'requires': ['users'],
            'join_path': 'users → states'
        },
        'lgas': {
            'requires': ['users'],
            'join_path': 'users → lgas'
        },
        'dependants': {
            'requires': ['users'],
            'join_path': 'users → dependants'
        },
        'facility_accreditations': {
            'requires': ['providers'],
            'join_path': 'providers → facility_accreditations'
        },
    }
    
    def __init__(self):
        self._schema_loaded = False
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern matching"""
        return query.lower().strip()
    
    def _extract_keywords(self, query: str) -> Set[str]:
        """Extract relevant keywords from query"""
        normalized = self._normalize_query(query)
        words = set(re.findall(r'\b\w+\b', normalized))
        return words
    
    def _match_patterns(self, query: str) -> List[Dict]:
        """Match query against predefined patterns"""
        normalized = self._normalize_query(query)
        matches = []
        
        for pattern, info in self.QUERY_PATTERNS.items():
            if re.search(pattern, normalized, re.IGNORECASE):
                matches.append({
                    'pattern': pattern,
                    'tables': info['tables'],
                    'joins': info['joins'],
                    'priority': info['priority']
                })
        
        # Sort by priority (highest first)
        matches.sort(key=lambda x: -x['priority'])
        return matches
    
    def _resolve_dependencies(self, tables: Set[str]) -> Set[str]:
        """Add required dependency tables for proper joins"""
        resolved = set(tables)
        changed = True
        
        while changed:
            changed = False
            for table in list(resolved):
                if table in self.JOIN_DEPENDENCIES:
                    for required in self.JOIN_DEPENDENCIES[table]['requires']:
                        if required not in resolved:
                            resolved.add(required)
                            changed = True
        
        return resolved
    
    def select_tables(self, query: str, max_tables: int = 10) -> List[TableMatch]:
        """
        Select relevant tables for a user query
        
        Args:
            query: User's natural language question
            max_tables: Maximum number of tables to return
            
        Returns:
            List of TableMatch objects sorted by relevance
        """
        selected_tables: Dict[str, TableMatch] = {}
        
        # 1. Pattern matching (highest priority)
        pattern_matches = self._match_patterns(query)
        for match in pattern_matches:
            for table in match['tables']:
                if table not in selected_tables:
                    selected_tables[table] = TableMatch(
                        table_name=table,
                        relevance_score=match['priority'],
                        match_reasons=[f"Pattern match: {match['pattern']}"],
                        required_joins=match['joins']
                    )
                else:
                    selected_tables[table].relevance_score = max(
                        selected_tables[table].relevance_score,
                        match['priority']
                    )
                    if f"Pattern match: {match['pattern']}" not in selected_tables[table].match_reasons:
                        selected_tables[table].match_reasons.append(f"Pattern match: {match['pattern']}")
        
        # 2. Keyword matching
        keywords = self._extract_keywords(query)
        for keyword in keywords:
            if keyword in self.KEYWORD_TABLE_MAP:
                tables = self.KEYWORD_TABLE_MAP[keyword]
                for table in tables:
                    if table not in selected_tables:
                        selected_tables[table] = TableMatch(
                            table_name=table,
                            relevance_score=50,  # Base score for keyword match
                            match_reasons=[f"Keyword match: {keyword}"],
                            required_joins=[]
                        )
                    else:
                        if f"Keyword match: {keyword}" not in selected_tables[table].match_reasons:
                            selected_tables[table].match_reasons.append(f"Keyword match: {keyword}")
                            selected_tables[table].relevance_score += 10  # Boost for multiple matches
        
        # 3. Resolve dependencies
        all_tables = self._resolve_dependencies(set(selected_tables.keys()))
        for table in all_tables:
            if table not in selected_tables:
                selected_tables[table] = TableMatch(
                    table_name=table,
                    relevance_score=30,  # Lower score for dependency
                    match_reasons=["Required for join"],
                    required_joins=[]
                )
        
        # 4. Sort by relevance and limit
        sorted_tables = sorted(
            selected_tables.values(),
            key=lambda x: -x.relevance_score
        )
        
        return sorted_tables[:max_tables]
    
    def get_selected_ddl(self, query: str, max_tables: int = 10) -> Tuple[str, List[str]]:
        """
        Get DDL for tables selected based on query
        
        Args:
            query: User's natural language question
            max_tables: Maximum number of tables
            
        Returns:
            Tuple of (combined DDL string, list of table names)
        """
        selected = self.select_tables(query, max_tables)
        table_names = [t.table_name for t in selected]
        
        ddl_parts = []
        for table_match in selected:
            ddl = schema_extractor.get_ddl(table_match.table_name)
            if ddl:
                ddl_parts.append(ddl)
        
        return "\n\n".join(ddl_parts), table_names
    
    def get_relevant_joins(self, query: str) -> List[Dict]:
        """Get canonical join paths relevant to the query"""
        selected = self.select_tables(query)
        
        # Collect all relevant join paths
        relevant_joins = set()
        for table_match in selected:
            for join_name in table_match.required_joins:
                relevant_joins.add(join_name)
        
        # Also add joins based on table combinations
        table_names = {t.table_name for t in selected}
        
        if 'diagnoses' in table_names and 'claims' in table_names:
            relevant_joins.add('claims_to_diagnosis')
        if 'states' in table_names and 'users' in table_names:
            relevant_joins.add('user_to_state')
        if 'states' in table_names and 'claims' in table_names:
            relevant_joins.add('claims_to_state')
        if 'providers' in table_names and 'claims' in table_names:
            relevant_joins.add('claims_to_provider')
        if 'services' in table_names and 'claims' in table_names:
            relevant_joins.add('claims_to_services')
        
        # Get join details from schema extractor
        canonical_joins = schema_extractor.get_canonical_joins()
        return [
            canonical_joins[join_name]
            for join_name in relevant_joins
            if join_name in canonical_joins
        ]
    
    def explain_selection(self, query: str) -> str:
        """Explain why certain tables were selected (for debugging)"""
        selected = self.select_tables(query)
        
        lines = [f"Query: {query}", "", "Selected Tables:"]
        for table in selected:
            lines.append(f"  • {table.table_name} (score: {table.relevance_score})")
            for reason in table.match_reasons:
                lines.append(f"    - {reason}")
        
        lines.append("")
        lines.append("Relevant Joins:")
        for join in self.get_relevant_joins(query):
            lines.append(f"  • {join['path']}")
            lines.append(f"    SQL: {join['sql']}")
        
        return "\n".join(lines)


# Singleton instance
table_selector = TableSelector()


def main():
    """Test table selection with sample queries"""
    test_queries = [
        "show me the disease with highest patients",
        "which disease has the most claims in Kogi state",
        "how many claims were processed last month",
        "top providers by claim count",
        "what services are most commonly used",
        "show patient distribution by state",
    ]
    
    print("=" * 60)
    print("Table Selector Test")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\n{'-' * 60}")
        print(table_selector.explain_selection(query))


if __name__ == "__main__":
    main()

