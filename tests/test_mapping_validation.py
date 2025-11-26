from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

import pytest

from ueba.config import mapping_loader
from ueba.config.mapping_loader import MappingLoaderError, MappingValidationError


def _write_yaml(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(dedent(content), encoding="utf-8")
    return path


def test_invalid_yaml_syntax(tmp_path: Path) -> None:
    invalid_file = _write_yaml(
        tmp_path,
        "invalid.yml",
        """
        priority: global
        defaults:
          entity_id: value
          entity_type: host
          [invalid syntax
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([invalid_file])

    assert "Invalid YAML" in str(exc.value)
    assert str(invalid_file) in str(exc.value)


def test_missing_defaults_section(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "missing_defaults.yml",
        """
        priority: global
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    assert "defaults section is required" in str(exc.value)


def test_invalid_priority_value(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "invalid_priority.yml",
        """
        priority: unknown_priority
        defaults:
          entity_id: id
          entity_type: host
          severity: low
          timestamp: ts
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    assert "Invalid priority" in str(exc.value)


def test_unknown_field_in_defaults(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "unknown_field.yml",
        """
        priority: global
        defaults:
          entity_id: id
          entity_type: host
          severity: low
          timestamp: ts
          unknown_field: value
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    assert "unknown field" in str(exc.value).lower()
    assert "unknown_field" in str(exc.value)


def test_selector_without_match(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "no_match.yml",
        """
        priority: global
        defaults:
          entity_id: id
          entity_type: host
          severity: low
          timestamp: ts
        selectors:
          - name: broken
            fields:
              severity: high
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    assert "missing a match block" in str(exc.value)


def test_selector_without_name(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "no_name.yml",
        """
        priority: global
        defaults:
          entity_id: id
          entity_type: host
          severity: low
          timestamp: ts
        selectors:
          - match:
              rule_id: "1"
            fields:
              severity: high
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    assert "require a 'name' field" in str(exc.value)


def test_empty_match_block(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "empty_match.yml",
        """
        priority: global
        defaults:
          entity_id: id
          entity_type: host
          severity: low
          timestamp: ts
        selectors:
          - name: broken
            match: {}
            fields:
              severity: high
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    assert "must specify at least one selector field" in str(exc.value)


def test_non_dict_mapping_file(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "not_dict.yml",
        """
        - this
        - is
        - a
        - list
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    assert "must define a dictionary" in str(exc.value)


def test_non_dict_source_body(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "bad_source.yml",
        """
        priority: global
        defaults:
          entity_id: id
          entity_type: host
          severity: low
          timestamp: ts
        sources:
          wazuh: not_a_dict
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    assert "must be a dictionary" in str(exc.value)


def test_file_not_found(tmp_path: Path) -> None:
    non_existing = tmp_path / "does_not_exist.yml"

    with pytest.raises(MappingLoaderError) as exc:
        mapping_loader.load([non_existing])

    assert "not found" in str(exc.value)


def test_load_default_path_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mapping_file = _write_yaml(
        tmp_path,
        "custom.yml",
        """
        priority: global
        defaults:
          entity_id: env.id
          entity_type: env_host
          severity: env_sev
          timestamp: env.ts
        """,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UEBA_MAPPING_PATHS", f"{mapping_file}")

    resolver = mapping_loader.load()
    result = resolver.lookup()

    assert result.entity_id == "env.id"
    assert result.entity_type == "env_host"


def test_load_multiple_paths_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file1 = _write_yaml(
        tmp_path,
        "file1.yml",
        """
        priority: global
        defaults:
          entity_id: file1.id
          entity_type: host
          severity: low
          timestamp: file1.ts
        """,
    )

    file2 = _write_yaml(
        tmp_path,
        "file2.yml",
        """
        priority: integration
        defaults:
          severity: high
        """,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UEBA_MAPPING_PATHS", f"{file1}{os.pathsep}{file2}")

    resolver = mapping_loader.load()
    result = resolver.lookup()

    assert result.entity_id == "file1.id"
    assert result.severity == "high"


def test_no_mapping_files_provided(tmp_path: Path) -> None:
    with pytest.raises(MappingLoaderError) as exc:
        mapping_loader.load([])

    assert "No mapping files were provided" in str(exc.value)


def test_enrichment_explicit_null_removes_field(tmp_path: Path) -> None:
    global_file = _write_yaml(
        tmp_path,
        "base.yml",
        """
        priority: global
        defaults:
          entity_id: base
          entity_type: host
          severity: low
          timestamp: ts
          enrichment:
            to_remove: original_value
            to_keep: keep_me
        """,
    )

    override_file = _write_yaml(
        tmp_path,
        "override.yml",
        """
        priority: emergency_override
        defaults:
          enrichment:
            to_remove: null
        """,
    )

    resolver = mapping_loader.load([global_file, override_file])
    result = resolver.lookup()

    assert "to_remove" not in result.enrichment
    assert result.enrichment["to_keep"] == "keep_me"


def test_enrichment_entire_null_clears_all(tmp_path: Path) -> None:
    global_file = _write_yaml(
        tmp_path,
        "base.yml",
        """
        priority: global
        defaults:
          entity_id: base
          entity_type: host
          severity: low
          timestamp: ts
          enrichment:
            field1: value1
            field2: value2
        """,
    )

    override_file = _write_yaml(
        tmp_path,
        "override.yml",
        """
        priority: emergency_override
        defaults:
          enrichment: null
        """,
    )

    resolver = mapping_loader.load([global_file, override_file])
    result = resolver.lookup()

    assert result.enrichment == {}


def test_line_numbers_in_error_messages(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "line_test.yml",
        """
        priority: global
        defaults:
          entity_id: id
          severity: low
          timestamp: ts
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    error_msg = str(exc.value)
    assert str(file) in error_msg
    assert ":" in error_msg


def test_non_scalar_enrichment_value(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "bad_enrichment.yml",
        """
        priority: global
        defaults:
          entity_id: id
          entity_type: host
          severity: low
          timestamp: ts
          enrichment:
            nested:
              not: allowed
        """,
    )

    with pytest.raises(MappingValidationError) as exc:
        mapping_loader.load([file])

    assert "must be scalar" in str(exc.value)


def test_numeric_field_values_converted_to_string(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "numeric.yml",
        """
        priority: global
        defaults:
          entity_id: id
          entity_type: host
          severity: 5
          timestamp: ts
          enrichment:
            count: 42
            ratio: 3.14
        """,
    )

    resolver = mapping_loader.load([file])
    result = resolver.lookup()

    assert result.severity == "5"
    assert result.enrichment["count"] == "42"
    assert result.enrichment["ratio"] == "3.14"


def test_group_matching_with_multiple_groups(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "groups.yml",
        """
        priority: global
        defaults:
          entity_id: default
          entity_type: host
          severity: low
          timestamp: ts
        selectors:
          - name: auth-selector
            match:
              group: authentication
            fields:
              entity_type: user
        """,
    )

    resolver = mapping_loader.load([file])

    result_match = resolver.lookup(groups=["authentication", "failed"])
    assert result_match.entity_type == "user"

    result_no_match = resolver.lookup(groups=["web", "firewall"])
    assert result_no_match.entity_type == "host"


def test_custom_match_all_fields_must_match(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "custom_match.yml",
        """
        priority: global
        defaults:
          entity_id: default
          entity_type: host
          severity: low
          timestamp: ts
        selectors:
          - name: custom-selector
            match:
              custom:
                vendor: wazuh
                product: ossec
            fields:
              entity_type: wazuh_ossec
        """,
    )

    resolver = mapping_loader.load([file])

    result_match = resolver.lookup(custom={"vendor": "wazuh", "product": "ossec"})
    assert result_match.entity_type == "wazuh_ossec"

    result_partial = resolver.lookup(custom={"vendor": "wazuh"})
    assert result_partial.entity_type == "host"


def test_source_defaults_override_global(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "source_defaults.yml",
        """
        priority: global
        defaults:
          entity_id: global.id
          entity_type: global_host
          severity: low
          timestamp: global.ts
          enrichment:
            global_field: present
        sources:
          wazuh:
            defaults:
              entity_type: wazuh_host
              enrichment:
                wazuh_field: enabled
        """,
    )

    resolver = mapping_loader.load([file])

    wazuh_result = resolver.lookup(source="wazuh")
    assert wazuh_result.entity_type == "wazuh_host"
    assert wazuh_result.enrichment["global_field"] == "present"
    assert wazuh_result.enrichment["wazuh_field"] == "enabled"

    other_result = resolver.lookup(source="other")
    assert other_result.entity_type == "global_host"
    assert other_result.enrichment["global_field"] == "present"
    assert "wazuh_field" not in other_result.enrichment


def test_source_selector_overrides_source_defaults(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "source_selector.yml",
        """
        priority: global
        defaults:
          entity_id: global.id
          entity_type: global_host
          severity: low
          timestamp: global.ts
        sources:
          wazuh:
            defaults:
              entity_type: wazuh_default
            selectors:
              - name: wazuh-auth
                match:
                  rule_id: "5710"
                fields:
                  entity_type: wazuh_user
        """,
    )

    resolver = mapping_loader.load([file])

    wazuh_auth = resolver.lookup(source="wazuh", rule_id="5710")
    assert wazuh_auth.entity_type == "wazuh_user"

    wazuh_other = resolver.lookup(source="wazuh", rule_id="9999")
    assert wazuh_other.entity_type == "wazuh_default"


def test_as_dict_output(tmp_path: Path) -> None:
    file = _write_yaml(
        tmp_path,
        "dict_test.yml",
        """
        priority: global
        defaults:
          entity_id: id
          entity_type: host
          severity: low
          timestamp: ts
          enrichment:
            field1: value1
        """,
    )

    resolver = mapping_loader.load([file])
    result = resolver.lookup()
    result_dict = result.as_dict()

    assert result_dict["entity_id"] == "id"
    assert result_dict["entity_type"] == "host"
    assert result_dict["severity"] == "low"
    assert result_dict["timestamp"] == "ts"
    assert result_dict["enrichment"]["field1"] == "value1"
