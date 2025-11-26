from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from ueba.config import mapping_loader
from ueba.config.mapping_loader import MappingValidationError


def _write_yaml(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(dedent(content), encoding="utf-8")
    return path


def test_merge_priority_and_selector_resolution(tmp_path: Path) -> None:
    global_file = _write_yaml(
        tmp_path,
        "global.yml",
        """
        priority: global
        defaults:
          entity_id: base.entity
          entity_type: host
          severity: medium
          timestamp: base.ts
          enrichment:
            base_field: present
        selectors:
          - name: linux-group-fallback
            match:
              group: linux
            fields:
              timestamp: group.ts
        sources:
          wazuh:
            defaults:
              entity_type: endpoint
              enrichment:
                wazuh_flag: enabled
            selectors:
              - name: wazuh-rule-overrides
                match:
                  rule_id: "2001"
                fields:
                  severity: high
                  enrichment:
                    correlation: matched
        """,
    )

    integration_file = _write_yaml(
        tmp_path,
        "integration.yml",
        """
        priority: integration
        defaults:
          severity: integration-default
        sources:
          wazuh:
            selectors:
              - name: wazuh-tier
                match:
                  custom:
                    tier: gold
                fields:
                  enrichment:
                    tier: gold
        """,
    )

    emergency_file = _write_yaml(
        tmp_path,
        "emergency.yml",
        """
        priority: emergency_override
        defaults: {}
        selectors:
          - name: emergency-2001
            match:
              rule_id: "2001"
            fields:
              severity: critical
              enrichment:
                base_field: null
        """,
    )

    resolver = mapping_loader.load([global_file, integration_file, emergency_file])
    result = resolver.lookup(source="wazuh", rule_id="2001", custom={"tier": "gold"})

    assert result.entity_id == "base.entity"
    assert result.entity_type == "endpoint"
    assert result.severity == "critical"
    assert result.timestamp == "base.ts"
    assert result.enrichment["tier"] == "gold"
    assert "base_field" not in result.enrichment
    assert result.enrichment["wazuh_flag"] == "enabled"
    assert result.enrichment["correlation"] == "matched"


def test_missing_field_validation(tmp_path: Path) -> None:
    invalid_file = _write_yaml(
        tmp_path,
        "invalid.yml",
        """
        priority: global
        defaults:
          entity_id: missing.type
          severity: low
          timestamp: now
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([invalid_file])

    assert "entity_type" in str(exc.value)
    assert str(invalid_file) in str(exc.value)


def test_higher_priority_inherits_when_field_omitted(tmp_path: Path) -> None:
    global_file = _write_yaml(
        tmp_path,
        "base.yml",
        """
        priority: global
        defaults:
          entity_id: base.entity
          entity_type: host
          severity: base
          timestamp: base.ts
        """,
    )

    integration_file = _write_yaml(
        tmp_path,
        "integration.yml",
        """
        priority: integration
        defaults:
          severity: integration
        """,
    )

    resolver = mapping_loader.load([global_file, integration_file])
    result = resolver.lookup()

    assert result.severity == "integration"
    assert result.entity_type == "host"
    assert result.entity_id == "base.entity"
    assert result.timestamp == "base.ts"


def test_selector_fallback_order(tmp_path: Path) -> None:
    mapping_file = _write_yaml(
        tmp_path,
        "selectors.yml",
        """
        priority: global
        defaults:
          entity_id: base
          entity_type: default
          severity: low
          timestamp: base.ts
        selectors:
          - name: rule-specific
            match:
              rule_id: "3001"
            fields:
              entity_type: rule
          - name: group-specific
            match:
              group: auth
            fields:
              entity_type: group
          - name: custom-specific
            match:
              custom:
                vendor: wazuh
            fields:
              entity_type: custom
        """,
    )

    resolver = mapping_loader.load([mapping_file])

    rule_result = resolver.lookup(rule_id="3001", groups=["auth"], custom={"vendor": "wazuh"})
    assert rule_result.entity_type == "rule"

    group_result = resolver.lookup(groups=["auth"], custom={"vendor": "wazuh"})
    assert group_result.entity_type == "group"

    custom_result = resolver.lookup(custom={"vendor": "wazuh"})
    assert custom_result.entity_type == "custom"

    default_result = resolver.lookup(groups=["other"])  # no selectors hit
    assert default_result.entity_type == "default"
