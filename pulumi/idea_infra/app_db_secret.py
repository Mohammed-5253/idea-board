"""App namespace + DB Secrets backend-db (app user) and db-migrate (app + owner)."""

import pulumi
import pulumi_kubernetes as k8s


def create_app_db_secret(db, opts: pulumi.ResourceOptions, namespace: str = "idea-board") -> dict:
    ns = k8s.core.v1.Namespace(
        "app",
        metadata={
            "name": namespace,
            "labels": {
                "pod-security.kubernetes.io/enforce": "restricted",
                "pod-security.kubernetes.io/enforce-version": "latest",
                "pod-security.kubernetes.io/warn": "restricted",
            },
        },
        opts=pulumi.ResourceOptions.merge(
            opts, pulumi.ResourceOptions(ignore_changes=["metadata.labels", "metadata.annotations"])
        ),
    )
    conn = db.apply(lambda d: {
        "DB_HOST": d["host"],
        "DB_PORT": str(d["port"]),
        "DB_NAME": d["dbname"],
        "DB_SSLMODE": "require",
        "DB_USER": d["app_username"],
        "DB_PASSWORD": d["app_password"],
    })
    migrate = pulumi.Output.all(conn, db).apply(lambda a: {
        **a[0],
        "BOOTSTRAP_OWNER_USER": a[1]["owner_username"],
        "BOOTSTRAP_OWNER_PASSWORD": a[1]["owner_password"],
    })
    for res, data in (("backend", ("backend-db", conn)), ("migrate", ("db-migrate", migrate))):
        k8s.core.v1.Secret(
            res,
            metadata={"name": data[0], "namespace": ns.metadata["name"]},
            string_data=pulumi.Output.secret(data[1]),
            opts=opts,
        )
    return {}
