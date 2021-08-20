# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.
"""Bootstraps the resources required to run the Elasticsearch Service
integration tests.
"""

import boto3
import logging
import time

from acktest.aws import identity
from acktest import resources

from e2e import bootstrap_directory
from e2e.bootstrap_resources import (
    TestBootstrapResources,
    VPC_CIDR_BLOCK,
    VPC_SUBNET_CIDR_BLOCK,
)


def create_vpc(ec2) -> str:
    logging.debug(f"Creating VPC with CIDR {VPC_CIDR_BLOCK}")

    resp = ec2.create_vpc(
        CidrBlock=VPC_CIDR_BLOCK,
    )
    vpc_id = resp['Vpc']['VpcId']

    # TODO(jaypipes): Put a proper waiter here...
    time.sleep(3)

    vpcs = ec2.describe_vpcs(VpcIds=[vpc_id])
    if len(vpcs['Vpcs']) != 1:
        raise RuntimeError(
            f"failed to describe VPC we just created '{vpc_id}'",
        )

    vpc = vpcs['Vpcs'][0]
    vpc_state = vpc['State']
    if vpc_state != "available":
        raise RuntimeError(
            f"VPC we just created '{vpc_id}' is not available. current state: {vpc_state}",
        )

    logging.info(f"Created VPC {vpc_id}")

    return vpc_id


def create_subnet(ec2, vpc_id: str, az: str, cidr: str) -> str:
    resp = ec2.create_subnet(
        CidrBlock=cidr,
        VpcId=vpc_id,
        AvailabilityZone=az,
    )
    subnet_id = resp['Subnet']['SubnetId']

    # TODO(jaypipes): Put a proper waiter here...
    time.sleep(3)

    subnets  = ec2.describe_subnets(SubnetIds=[subnet_id])
    if len(subnets['Subnets']) != 1:
        raise RuntimeError(
            f"failed to describe subnet we just created '{subnet_id}'",
        )

    subnet = subnets['Subnets'][0]
    subnet_state = subnet['State']
    if subnet_state != "available":
        raise RuntimeError(
            f"Subnet we just created '{subnet_id}' is not available. current state: {subnet_state}",
        )

    logging.info(f"Created VPC Subnet {subnet_id}")

    return subnet_id


def create_service_linked_role(iam) -> str:
    # TODO(jaypipes): There does not seem to be any way at all to list or
    # describe service-linked-roles in IAM. So, the only way to make this work
    # is just to check for an error when trying to create the service linked
    # role to see if one with the same name already "has been taken in this
    # account" (whatever that means).
    #
    # Once again, IAM proves why we can't have nice things.
    try:
        resp = iam.create_service_linked_role(
            AWSServiceName="es.amazonaws.com",
            Description="An SLR to allow Amazon Elasticsearch Service to work within a private VPC.",
        )
        slr_name = resp['Role']['RoleName']

        logging.info(f"Created service-linked role {slr_name}")

    except iam.exceptions.InvalidInputException as e:
        if "Service role name AWSServiceRoleForAmazonElasticsearchService has been taken in this account" in str(e):
            logging.info(f"Service-linked role AWSServiceRoleForAmazonElasticsearchService already exists")
            return "AWSServiceRoleForAmazonElasticsearchService"
        raise e
    return slr_name


def service_bootstrap() -> dict:
    logging.getLogger().setLevel(logging.INFO)

    region = identity.get_region()
    ec2 = boto3.client("ec2", region_name=region)
    iam = boto3.client("iam", region_name=region)
    # only normal zones, no localzones
    azs = map(lambda zone: zone['ZoneName'],
            filter(lambda zone: zone['OptInStatus'] == 'opt-in-not-required', ec2.describe_availability_zones()['AvailabilityZones']))

    vpc_id = create_vpc(ec2)
    subnets = [create_subnet(ec2, vpc_id, az, cidr) for (cidr,az) in zip(VPC_SUBNET_CIDR_BLOCK, azs)]
    slr_name = create_service_linked_role(iam)

    return TestBootstrapResources(
        vpc_id,
        subnets,
        slr_name,
    ).__dict__


if __name__ == "__main__":
    config = service_bootstrap()
    resources.write_bootstrap_config(config, bootstrap_directory)
