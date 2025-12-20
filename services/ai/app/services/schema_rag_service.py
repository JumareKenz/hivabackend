"""
Schema-RAG Service - Maps user entities to database columns using Vector RAG
Uses ChromaDB + SentenceTransformers for semantic entity matching
"""
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import re
from sentence_transformers import SentenceTransformer
from chromadb import Client, Collection
from chromadb.config import Settings
from app.services.database_service import database_service
from app.services.schema_loader import schema_loader
try:
    from app.core.config import settings
except ImportError:
    # Fallback for different project structure
    class Settings:
        EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
    settings = Settings()


class SchemaRAGService:
    """
    Schema-RAG service that maps user entities to database columns.
    Uses vector embeddings (ChromaDB + SentenceTransformers) for semantic matching.
    """
    
    def __init__(self):
        self._entity_cache: Dict[str, Dict[str, Any]] = {}
        self._column_value_index: Dict[str, List[str]] = {}  # column_name -> [values]
        self._initialized = False
        
        # Vector RAG components
        self._embedding_model: Optional[SentenceTransformer] = None
        self._chroma_client: Optional[Client] = None
        self._entity_collection: Optional[Collection] = None
        
        # Embedding model (use same as FAQ RAG for consistency)
        self.embedding_model_name = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    
    async def initialize(self, force: bool = False):
        """Initialize Schema-RAG by building entity mappings and vector index (non-blocking)"""
        if self._initialized and not force:
            return
        
        # Use lazy initialization - only initialize components when needed
        try:
            # Initialize embedding model (can be slow, but needed for vector search)
            if not self._embedding_model:
                self._embedding_model = SentenceTransformer(self.embedding_model_name)
            
            # Initialize ChromaDB (fast)
            if not self._chroma_client:
                self._chroma_client = Client(Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                ))
            
            # Get or create collection for entity mappings
            if not self._entity_collection:
                try:
                    self._entity_collection = self._chroma_client.get_or_create_collection(
                        name="schema_entity_mappings",
                        metadata={"description": "Entity mappings for Schema-RAG"}
                    )
                except:
                    # If collection exists, get it
                    self._entity_collection = self._chroma_client.get_collection("schema_entity_mappings")
            
            # Only build mappings if not already done (or if forced)
            if not self._initialized or force:
                # Get comprehensive schema
                comprehensive_schema = await schema_loader.load_comprehensive_schema()
                table_schemas = comprehensive_schema.get('table_schemas', {})
                
                # Build entity mappings for key columns (dictionary-based, fast)
                await self._build_entity_mappings(table_schemas)
                
                # Build vector index (can be slow, but only once)
                # Skip if collection already has data
                if self._entity_collection.count() == 0 or force:
                    await self._build_vector_index()
            
            self._initialized = True
        except Exception as e:
            # If initialization fails, fall back to dictionary-only mode
            print(f"⚠️ Vector RAG initialization failed, using dictionary mode: {e}")
            # Still mark as initialized to avoid repeated failures
            self._initialized = True
    
    async def _build_entity_mappings(self, table_schemas: Dict[str, Dict]):
        """Build mappings of entities to database values"""
        # Focus on key columns that users might reference
        key_columns = {
            'states': ['name', 'state_name', 'state'],
            'providers': ['name', 'provider_name', 'facility_name'],
            'users': ['state', 'state_id'],
        }
        
        # Sample values from these columns
        for table_name, schema in table_schemas.items():
            table_lower = table_name.lower().replace('analytics_view_', '')
            
            # Check if this is a states table
            if 'state' in table_lower and table_lower != 'users':
                await self._index_column_values(table_name, 'name', 'state')
                await self._index_column_values(table_name, 'state_name', 'state')
            
            # Check if this is a providers table
            if 'provider' in table_lower:
                await self._index_column_values(table_name, 'name', 'provider')
                await self._index_column_values(table_name, 'provider_name', 'provider')
                await self._index_column_values(table_name, 'facility_name', 'provider')
        
        # Build state name mappings (common Nigerian states)
        self._build_state_mappings()
    
    async def _index_column_values(self, table_name: str, column_name: str, entity_type: str):
        """Index distinct values from a column"""
        try:
            # Try analytics view first
            view_name = f"analytics_view_{table_name.replace('analytics_view_', '')}"
            query = f"SELECT DISTINCT {column_name} FROM {view_name} WHERE {column_name} IS NOT NULL LIMIT 100"
            
            try:
                results = await database_service.execute_query(query)
                values = [str(row.get(column_name, '')).strip() for row in results if row.get(column_name)]
                
                if values:
                    if column_name not in self._column_value_index:
                        self._column_value_index[column_name] = []
                    self._column_value_index[column_name].extend(values)
                    
                    # Build entity cache
                    for value in values:
                        value_lower = value.lower()
                        if entity_type not in self._entity_cache:
                            self._entity_cache[entity_type] = {}
                        self._entity_cache[entity_type][value_lower] = {
                            'table': view_name,
                            'column': column_name,
                            'value': value,
                            'aliases': self._generate_aliases(value)
                        }
            except:
                # Fallback: use known mappings
                pass
        except Exception as e:
            print(f"Warning: Could not index {table_name}.{column_name}: {e}")
    
    def _build_state_mappings(self):
        """Build comprehensive state name mappings"""
        # Nigerian states with common variations
        state_mappings = {
            'kogi': ['kogi', 'kgs', 'kgshia', 'kogi state'],
            'kano': ['kano', 'ks', 'kschma', 'kano state'],
            'kaduna': ['kaduna', 'kd', 'kadchma', 'kaduna state'],
            'osun': ['osun', 'os', 'oshia', 'osun state'],
            'rivers': ['rivers', 'riv', 'rivchpp', 'port harcourt', 'rivers state'],
            'fct': ['fct', 'federal capital territory', 'abuja', 'fhis', 'federal capital'],
            'adamawa': ['adamawa', 'ad', 'adschma', 'adamawa state'],
            'zamfara': ['zamfara', 'zm', 'zamchema', 'zamfara state'],
            'sokoto': ['sokoto', 'so', 'sohema', 'sokoto state'],
            'lagos': ['lagos', 'la', 'lagos state'],
            'oyo': ['oyo', 'oy', 'oyo state'],
            'plateau': ['plateau', 'pl', 'plateau state'],
            'benue': ['benue', 'be', 'benue state'],
            'niger': ['niger', 'ni', 'niger state'],
            'kwara': ['kwara', 'kw', 'kwara state'],
        }
        
        # Add to entity cache
        if 'state' not in self._entity_cache:
            self._entity_cache['state'] = {}
        
        for state_name, aliases in state_mappings.items():
            state_lower = state_name.lower()
            self._entity_cache['state'][state_lower] = {
                'table': 'analytics_view_states',
                'column': 'name',
                'value': state_name.title(),
                'aliases': aliases,
                'canonical': state_name
            }
            
            # Add aliases
            for alias in aliases:
                if alias != state_lower:
                    self._entity_cache['state'][alias] = {
                        'table': 'analytics_view_states',
                        'column': 'name',
                        'value': state_name.title(),
                        'aliases': aliases,
                        'canonical': state_name,
                        'is_alias': True
                    }
    
    def _generate_aliases(self, value: str) -> List[str]:
        """Generate common aliases for a value"""
        aliases = [value.lower()]
        
        # Common abbreviations
        if len(value.split()) > 1:
            # "Port Harcourt" -> "port harcourt", "ph"
            words = value.lower().split()
            if len(words) == 2:
                aliases.append(f"{words[0][0]}{words[1][0]}")
        
        return aliases
    
    async def _build_vector_index(self):
        """Build vector index for entity mappings using ChromaDB"""
        if not self._entity_collection or not self._embedding_model:
            return
        
        print("  Building vector index for entities...")
        
        # Check if collection is empty
        count = self._entity_collection.count()
        if count > 0:
            print(f"  Vector index already has {count} entities, skipping rebuild")
            return
        
        # Prepare documents for indexing
        documents = []
        metadatas = []
        ids = []
        
        # Index states
        if 'state' in self._entity_cache:
            for entity_key, entity_info in self._entity_cache['state'].items():
                # Create searchable text with entity and aliases
                search_text = f"{entity_key} {' '.join(entity_info.get('aliases', []))}"
                documents.append(search_text)
                metadatas.append({
                    'type': 'state',
                    'entity_key': entity_key,
                    'table': entity_info['table'],
                    'column': entity_info['column'],
                    'value': entity_info['value'],
                    'canonical': entity_info.get('canonical', entity_key)
                })
                ids.append(f"state_{entity_key}")
        
        # Index providers
        if 'provider' in self._entity_cache:
            for entity_key, entity_info in self._entity_cache['provider'].items():
                search_text = f"{entity_key} {' '.join(entity_info.get('aliases', []))}"
                documents.append(search_text)
                metadatas.append({
                    'type': 'provider',
                    'entity_key': entity_key,
                    'table': entity_info['table'],
                    'column': entity_info['column'],
                    'value': entity_info['value']
                })
                ids.append(f"provider_{entity_key}")
        
        if documents:
            # Generate embeddings
            print(f"  Generating embeddings for {len(documents)} entities...")
            embeddings = self._embedding_model.encode(documents, show_progress_bar=True)
            
            # Add to ChromaDB
            self._entity_collection.add(
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                ids=ids
            )
            print(f"  ✅ Indexed {len(documents)} entities in vector database")
    
    async def map_entities_to_columns(
        self,
        query: str,
        schema_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Map user entities in query to database columns and values using Vector RAG.
        
        Args:
            query: Natural language query
            schema_context: Optional schema context
        
        Returns:
            Dictionary with:
            - mapped_entities: List of mapped entities
            - sql_hints: SQL hints for entity mapping
            - confidence: Mapping confidence
        """
        # Lazy initialization - only initialize if needed
        if not self._initialized:
            try:
                await self.initialize()
            except Exception as e:
                # If initialization fails, continue with dictionary-only mode
                print(f"⚠️ Schema-RAG initialization failed, using dictionary mode: {e}")
                # Build basic state mappings for fallback
                if not self._entity_cache.get('state'):
                    self._build_state_mappings()
        
        query_lower = query.lower()
        mapped_entities = []
        sql_hints = []
        
        # Use vector search for semantic matching
        vector_mappings = await self._map_entities_with_vector_search(query)
        if vector_mappings:
            mapped_entities.extend(vector_mappings)
            for mapping in vector_mappings:
                if mapping['type'] == 'state':
                    sql_hints.append(
                        f"JOIN analytics_view_states s ON u.state = s.id WHERE s.name = '{mapping['db_value']}'"
                    )
        
        # Fallback to dictionary lookup for exact matches (faster)
        state_mappings = self._map_states(query_lower)
        if state_mappings:
            # Avoid duplicates
            existing_states = {m['db_value'] for m in mapped_entities if m.get('type') == 'state'}
            for mapping in state_mappings:
                if mapping['db_value'] not in existing_states:
                    mapped_entities.append(mapping)
                    sql_hints.append(
                        f"JOIN analytics_view_states s ON u.state = s.id WHERE s.name = '{mapping['db_value']}'"
                    )
        
        # Map providers (vector search + dictionary)
        provider_mappings = await self._map_providers(query_lower)
        if provider_mappings:
            mapped_entities.extend(provider_mappings)
        
        # Map other entities (dates, statuses, etc.)
        other_mappings = self._map_other_entities(query_lower)
        if other_mappings:
            mapped_entities.extend(other_mappings)
        
        return {
            'mapped_entities': mapped_entities,
            'sql_hints': sql_hints,
            'confidence': 0.95 if mapped_entities else 0.5,
            'query_enhanced': self._enhance_query_with_mappings(query, mapped_entities),
            'vector_search_used': len(vector_mappings) > 0
        }
    
    async def _map_entities_with_vector_search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Map entities using vector similarity search.
        
        Args:
            query: User query
            top_k: Number of top matches to return
        
        Returns:
            List of mapped entities
        """
        if not self._entity_collection or not self._embedding_model:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self._embedding_model.encode([query]).tolist()[0]
            
            # Search in ChromaDB
            results = self._entity_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=['metadatas', 'distances']
            )
            
            mappings = []
            if results['metadatas'] and len(results['metadatas'][0]) > 0:
                for i, metadata in enumerate(results['metadatas'][0]):
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    
                    # Only include if similarity is high enough (distance < 0.5)
                    if distance < 0.5:
                        mappings.append({
                            'type': metadata['type'],
                            'user_mention': query,  # Original query text
                            'db_table': metadata['table'],
                            'db_column': metadata['column'],
                            'db_value': metadata['value'],
                            'canonical': metadata.get('canonical', metadata['value']),
                            'confidence': 1.0 - distance,  # Convert distance to confidence
                            'similarity_score': 1.0 - distance
                        })
            
            return mappings
        except Exception as e:
            print(f"Warning: Vector search failed: {e}")
            return []
    
    def _map_states(self, query_lower: str) -> List[Dict[str, Any]]:
        """Map state names in query to database values (exact match fallback)"""
        mappings = []
        
        if 'state' not in self._entity_cache:
            return mappings
        
        # Check for state mentions (exact/substring matching)
        for entity_key, entity_info in self._entity_cache['state'].items():
            if entity_key in query_lower:
                mappings.append({
                    'type': 'state',
                    'user_mention': entity_key,
                    'db_table': entity_info['table'],
                    'db_column': entity_info['column'],
                    'db_value': entity_info['value'],
                    'canonical': entity_info.get('canonical', entity_key),
                    'confidence': 0.95
                })
        
        return mappings
    
    async def _map_providers(self, query_lower: str) -> List[Dict[str, Any]]:
        """Map provider names in query to database values (vector + dictionary)"""
        mappings = []
        
        # Try vector search first
        vector_mappings = await self._map_entities_with_vector_search(query_lower, top_k=2)
        provider_vector = [m for m in vector_mappings if m['type'] == 'provider']
        mappings.extend(provider_vector)
        
        # Fallback to dictionary lookup
        if 'provider' not in self._entity_cache:
            return mappings
        
        # Check for provider mentions (fuzzy matching)
        for entity_key, entity_info in self._entity_cache['provider'].items():
            # Simple substring matching
            if entity_key in query_lower or any(alias in query_lower for alias in entity_info.get('aliases', [])):
                # Avoid duplicates
                if not any(m['db_value'] == entity_info['value'] for m in mappings):
                    mappings.append({
                        'type': 'provider',
                        'user_mention': entity_key,
                        'db_table': entity_info['table'],
                        'db_column': entity_info['column'],
                        'db_value': entity_info['value'],
                        'confidence': 0.85
                    })
        
        return mappings
    
    def _map_other_entities(self, query_lower: str) -> List[Dict[str, Any]]:
        """Map other entities (dates, statuses, etc.)"""
        mappings = []
        
        # Map status values
        status_map = {
            'pending': 0,
            'approved': 1,
            'rejected': 2,
            'verified': 3
        }
        
        for status_name, status_value in status_map.items():
            if status_name in query_lower:
                mappings.append({
                    'type': 'status',
                    'user_mention': status_name,
                    'db_table': 'analytics_view_claims',
                    'db_column': 'status',
                    'db_value': status_value,
                    'confidence': 0.9
                })
        
        return mappings
    
    def _enhance_query_with_mappings(
        self,
        query: str,
        mappings: List[Dict[str, Any]]
    ) -> str:
        """Enhance query with explicit entity mappings"""
        if not mappings:
            return query
        
        enhanced = query
        for mapping in mappings:
            # Add clarification if needed
            if mapping['type'] == 'state':
                enhanced += f" [State: {mapping['canonical'].title()}]"
        
        return enhanced
    
    def get_entity_mapping_context(self, mappings: List[Dict[str, Any]]) -> str:
        """Generate SQL context from entity mappings"""
        if not mappings:
            return ""
        
        context = "\n=== ENTITY MAPPINGS (Vector RAG) ===\n"
        context += "The following entities in the user query map to database values:\n\n"
        
        for mapping in mappings:
            confidence = mapping.get('confidence', 0.8)
            similarity = mapping.get('similarity_score', 'N/A')
            context += f"- {mapping['user_mention']} → {mapping['db_table']}.{mapping['db_column']} = '{mapping['db_value']}'"
            if 'similarity_score' in mapping:
                context += f" (similarity: {similarity:.2f})"
            context += "\n"
        
        context += "\nUse these mappings in your SQL query.\n"
        context += "=== END ENTITY MAPPINGS ===\n"
        
        return context


# Global instance
schema_rag_service = SchemaRAGService()
