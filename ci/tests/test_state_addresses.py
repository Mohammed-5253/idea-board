"""ci/state_addresses.py prints `terraform state list` lines and never attribute values.

Run: python3 -m pytest ci/tests
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "state_addresses.py"
SECRET = "do-not-print-me"


def run(state: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT)],
        input=json.dumps(state), capture_output=True, text=True,
    )


def res(type_, name, keys, module=None, mode="managed"):
    r = {"mode": mode, "type": type_, "name": name, "provider": "p",
         "instances": [{"attributes": {"password": SECRET}, **({} if k is None else {"index_key": k})}
                       for k in keys]}
    if module:
        r["module"] = module
    return r


def test_addresses_like_state_list():
    state = {"version": 4, "outputs": {"pw": {"value": SECRET}}, "resources": [
        res("aws_vpc", "this", [None], module='module.vpc.module.vpc'),
        res("aws_subnet", "private", [0, 1], module="module.vpc.module.vpc"),
        res("terraform_data", "k", ["a", 'q"x', "d${y}", "p%{z}", "b\\s"]),
        res("aws_availability_zones", "az", [None], mode="data"),
        res("terraform_data", "inner", [None], module='module.m["a b"]'),
    ]}
    r = run(state)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == sorted([
        "module.vpc.module.vpc.aws_vpc.this",
        "module.vpc.module.vpc.aws_subnet.private[0]",
        "module.vpc.module.vpc.aws_subnet.private[1]",
        'terraform_data.k["a"]',
        'terraform_data.k["q\\"x"]',
        'terraform_data.k["d$${y}"]',
        'terraform_data.k["p%%{z}"]',
        'terraform_data.k["b\\\\s"]',
        "data.aws_availability_zones.az",
        'module.m["a b"].terraform_data.inner',
    ])
    assert SECRET not in r.stdout + r.stderr


def test_empty_and_bad_input():
    assert run({"version": 4, "resources": []}).stdout == ""
    bad = run({"version": 3, "modules": [{"secret": SECRET}]})
    assert bad.returncode == 1 and SECRET not in bad.stdout + bad.stderr
