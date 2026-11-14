"""VPC + subnets + single NAT: what terraform-aws-modules/vpc 6.7.3 creates for our inputs."""

import ipaddress

import pulumi
import pulumi_aws as aws


def cidrsubnet(cidr: str, newbits: int, netnum: int) -> str:
    net = ipaddress.ip_network(cidr)
    return str(list(net.subnets(prefixlen_diff=newbits))[netnum])


def create_vpc(name: str, cidr: str, az_count: int, opts: pulumi.ResourceOptions) -> dict:
    azs = aws.get_availability_zones_output(
        state="available", opts=pulumi.InvokeOptions(provider=opts.provider)
    ).names.apply(lambda n: n[:az_count])
    public_cidrs = [cidrsubnet(cidr, 8, i) for i in range(az_count)]
    private_cidrs = [cidrsubnet(cidr, 4, i + 1) for i in range(az_count)]

    vpc = aws.ec2.Vpc(
        f"{name}-vpc",
        cidr_block=cidr,
        enable_dns_hostnames=True,
        enable_dns_support=True,
        instance_tenancy="default",
        tags={"Name": name},
        opts=opts,
    )
    igw = aws.ec2.InternetGateway(f"{name}-igw", vpc_id=vpc.id, tags={"Name": name}, opts=opts)

    public = []
    for i, c in enumerate(public_cidrs):
        az = azs.apply(lambda a, i=i: a[i])
        public.append(
            aws.ec2.Subnet(
                f"{name}-public-{i}",
                vpc_id=vpc.id,
                cidr_block=c,
                availability_zone=az,
                map_public_ip_on_launch=False,
                tags=az.apply(
                    lambda a: {"Name": f"{name}-public-{a}", "kubernetes.io/role/elb": "1"}
                ),
                opts=opts,
            )
        )
    private = []
    for i, c in enumerate(private_cidrs):
        az = azs.apply(lambda a, i=i: a[i])
        private.append(
            aws.ec2.Subnet(
                f"{name}-private-{i}",
                vpc_id=vpc.id,
                cidr_block=c,
                availability_zone=az,
                tags=az.apply(
                    lambda a: {"Name": f"{name}-private-{a}", "kubernetes.io/role/internal-elb": "1"}
                ),
                opts=opts,
            )
        )

    public_rt = aws.ec2.RouteTable(
        f"{name}-public", vpc_id=vpc.id, tags={"Name": f"{name}-public"}, opts=opts
    )
    aws.ec2.Route(
        f"{name}-public-igw",
        route_table_id=public_rt.id,
        destination_cidr_block="0.0.0.0/0",
        gateway_id=igw.id,
        opts=opts,
    )
    for i, s in enumerate(public):
        aws.ec2.RouteTableAssociation(
            f"{name}-public-{i}", subnet_id=s.id, route_table_id=public_rt.id, opts=opts
        )

    nat_name = azs.apply(lambda a: {"Name": f"{name}-{a[0]}"})
    after_igw = pulumi.ResourceOptions.merge(opts, pulumi.ResourceOptions(depends_on=[igw]))
    eip = aws.ec2.Eip(f"{name}-nat", domain="vpc", tags=nat_name, opts=after_igw)
    nat = aws.ec2.NatGateway(
        f"{name}-nat", allocation_id=eip.id, subnet_id=public[0].id, tags=nat_name, opts=after_igw
    )

    private_rt = aws.ec2.RouteTable(
        f"{name}-private", vpc_id=vpc.id, tags={"Name": f"{name}-private"}, opts=opts
    )
    aws.ec2.Route(
        f"{name}-private-nat",
        route_table_id=private_rt.id,
        destination_cidr_block="0.0.0.0/0",
        nat_gateway_id=nat.id,
        opts=opts,
    )
    for i, s in enumerate(private):
        aws.ec2.RouteTableAssociation(
            f"{name}-private-{i}", subnet_id=s.id, route_table_id=private_rt.id, opts=opts
        )

    # Module defaults: manage (and lock down / reset) the VPC's default SG, NACL, route table.
    aws.ec2.DefaultSecurityGroup(
        f"{name}-default", vpc_id=vpc.id, ingress=[], egress=[],
        tags={"Name": f"{name}-default"}, opts=opts,
    )
    allow = [
        {"rule_no": 100, "action": "allow", "from_port": 0, "to_port": 0, "protocol": "-1",
         "cidr_block": "0.0.0.0/0"},
        {"rule_no": 101, "action": "allow", "from_port": 0, "to_port": 0, "protocol": "-1",
         "ipv6_cidr_block": "::/0"},
    ]
    aws.ec2.DefaultNetworkAcl(
        f"{name}-default",
        default_network_acl_id=vpc.default_network_acl_id,
        ingress=allow,
        egress=allow,
        tags={"Name": f"{name}-default"},
        opts=pulumi.ResourceOptions.merge(opts, pulumi.ResourceOptions(ignore_changes=["subnetIds"])),
    )
    aws.ec2.DefaultRouteTable(
        f"{name}-default",
        default_route_table_id=vpc.default_route_table_id,
        routes=[],
        tags={"Name": f"{name}-default"},
        opts=opts,
    )
    return {
        "vpc_id": vpc.id,
        "private_subnet_ids": [s.id for s in private],
        "public_subnet_ids": [s.id for s in public],
    }
