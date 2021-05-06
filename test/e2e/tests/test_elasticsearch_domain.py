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

"""Integration tests for the ElasticsearchService API ElasticsearchDomain
resource
"""

import boto3
import datetime
import pytest
import logging
import time
from typing import Dict

from acktest.k8s import resource as k8s

from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_resource
from e2e.replacement_values import REPLACEMENT_VALUES

RESOURCE_PLURAL = 'elasticsearchdomains'

DELETE_WAIT_AFTER_SECONDS = 20
CREATE_INTERVAL_SLEEP_SECONDS = 15
# Time to wait before we get to an expected RUNNING state.
# In my experience, it regularly takes more than 6 minutes to create a
# single-instance RabbitMQ broker...
CREATE_TIMEOUT_SECONDS = 600


@pytest.fixture(scope="module")
def es_client():
    return boto3.client('es')


# TODO(jaypipes): Move to k8s common library
def get_resource_arn(self, resource: Dict):
    assert 'ackResourceMetadata' in resource['status'] and \
        'arn' in resource['status']['ackResourceMetadata']
    return resource['status']['ackResourceMetadata']['arn']


@service_marker
@pytest.mark.canary
class TestDomain:
    def test_create_delete_7_9(self, es_client):
        resource_name = "my-es-domain"

        replacements = REPLACEMENT_VALUES.copy()
        replacements["DOMAIN_NAME"] = resource_name

        resource_data = load_resource(
            "domain_es7.9",
            additional_replacements=replacements,
        )
        logging.error(resource_data)

        # Create the k8s resource
        ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
            resource_name, namespace="default",
        )
        k8s.create_custom_resource(ref, resource_data)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        assert cr is not None
        assert k8s.get_resource_exists(ref)

        logging.info(cr)

        # Let's check that the domain appears in AES
        aws_res = es_client.describe_elasticsearch_domain(DomainName=resource_name)
        assert aws_res is not None

        now = datetime.datetime.now()
        timeout = now + datetime.timedelta(seconds=CREATE_TIMEOUT_SECONDS)

        # TODO(jaypipes): Move this into generic AWS-side waiter
        while aws_res['Created'] != True:
            if datetime.datetime.now() >= timeout:
                raise Exception("failed to find created ES Domain before timeout")
            time.sleep(CREATE_INTERVAL_SLEEP_SECONDS)
            aws_res = es_client.describe_elasticsearch_domain(DomainName=resource_name)
            assert aws_res is not None

        # Delete the k8s resource on teardown of the module
        k8s.delete_custom_resource(ref)

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Domain should no longer appear in AES
        res_found = False
        try:
            es_client.describe_elasticsearch_domain(DomainName=resource_name)
            res_found = True
        except es_client.exceptions.NotFoundException:
            pass

        assert res_found is False
