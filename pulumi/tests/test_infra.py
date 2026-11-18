"""Run the program under Pulumi mocks and check the key settings of each module."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNNER = r'''
import json, runpy, sys
import pulumi
from pulumi.runtime.stack import wait_for_rpcs
from pulumi.runtime.sync_await import _sync_await

seen = []
calls = []

class Mocks(pulumi.runtime.Mocks):
    def new_resource(self, args):
        state = dict(args.inputs)
        if args.typ == "random:index/randomPassword:RandomPassword":
            state["result"] = "pw-" + args.name
        if args.typ == "aws:rds/instance:Instance":
            state.update(address="db.example", port=5432)
        seen.append({"type": args.typ, "inputs": args.inputs})
        return [args.name + "_id", state]

    def call(self, args):
        if args.token.endswith("getAvailabilityZones"):
            return {"names": ["a-1a", "a-1b", "a-1c"]}
        if args.token == "aws:iam/getOpenIdConnectProvider:getOpenIdConnectProvider":
            calls.append({"token": args.token, "args": dict(args.args)})
            return {"arn": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com",
                    "url": args.args.get("url")}
        return {"id": "x", "dnsName": "alb.example"}

pulumi.runtime.set_mocks(Mocks(), project="idea-board-aws", stack="test", preview=False)
pulumi.runtime.set_all_config({f"idea-board-aws:{k}": v for k, v in json.loads(sys.argv[1]).items()})
error = None
try:
    runpy.run_path("__main__.py", run_name="__main__")
    _sync_await(wait_for_rpcs())
except Exception as exc:
    error = str(exc)
print(json.dumps({"resources": seen, "calls": calls, "error": error}, default=str))
'''


def run(**config):
    cfg = {"kubeconfig": "apiVersion: v1", **config}
    out = subprocess.run(
        [sys.executable, "-c", RUNNER, json.dumps(cfg)],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out.strip().splitlines()[-1])


def plain(v):
    """Drop Pulumi's secret wrapper ({<sig>: ..., "value": v}) from mock inputs."""
    if isinstance(v, dict):
        if "value" in v and len(v) == 2:
            return plain(v["value"])
        return {k: plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [plain(x) for x in v]
    return v


def of(r, typ):
    return [plain(x["inputs"]) for x in r["resources"] if x["type"] == typ]


def test_vpc_subnets_and_defaults():
    r = run()
    assert r["error"] is None
    cidrs = sorted(s["cidrBlock"] for s in of(r, "aws:ec2/subnet:Subnet"))
    assert cidrs == ["10.10.0.0/24", "10.10.1.0/24", "10.10.16.0/20", "10.10.32.0/20"]
    assert len(of(r, "aws:ec2/natGateway:NatGateway")) == 1
    assert of(r, "aws:ec2/defaultNetworkAcl:DefaultNetworkAcl")
    assert of(r, "aws:ec2/defaultRouteTable:DefaultRouteTable")


def test_ecr_oidc_rds_secrets():
    r = run()
    assert {x["name"] for x in of(r, "aws:ecr/repository:Repository")} == {
        "idea-board/backend", "idea-board/frontend"}
    (role,) = of(r, "aws:iam/role:Role")
    cond = json.loads(role["assumeRolePolicy"])["Statement"][0]["Condition"]["StringEquals"]
    assert cond["token.actions.githubusercontent.com:sub"].endswith(":ref:refs/heads/main")
    # The OIDC provider belongs to terraform/bootstrap/aws: looked up, never created.
    assert not of(r, "aws:iam/openIdConnectProvider:OpenIdConnectProvider")
    assert [c["args"]["url"] for c in r["calls"]] == ["https://token.actions.githubusercontent.com"]
    principal = json.loads(role["assumeRolePolicy"])["Statement"][0]["Principal"]["Federated"]
    assert principal == "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    (db,) = of(r, "aws:rds/instance:Instance")
    assert db["engineVersion"] == "17" and db["username"] == "ideas_owner"
    secrets = {s["metadata"]["name"]: s["stringData"] for s in of(r, "kubernetes:core/v1:Secret")}
    assert secrets["backend-db"]["DB_PASSWORD"] == "pw-app"
    assert secrets["db-migrate"]["BOOTSTRAP_OWNER_PASSWORD"] == "pw-owner"


def test_cloudfront_toggle_and_validation():
    assert not of(run(), "aws:cloudfront/distribution:Distribution")
    on = run(enable_cloudfront="true")
    (dist,) = of(on, "aws:cloudfront/distribution:Distribution")
    assert dist["orderedCacheBehaviors"][0]["pathPattern"] == "/api/*"
    bad = run(enable_cloudfront="true", cloudfront_default_ttl="10", cloudfront_max_ttl="1")
    assert "TTLs must satisfy" in bad["error"]


def test_remote_backend_and_kms_secrets():
    project = (ROOT / "Pulumi.yaml").read_text()
    assert "url: s3://idea-board-tfstate-326435482847/pulumi?region=ap-south-1" in project
    stack = (ROOT / "Pulumi.prod.yaml").read_text()
    assert "secretsprovider: awskms://alias/idea-board-pulumi?region=ap-south-1" in stack
