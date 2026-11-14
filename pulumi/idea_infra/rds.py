"""PostgreSQL 17 on RDS (cheapest, private) + owner/app passwords; output `db` is secret."""

import pulumi
import pulumi_aws as aws
import pulumi_random as random

DB_NAME = "ideas"


def create_rds(name, vpc_id, vpc_cidr, subnet_ids, opts, instance_class="db.t4g.micro") -> dict:
    owner = random.RandomPassword("owner", length=32, special=False)
    app = random.RandomPassword("app", length=32, special=False)
    subnets = aws.rds.SubnetGroup("db", name=name, description="Managed by Terraform", subnet_ids=subnet_ids, opts=opts)
    sg = aws.ec2.SecurityGroup(
        "db",
        name=f"{name}-db",
        description="PostgreSQL from inside the VPC",
        vpc_id=vpc_id,
        ingress=[{"from_port": 5432, "to_port": 5432, "protocol": "tcp", "cidr_blocks": [vpc_cidr]}],
        opts=opts,
    )
    db = aws.rds.Instance(
        "db",
        identifier=name,
        engine="postgres",
        engine_version="17",
        instance_class=instance_class,
        allocated_storage=20,
        storage_type="gp3",
        storage_encrypted=True,
        db_name=DB_NAME,
        username="ideas_owner",
        password=owner.result,
        db_subnet_group_name=subnets.name,
        vpc_security_group_ids=[sg.id],
        publicly_accessible=False,
        multi_az=False,
        backup_retention_period=0,
        skip_final_snapshot=True,
        deletion_protection=False,
        apply_immediately=True,
        opts=opts,
    )
    return {
        "endpoint": db.address,
        "db": pulumi.Output.secret({
            "host": db.address,
            "port": db.port,
            "dbname": DB_NAME,
            "owner_username": db.username,
            "owner_password": owner.result,
            "app_username": "ideas_app",
            "app_password": app.result,
        }),
    }
