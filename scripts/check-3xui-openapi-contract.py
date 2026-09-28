#!/usr/bin/env python3
"""Fail-closed 3x-ui OpenAPI compatibility gate.

Validates three things together:
1. the vendored schema is the exact pinned upstream Git blob;
2. every declared client endpoint still has the expected OpenAPI method/signature;
3. the declared manifest exactly matches panel API routes used by xui.py/version_api.py.

The checker is intentionally stdlib-only so CI never needs network access.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
PLACEHOLDER_ALIASES = {
    "node_id": "id",
    "inbound_id": "id",
    "device_id": "id",
    "telegram_id": "tgId",
    "sub_id": "subId",
}


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _placeholder_name(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return PLACEHOLDER_ALIASES.get(expr.id, expr.id)
    if isinstance(expr, ast.Attribute):
        return expr.attr
    if isinstance(expr, ast.Call) and expr.args:
        if isinstance(expr.func, ast.Name) and expr.func.id in {"int", "str", "quote"}:
            return _placeholder_name(expr.args[0])
    return None


def _route_values(expr: ast.AST, env: dict[str, set[str]]) -> set[str]:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return {expr.value}
    if isinstance(expr, ast.Name):
        return set(env.get(expr.id, set()))
    if isinstance(expr, ast.IfExp):
        return _route_values(expr.body, env) | _route_values(expr.orelse, env)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left = _route_values(expr.left, env)
        right = _route_values(expr.right, env)
        return {a + b for a in left for b in right}
    if isinstance(expr, ast.JoinedStr):
        values = {""}
        for part in expr.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                values = {prefix + part.value for prefix in values}
                continue
            if isinstance(part, ast.FormattedValue):
                name = _placeholder_name(part.value)
                if not name:
                    return set()
                values = {prefix + "{" + name + "}" for prefix in values}
                continue
            return set()
        return values
    return set()


def _canonical_route(value: str) -> str | None:
    marker = "/panel/api/"
    pos = value.find(marker)
    if pos < 0:
        return None
    return value[pos:]


def discover_client_routes(root: Path, source_files: list[str]) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for relative in source_files:
        path = root / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for func in functions:
            env: dict[str, set[str]] = {}
            # Resolve simple local route aliases such as:
            # path = ".../list/slim" if slim else ".../list"
            for _ in range(4):
                changed = False
                for node in ast.walk(func):
                    target_name: str | None = None
                    value: ast.AST | None = None
                    if isinstance(node, ast.Assign) and len(node.targets) == 1:
                        if isinstance(node.targets[0], ast.Name):
                            target_name = node.targets[0].id
                            value = node.value
                    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                        target_name = node.target.id
                        value = node.value
                    if not target_name or value is None:
                        continue
                    found = _route_values(value, env)
                    if not found:
                        continue
                    before = set(env.get(target_name, set()))
                    after = before | found
                    if after != before:
                        env[target_name] = after
                        changed = True
                if not changed:
                    break

            for node in ast.walk(func):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                name = node.func.attr
                method: str | None = None
                path_expr: ast.AST | None = None
                if name in {"_request", "_version_request"} and len(node.args) >= 2:
                    if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        candidate = node.args[0].value.upper()
                        if candidate in HTTP_METHODS:
                            method = candidate
                            path_expr = node.args[1]
                elif name == "_mutation_request" and node.args:
                    method = "POST"
                    for keyword in node.keywords:
                        if (
                            keyword.arg == "method"
                            and isinstance(keyword.value, ast.Constant)
                            and isinstance(keyword.value.value, str)
                        ):
                            candidate = keyword.value.value.upper()
                            if candidate in HTTP_METHODS:
                                method = candidate
                    path_expr = node.args[0]
                elif name.upper() in HTTP_METHODS and node.args:
                    # Covers direct aiohttp GET used by download_database().
                    method = name.upper()
                    path_expr = node.args[0]

                if not method or path_expr is None:
                    continue
                for value in _route_values(path_expr, env):
                    route = _canonical_route(value)
                    if route:
                        routes.add((method, route))
    return routes


def _resolve_schema(schema: Any, document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    if not ref.startswith("#/"):
        return {}
    current: Any = document
    for raw in ref[2:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return {}
        current = current[token]
    return current if isinstance(current, dict) else {}


def validate_openapi_contract(
    manifest: dict[str, Any],
    api: dict[str, Any],
    *,
    schema_blob_sha: str | None = None,
) -> list[str]:
    errors: list[str] = []

    supported = str(manifest.get("supported_3xui_version") or "")
    upstream = manifest.get("upstream") or {}
    if upstream.get("ref") != f"v{supported}":
        errors.append("manifest upstream.ref must exactly match supported_3xui_version")

    if schema_blob_sha and upstream.get("schema_blob_sha") != schema_blob_sha:
        errors.append(
            "vendored OpenAPI blob SHA does not match pinned upstream schema_blob_sha"
        )

    if api.get("openapi") != "3.0.3":
        errors.append(f"expected OpenAPI 3.0.3, got {api.get('openapi')!r}")
    if (api.get("info") or {}).get("title") != "3X-UI Panel API":
        errors.append("unexpected OpenAPI info.title")

    security_name = str(manifest.get("required_security_scheme") or "")
    schemes = ((api.get("components") or {}).get("securitySchemes") or {})
    scheme = schemes.get(security_name) or {}
    if scheme.get("type") != "http" or str(scheme.get("scheme") or "").lower() != "bearer":
        errors.append(f"required security scheme {security_name!r} is not HTTP bearer")

    endpoints = manifest.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        return errors + ["manifest endpoints must be a non-empty list"]

    keys: set[tuple[str, str]] = set()
    weak_response_keys: set[tuple[str, str]] = set()
    default_props = set(manifest.get("default_response_200_json_properties") or [])
    paths = api.get("paths") or {}

    for entry in endpoints:
        method = str(entry.get("method") or "").upper()
        path = str(entry.get("path") or "")
        key = (method, path)
        if method not in HTTP_METHODS or not path.startswith("/panel/api/"):
            errors.append(f"invalid endpoint declaration: {method} {path}")
            continue
        if key in keys:
            errors.append(f"duplicate endpoint declaration: {method} {path}")
            continue
        keys.add(key)

        path_item = paths.get(path)
        if not isinstance(path_item, dict):
            errors.append(f"OpenAPI missing path: {method} {path}")
            continue
        operation = path_item.get(method.lower())
        if not isinstance(operation, dict):
            errors.append(f"OpenAPI missing method: {method} {path}")
            continue

        effective_security = operation.get("security", api.get("security", []))
        if not any(
            isinstance(item, dict) and security_name in item
            for item in (effective_security or [])
        ):
            errors.append(f"bearer auth missing for {method} {path}")

        request_expected = entry.get("request")
        request_body = operation.get("requestBody")
        if request_expected is None:
            if isinstance(request_body, dict) and request_body.get("content"):
                errors.append(
                    f"unexpected request body contract for {method} {path}; "
                    "declare it explicitly in the manifest"
                )
        else:
            if not isinstance(request_expected, dict):
                errors.append(f"invalid request declaration for {method} {path}")
            elif not isinstance(request_body, dict):
                errors.append(f"OpenAPI requestBody missing for {method} {path}")
            else:
                expected_required = bool(request_expected.get("required"))
                actual_required = bool(request_body.get("required"))
                if actual_required != expected_required:
                    errors.append(
                        f"requestBody.required drift for {method} {path}: "
                        f"expected {expected_required}, got {actual_required}"
                    )
                content_type = str(request_expected.get("content_type") or "")
                content = request_body.get("content") or {}
                media = content.get(content_type)
                if not isinstance(media, dict):
                    errors.append(
                        f"request content type drift for {method} {path}: "
                        f"missing {content_type}"
                    )
                else:
                    schema = _resolve_schema(media.get("schema"), api)
                    actual_fields = sorted(str(x) for x in (schema.get("required") or []))
                    expected_fields = sorted(
                        str(x) for x in (request_expected.get("required_fields") or [])
                    )
                    if actual_fields != expected_fields:
                        errors.append(
                            f"required request fields drift for {method} {path}: "
                            f"expected {expected_fields}, got {actual_fields}"
                        )

        responses = operation.get("responses") or {}
        response_200 = responses.get("200")
        if not isinstance(response_200, dict):
            errors.append(f"200 response missing for {method} {path}")
            continue

        if entry.get("response_envelope", True) is False:
            weak_response_keys.add(key)
        else:
            media = (response_200.get("content") or {}).get("application/json")
            if not isinstance(media, dict):
                errors.append(f"JSON 200 response missing for {method} {path}")
                continue
            schema = _resolve_schema(media.get("schema"), api)
            props = set((schema.get("properties") or {}).keys())
            missing_props = sorted(default_props - props)
            if missing_props:
                errors.append(
                    f"response envelope drift for {method} {path}: "
                    f"missing properties {missing_props}"
                )

    exceptions = manifest.get("documented_exceptions") or []
    exception_keys = {
        (str(item.get("method") or "").upper(), str(item.get("path") or ""))
        for item in exceptions
        if isinstance(item, dict)
    }
    if exception_keys != weak_response_keys:
        errors.append(
            "documented_exceptions must exactly match endpoints with response_envelope=false"
        )

    return errors


def validate_contract(root: Path, manifest_path: Path | None = None) -> list[str]:
    manifest_path = manifest_path or root / "contracts/3xui/contract.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema_path = root / str(manifest.get("vendored_schema") or "")
    schema_bytes = schema_path.read_bytes()
    api = json.loads(schema_bytes.decode("utf-8"))

    errors = validate_openapi_contract(
        manifest,
        api,
        schema_blob_sha=git_blob_sha(schema_bytes),
    )

    source_files = manifest.get("source_files") or []
    if not isinstance(source_files, list) or not all(isinstance(x, str) for x in source_files):
        errors.append("manifest source_files must be a list of repository paths")
        return errors

    declared = {
        (str(item.get("method") or "").upper(), str(item.get("path") or ""))
        for item in (manifest.get("endpoints") or [])
        if isinstance(item, dict)
    }
    discovered = discover_client_routes(root, list(source_files))

    for method, path in sorted(discovered - declared):
        errors.append(f"client route is undeclared: {method} {path}")
    for method, path in sorted(declared - discovered):
        errors.append(f"manifest route is not used by client sources: {method} {path}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: auto-detected).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Contract manifest path (default: contracts/3xui/contract.json).",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    manifest = args.manifest.resolve() if args.manifest else None
    try:
        errors = validate_contract(root, manifest)
    except (OSError, ValueError, json.JSONDecodeError, SyntaxError) as exc:
        print(f"3x-ui OpenAPI contract gate failed to run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("3x-ui OpenAPI contract FAILED:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    data = json.loads((manifest or root / "contracts/3xui/contract.json").read_text(encoding="utf-8"))
    print(
        "3x-ui OpenAPI contract OK: "
        f"v{data['supported_3xui_version']} · "
        f"{len(data['endpoints'])} endpoints · "
        f"blob {data['upstream']['schema_blob_sha']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
