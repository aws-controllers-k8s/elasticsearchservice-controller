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

"""Cleans up the resources created by the bootstrapping process.
"""

import boto3
import logging

from acktest import resources
from acktest.aws import identity

from e2e import bootstrap_directory
from e2e.bootstrap_resources import TestBootstrapResources


def delete_subnet(subnet_id: str):
    region = identity.get_region()
    ec2 = boto3.client("ec2", region_name=region)

    ec2.delete_subnet(SubnetId=subnet_id)

    logging.info(f"Deleted VPC Subnet {subnet_id}")


def delete_vpc(vpc_id: str):
    region = identity.get_region()
    ec2 = boto3.client("ec2", region_name=region)

    ec2.delete_vpc(VpcId=vpc_id)

    logging.info(f"Deleted VPC {vpc_id}")


def delete_service_linked_role(slr_name: str):
    region = identity.get_region()
    iam = boto3.client("iam", region_name=region)
    
    iam.delete_service_linked_role(RoleName=slr_name)

    # NOTE(jaypipes): delete-service-linked-role returns a "DeletionTaskId"
    # that you can use to "check on" the status of your deletion request using
    # a separate get-service-linked-role-deletion-status command. Yes, that is
    # actually the name of the command...
    #
    # Perhaps add some waiter here that checks on the deletion status. For now,
    # just assume the request eventually succeeded.

    logging.info(f"Deleted service-linked role {slr_name}")

def service_cleanup(config: dict):
    logging.getLogger().setLevel(logging.INFO)

    resources = TestBootstrapResources(
        **config
    )

    for subnet in resources.VPCSubnetIDs:
        try:
            delete_subnet(subnet)
        except:
            logging.exception(f"Unable to delete VPC subnet {subnet}")

    try:
        delete_vpc(resources.VPCID)
    except:
        logging.exception(f"Unable to delete VPC {resources.VPCID}")

    try:
        delete_service_linked_role(resources.ServiceLinkedRoleName)
    except:
        logging.exception(f"Unable to delete SLR {resources.ServiceLinkedRoleName}")


if __name__ == "__main__":   
    bootstrap_config = resources.read_bootstrap_config(bootstrap_directory)
    service_cleanup(bootstrap_config) 
