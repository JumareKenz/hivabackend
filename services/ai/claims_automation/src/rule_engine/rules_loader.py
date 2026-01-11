"""
Rules Loader
Loads rule definitions from configuration files with versioning and caching
"""

import json
import yaml
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from ..core.config import settings
from ..core.models import RuleDefinition, RuleCategory, RuleSeverity

logger = logging.getLogger(__name__)


class RulesLoader:
    """
    Load and manage rule definitions from configuration.
    Supports YAML and JSON formats.
    """
    
    def __init__(self, rules_path: Optional[Path] = None):
        self.rules_path = rules_path or settings.RULE_STORE_PATH
        self.cache: Dict[str, RuleDefinition] = {}
        self.active_version: str = "1.0.0"
    
    async def load_active_ruleset(self) -> Dict[str, RuleDefinition]:
        """
        Load all active rules from configuration.
        Returns dict of rule_id -> RuleDefinition
        """
        rules = {}
        
        # Try to load from files first
        if self.rules_path.exists():
            rules = await self._load_from_files()
        
        # If no rules loaded, use hardcoded defaults
        if not rules:
            logger.warning("No rules found in configuration, loading hardcoded defaults")
            rules = self._load_hardcoded_rules()
        
        logger.info(f"Loaded {len(rules)} rules (version {self.active_version})")
        
        return rules
    
    async def _load_from_files(self) -> Dict[str, RuleDefinition]:
        """Load rules from YAML/JSON configuration files"""
        rules = {}
        
        for rules_file in self.rules_path.glob("*.yaml"):
            try:
                with open(rules_file, 'r') as f:
                    data = yaml.safe_load(f)
                    file_rules = self._parse_rules_config(data)
                    rules.update(file_rules)
                    logger.info(f"Loaded {len(file_rules)} rules from {rules_file.name}")
            except Exception as e:
                logger.error(f"Failed to load rules from {rules_file}: {e}")
        
        for rules_file in self.rules_path.glob("*.json"):
            try:
                with open(rules_file, 'r') as f:
                    data = json.load(f)
                    file_rules = self._parse_rules_config(data)
                    rules.update(file_rules)
                    logger.info(f"Loaded {len(file_rules)} rules from {rules_file.name}")
            except Exception as e:
                logger.error(f"Failed to load rules from {rules_file}: {e}")
        
        return rules
    
    def _parse_rules_config(self, config: Dict) -> Dict[str, RuleDefinition]:
        """Parse rules from configuration dictionary"""
        rules = {}
        
        if 'version' in config:
            self.active_version = config['version']
        
        for rule_data in config.get('rules', []):
            try:
                rule = RuleDefinition(
                    rule_id=rule_data['rule_id'],
                    version=rule_data.get('version', self.active_version),
                    name=rule_data['name'],
                    description=rule_data.get('description', ''),
                    category=RuleCategory(rule_data['category']),
                    severity=RuleSeverity(rule_data['severity']),
                    enabled=rule_data.get('enabled', True),
                    condition_expression=rule_data['condition'],
                    parameters=rule_data.get('parameters', {}),
                    applies_to_claim_types=rule_data.get('applies_to_claim_types', ['ALL']),
                    applies_to_jurisdictions=rule_data.get('applies_to_jurisdictions', ['ALL']),
                    documentation_url=rule_data.get('documentation_url'),
                    created_by=rule_data.get('created_by', 'system')
                )
                rules[rule.rule_id] = rule
            except Exception as e:
                logger.error(f"Failed to parse rule {rule_data.get('rule_id', 'unknown')}: {e}")
        
        return rules
    
    def _load_hardcoded_rules(self) -> Dict[str, RuleDefinition]:
        """
        Hardcoded rules for initial deployment.
        These are the most critical rules that must always be active.
        """
        rules = {}
        
        # CRITICAL RULES
        rules['CR001'] = RuleDefinition(
            rule_id='CR001',
            version='1.0.0',
            name='No Negative Amounts',
            description='Claim amount must be positive',
            category=RuleCategory.CRITICAL,
            severity=RuleSeverity.CRITICAL,
            enabled=True,
            condition_expression='claim.billed_amount > 0',
            parameters={}
        )
        
        rules['CR002'] = RuleDefinition(
            rule_id='CR002',
            version='1.0.0',
            name='Service Date Not Future',
            description='Service date cannot be in the future',
            category=RuleCategory.CRITICAL,
            severity=RuleSeverity.CRITICAL,
            enabled=True,
            condition_expression='claim.service_date <= today()',
            parameters={}
        )
        
        rules['CR003'] = RuleDefinition(
            rule_id='CR003',
            version='1.0.0',
            name='Minimum Data Requirements',
            description='Claim must have at least one procedure code and diagnosis code',
            category=RuleCategory.CRITICAL,
            severity=RuleSeverity.CRITICAL,
            enabled=True,
            condition_expression='len(claim.procedure_codes) > 0 and len(claim.diagnosis_codes) > 0',
            parameters={}
        )
        
        rules['CR004'] = RuleDefinition(
            rule_id='CR004',
            version='1.0.0',
            name='Valid Claim ID',
            description='Claim must have valid unique identifier',
            category=RuleCategory.CRITICAL,
            severity=RuleSeverity.CRITICAL,
            enabled=True,
            condition_expression='len(claim.claim_id) > 0',
            parameters={}
        )
        
        rules['CR005'] = RuleDefinition(
            rule_id='CR005',
            version='1.0.0',
            name='Maximum Amount Sanity Check',
            description='Claim amount must be below sanity threshold',
            category=RuleCategory.CRITICAL,
            severity=RuleSeverity.CRITICAL,
            enabled=True,
            condition_expression='claim.billed_amount < parameters["max_amount"]',
            parameters={'max_amount': 50000000.0}  # 50 million NGN
        )
        
        # POLICY COVERAGE RULES
        rules['PC001'] = RuleDefinition(
            rule_id='PC001',
            version='1.0.0',
            name='Policy Active Status',
            description='Policy must be in ACTIVE status',
            category=RuleCategory.POLICY_COVERAGE,
            severity=RuleSeverity.MAJOR,
            enabled=True,
            condition_expression='policy is None or policy.status == "ACTIVE"',
            parameters={}
        )
        
        rules['PC002'] = RuleDefinition(
            rule_id='PC002',
            version='1.0.0',
            name='Service Date Within Policy Period',
            description='Service date must fall within policy effective period',
            category=RuleCategory.POLICY_COVERAGE,
            severity=RuleSeverity.MAJOR,
            enabled=True,
            condition_expression='policy is None or (claim.service_date >= policy.effective_date and (policy.termination_date is None or claim.service_date <= policy.termination_date))',
            parameters={}
        )
        
        rules['PC003'] = RuleDefinition(
            rule_id='PC003',
            version='1.0.0',
            name='Annual Maximum Not Exceeded',
            description='Claim amount would not exceed policy annual maximum',
            category=RuleCategory.POLICY_COVERAGE,
            severity=RuleSeverity.MAJOR,
            enabled=True,
            condition_expression='policy is None or policy.annual_maximum is None or claim.billed_amount <= policy.annual_maximum',
            parameters={}
        )
        
        # PROVIDER ELIGIBILITY RULES
        rules['PE001'] = RuleDefinition(
            rule_id='PE001',
            version='1.0.0',
            name='Provider Active Status',
            description='Provider must be in ACTIVE status',
            category=RuleCategory.PROVIDER_ELIGIBILITY,
            severity=RuleSeverity.MAJOR,
            enabled=True,
            condition_expression='provider is None or provider.status == "ACTIVE"',
            parameters={}
        )
        
        rules['PE002'] = RuleDefinition(
            rule_id='PE002',
            version='1.0.0',
            name='Provider License Valid',
            description='Provider license must be valid (not expired)',
            category=RuleCategory.PROVIDER_ELIGIBILITY,
            severity=RuleSeverity.MAJOR,
            enabled=True,
            condition_expression='provider is None or provider.license_status == "VALID"',
            parameters={}
        )
        
        rules['PE003'] = RuleDefinition(
            rule_id='PE003',
            version='1.0.0',
            name='Service Date Within Provider Contract',
            description='Service date must fall within provider effective period',
            category=RuleCategory.PROVIDER_ELIGIBILITY,
            severity=RuleSeverity.MAJOR,
            enabled=True,
            condition_expression='provider is None or (claim.service_date >= provider.effective_date and (provider.termination_date is None or claim.service_date <= provider.termination_date))',
            parameters={}
        )
        
        # TEMPORAL VALIDATION RULES
        rules['TV001'] = RuleDefinition(
            rule_id='TV001',
            version='1.0.0',
            name='Timely Filing Limit',
            description='Claim must be submitted within timely filing limit',
            category=RuleCategory.TEMPORAL_VALIDATION,
            severity=RuleSeverity.MAJOR,
            enabled=True,
            condition_expression='(today() - claim.service_date).days <= parameters["days_limit"]',
            parameters={'days_limit': 365}
        )
        
        rules['TV002'] = RuleDefinition(
            rule_id='TV002',
            version='1.0.0',
            name='Service Date Range Valid',
            description='If date range provided, end date must be >= start date',
            category=RuleCategory.TEMPORAL_VALIDATION,
            severity=RuleSeverity.MAJOR,
            enabled=True,
            condition_expression='claim.service_date_end is None or claim.service_date_end >= claim.service_date',
            parameters={}
        )
        
        # TARIFF COMPLIANCE RULES
        rules['TC001'] = RuleDefinition(
            rule_id='TC001',
            version='1.0.0',
            name='High Cost Alert',
            description='Flag claims above high cost threshold for review',
            category=RuleCategory.TARIFF_COMPLIANCE,
            severity=RuleSeverity.MINOR,
            enabled=True,
            condition_expression='claim.billed_amount < parameters["threshold"]',
            parameters={'threshold': 500000.0}  # 500k NGN
        )
        
        # DUPLICATE DETECTION RULES
        rules['DD001'] = RuleDefinition(
            rule_id='DD001',
            version='1.0.0',
            name='Member High Frequency Alert',
            description='Flag if member has unusually high claim frequency',
            category=RuleCategory.DUPLICATE_DETECTION,
            severity=RuleSeverity.MINOR,
            enabled=True,
            condition_expression='member_history is None or member_history.claims_30d < parameters["max_claims_30d"]',
            parameters={'max_claims_30d': 20}
        )
        
        rules['DD002'] = RuleDefinition(
            rule_id='DD002',
            version='1.0.0',
            name='Provider High Frequency Alert',
            description='Flag if provider has unusually high claim frequency',
            category=RuleCategory.DUPLICATE_DETECTION,
            severity=RuleSeverity.MINOR,
            enabled=True,
            condition_expression='provider_history is None or provider_history.claims_30d < parameters["max_claims_30d"]',
            parameters={'max_claims_30d': 500}
        )
        
        logger.info(f"Loaded {len(rules)} hardcoded rules")
        return rules
    
    async def get_active_version(self) -> str:
        """Get active ruleset version"""
        return self.active_version
    
    async def get_rule_by_id(self, rule_id: str) -> Optional[RuleDefinition]:
        """Get specific rule by ID"""
        if rule_id in self.cache:
            return self.cache[rule_id]
        
        # Reload if not in cache
        ruleset = await self.load_active_ruleset()
        return ruleset.get(rule_id)


