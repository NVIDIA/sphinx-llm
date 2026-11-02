#!/usr/bin/env python
# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# /// script
# requires-python = ">=3.12"
# dependencies = ["packaging>=24,<27", "ruamel.yaml>=0.18,<0.20"]
# ///
"""Run with uv to refresh Python CI coverage; --dry-run leaves the workflow untouched.

Keep security-maintained Python until EOL, and keep the five Sphinx rows on 3.12.
Only the remaining matrix rows change; package support and other jobs do not.
"""

import argparse
import io
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as Quoted

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/test.yml"


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def supported_python(data, today):
    data = data["result"]["releases"]
    if not isinstance(data, list) or not data:
        raise ValueError("Expected nonempty Python lifecycle metadata")
    supported, known = [], set()
    for entry in data:
        cycle = entry["name"]
        if not re.fullmatch(r"\d+\.\d+", cycle) or cycle in known:
            raise ValueError(f"Invalid or duplicate Python cycle: {cycle}")
        known.add(cycle)
        released, latest = (
            date.fromisoformat(entry["releaseDate"]),
            Version(entry["latest"]["name"]),
        )
        eol = date.fromisoformat(entry["eolFrom"])
        if eol < released:
            raise ValueError(f"EOL precedes release: {cycle}")
        if latest.release[:2] != Version(cycle).release:
            raise ValueError(f"Release does not match cycle: {cycle}")
        if (
            cycle.startswith("3.")
            and released <= today
            and not latest.is_prerelease
            and not latest.is_devrelease
            and today < eol
        ):
            supported.append(cycle)
    if not supported:
        raise ValueError("No supported stable Python releases")
    return sorted(supported, key=Version), known


def sphinx_releases(data, today):
    releases = []
    for number, files in data["releases"].items():
        version = Version(number)
        if version.is_prerelease or version.is_devrelease:
            continue
        for file in files:
            # Old distributions without Requires-Python are not compatibility evidence.
            if file["yanked"] or not file.get("requires_python"):
                continue
            uploaded = date.fromisoformat(file["upload_time_iso_8601"][:10])
            if uploaded <= today:
                releases.append((version, SpecifierSet(file["requires_python"])))
    if not releases:
        raise ValueError("No usable stable Sphinx releases")
    return sorted(releases, key=lambda item: item[0], reverse=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    versions, known = supported_python(
        fetch_json("https://endoflife.date/api/v1/products/python/"), today
    )
    releases = sphinx_releases(fetch_json("https://pypi.org/pypi/sphinx/json"), today)
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 2**16
    yaml.indent(mapping=2, sequence=4, offset=2)
    workflow = yaml.load(WORKFLOW)
    rows = workflow["jobs"]["test"]["strategy"]["matrix"]["include"]
    if (
        len(rows) < 5
        or [row["python-version"] for row in rows[:5]] != ["3.12"] * 5
        or [row["sphinx-version"] for row in rows[:5]]
        != [">=5.1,<6", ">=6,<7", ">=7,<8", ">=8,<9", ">=9,<10"]
        or any(row["python-version"] not in known for row in rows)
    ):
        raise ValueError("Unexpected matrix layout or incomplete Python metadata")
    desired = []
    for python in versions:
        if python == "3.12":
            continue
        compatible = next(
            (v for v, requirement in releases if requirement.contains(f"{python}.0")),
            None,
        )
        if compatible is None:
            raise ValueError(f"No compatible Sphinx for Python {python}")
        desired.append(
            {
                "python-version": Quoted(python),
                "sphinx-version": Quoted(
                    f">={compatible.major},<{compatible.major + 1}"
                ),
            }
        )
    print("Supported Python:", ", ".join(versions))
    if list(rows[5:]) == desired:
        print("CI matrix already current")
    else:
        print("CI matrix update needed")
        del rows[5:]
        rows.extend(desired)
        output = io.StringIO()
        yaml.dump(workflow, output)
        if not args.dry_run:
            WORKFLOW.write_text(output.getvalue(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
