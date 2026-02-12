# Copyright (C) 2015 SRCE
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import json
import logging
import os
import socket
import time
import traceback

import glanceclient
import glanceclient.exc
import neutronclient.v2_0.client as neutron_client
import novaclient.client as nova_client
from argo_probe_fedcloud import helpers
from novaclient.exceptions import NotFound

# time to sleep between status checks
STATUS_SLEEP_TIME = 10
SERVER_NAME = "cloudmonprobe-servertest"

LOG = logging.getLogger(__name__)


def get_image_from_id(image_id, glance):
    try:
        image = glance.images.get(image_id)
        if image.status == "active":
            return image
    except glanceclient.exc.HTTPNotFound:
        pass
    LOG.debug(f"Image with id {image_id} not found!")
    return None


def get_registry_image(registry_id, glance):
    for image in glance.images.list():
        if image.status != "active":
            continue
        attrs = json.loads(image.get("APPLIANCE_ATTRIBUTES", "{}"))
        if attrs.get("eu.egi.cloud.image_ref", "") == registry_id:
            return image
    LOG.debug("Image with registry_id {registry_id} not found!")
    return None


def get_flavor(flavor_name, nova):
    try:
        return nova.flavors.find(name=flavor_name)
    except NotFound:
        helpers.nagios_out(
            helpers.CRITICAL, f"Could not fetch flavor ID for flavor {flavor_name}"
        )


def get_smaller_flavor(nova):
    flvs = nova.flavors.list(
        detailed=True, min_disk="8", sort_dir="asc", sort_key="vcpus"
    )
    min_cpu = flvs[0].vcpus
    return sorted(filter(lambda x: x.vcpus == min_cpu, flvs), key=lambda x: x.ram).pop(
        0
    )


def wait_for_delete(server_id, vm_timeout, nova):
    try:
        server = nova.servers.get(server_id)
        server.delete()
    except NotFound:
        LOG.debug(f"Server {server_id} is gone, ignoring")
        return True
    return wait_for_status("DELETED", server_id, vm_timeout, nova)


def clean_up(argo_host, vm_timeout, nova):
    for s in nova.servers.list():
        server_mon_host = s.metadata.get("argo-mon-host", "")
        if server_mon_host:
            if server_mon_host == argo_host:
                LOG.debug("Found server from previous run, deleting and aborting!")
                wait_for_delete(s.id, vm_timeout, nova)
                helpers.nagios_out(
                    helpers.WARNING,
                    "Previous run server still runnning, won't continue!",
                )
            else:
                # this is another test
                # we may want to delete it if it's been too long, now we wait for
                # STATUS_SLEEP_TIME so it can get cleaned up by the other server
                LOG.debug(
                    f"Found server from {server_mon_host}, "
                    f"triggering probe anyway after {STATUS_SLEEP_TIME} seconds"
                )
                time.sleep(STATUS_SLEEP_TIME)


def wait_for_status(status, server_id, vm_timeout, nova):
    i = 0
    LOG.debug(f"Check server {server_id} status every {STATUS_SLEEP_TIME}s")
    while i < vm_timeout / STATUS_SLEEP_TIME:
        # server status
        try:
            server = nova.servers.get(server_id)
            LOG.debug(server.status)
            if status in server.status:
                return True
            if "ERROR" in server.status:
                LOG.debug(f"Error from nova: {server.fault}")
                return False
            time.sleep(STATUS_SLEEP_TIME)
        except NotFound:
            if status == "DELETED":
                return True
            else:
                LOG.debug(f"Server {server_id} not found!? retrying")
        except Exception as e:
            LOG.debug(
                f"There was an error checking server {server_id} "
                f"status: {e}, retrying"
            )
        i += 1
    return False
    # this goes out!
    helpers.nagios_out(
        helpers.CRITICAL,
        f"Timeout ({vm_timeout}) exceeded waiting for server {server_id} to be active",
    )
    return False


def create_server(argo_host, image, flavor, network, nova):
    nics = [{"net-id": network}] if network else None
    try:
        server = nova.servers.create(
            name=SERVER_NAME,
            image=image,
            flavor=flavor,
            meta={"argo-mon-host": argo_host},
            nics=nics,
        )
        return server.id
    except Exception as e:
        LOG.debug("Error from server while creating server")
        LOG.debug(e)
        helpers.nagios_out(
            helpers.CRITICAL,
            f"Could not launch server from image {image.id}: {e}",
        )


def get_network_id(project_id, neutron):
    for net in neutron.list_networks()["networks"]:
        if net["status"] == "ACTIVE" and (
            net["project_id"] == project_id or net["tenant_id"] == project_id
        ):
            network_id = net["id"]
            LOG.debug(f"Network id {network_id}")
            return network_id
    else:
        LOG.debug(
            "No tenant-owned network found, hoping VM creation will still work..."
        )
        return None


def novaprobe():
    argnotspec = []
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", dest="endpoint", required=True)
    parser.add_argument("-v", dest="verb", action="count")
    parser.add_argument("--flavor", dest="flavor")
    parser.add_argument("--image", dest="image")
    parser.add_argument("--cert", dest="cert")
    parser.add_argument("--access-token", dest="access_token")
    parser.add_argument("-t", dest="timeout", type=int, default=120)
    parser.add_argument("--vm-timeout", dest="vm_timeout", type=int, default=300)
    parser.add_argument("--registry-image", dest="registry_img")
    parser.add_argument(
        "--identity-provider", dest="identity_provider", default="egi.eu"
    )
    parser.add_argument("--region", dest="region", default=None)
    parser.add_argument("--argo-host-name", dest="argo_host_name", default=None)
    parser.add_argument("--insecure", dest="insecure", action="store_true")

    argholder = parser.parse_args()
    helpers.configure_logging(argholder.verb)

    if argholder.cert is None and argholder.access_token is None:
        helpers.nagios_out(
            helpers.UNKNOWN, "cert or access-token command-line arguments not specified"
        )

    if argholder.image is None and argholder.registry_img is None:
        helpers.nagios_out(
            helpers.UNKNOWN,
            "image or registry_img command-line arguments not specified",
        )

    if argholder.cert and not os.path.isfile(argholder.cert):
        helpers.nagios_out(helpers.UNKNOWN, "cert file does not exist")
    if argholder.access_token and not os.path.isfile(argholder.access_token):
        helpers.nagios_out(helpers.UNKNOWN, "access-token file does not exist")

    LOG.debug(f"Endpoint: {argholder.endpoint}")

    access_token = None
    if argholder.access_token:
        access_file = open(argholder.access_token, "r")
        access_token = access_file.read().rstrip("\n")
        access_file.close()

    argo_host = argholder.argo_host_name
    if not argo_host:
        argo_host = socket.gethostname()
    LOG.debug(f"ARGO Host: {argo_host}")

    region = argholder.region
    if region:
        LOG.debug(f"Region: {region}")

    for auth_class in [helpers.OIDCAuth, helpers.SecretAppCredentialsAuth]:
        # for auth_class in [helpers.SecretAppCredentialsAuth]:
        authenticated = False
        try:
            auth = auth_class(
                endpoint=argholder.endpoint,
                timeout=argholder.timeout,
                verify=not argholder.insecure,
                access_token=access_token,
                identity_provider=argholder.identity_provider,
                userca=argholder.cert,
            )
            auth.authenticate()
            project_id = auth.get_project_id()
            LOG.debug(f"Authenticated with {auth_class.name}")
            authenticated = True
            ks_session = auth.session
        except helpers.AuthenticationException:
            # just go ahead
            LOG.debug("Authentication with %s failed" % auth_class.name)

        if authenticated:
            break
    else:
        helpers.nagios_out(helpers.CRITICAL, "Unable to authenticate against Keystone")

    # get clients
    nova = nova_client.Client("2", region_name=region, session=ks_session)
    glance = glanceclient.Client("2", region_name=region, session=ks_session)
    neutron = neutron_client.Client(region_name=region, session=ks_session)

    LOG.debug("Nova version: %s" % nova.versions.get_current().version)

    if not argholder.image:
        if argholder.registry_img:
            image = get_registry_image(argholder.registry_img, glance)
    else:
        image = get_image_from_id(argholder.image, glance)

    if not image:
        helpers.nagios_out(helpers.CRITICAL, "Could not find an image for the probe")
    LOG.debug(f"Image: {image.id}")

    if not argholder.flavor:
        flavor = get_smaller_flavor(nova)
    else:
        flavor = get_flavor(argholder.flavor, nova)
    LOG.debug(f"Flavor ID: {flavor.id}")

    LOG.debug(project_id)
    network_id = get_network_id(project_id, neutron)

    # remove previous servers if found
    clean_up(argo_host, argholder.vm_timeout, nova)

    # create server
    st = time.time()
    server_id = create_server(argo_host, image, flavor, network_id, nova)
    server_built = wait_for_status("ACTIVE", server_id, argholder.vm_timeout, nova)
    server_createt = round(time.time() - st, 2)

    if server_built:
        LOG.debug(f"Server created in {server_createt:.2f} seconds")

    # server delete
    st = time.time()
    server_deleted = wait_for_delete(server_id, argholder.vm_timeout, nova)
    server_deletet = round(time.time() - st, 2)
    LOG.debug(f"Server={server_id} deleted in %{server_deletet:.2f} seconds")

    if server_built and server_deleted:
        exit_code = helpers.OK
        msg = (
            f"Compute instance={server_id} created ({server_createt:.2f}s) "
            f"and destroyed ({server_deletet:.2f}s)"
        )
    elif server_built:
        exit_code = helpers.CRITICAL
        msg = (
            f"Compute instance={server_id} created ({server_createt:.2f}s) "
            f"but not destroyed ({server_deletet:.2f}s)"
        )
    else:
        exit_code = helpers.CRITICAL
        msg = (
            f"Compute instance={server_id} created with error ({server_createt:.2f}s) "
            f"and destroyed ({server_deletet:.2f}s)"
        )

    helpers.nagios_out(exit_code, msg)


def main():
    try:
        novaprobe()
    except Exception as e:
        LOG.debug(traceback.format_exc())
        helpers.nagios_out(helpers.CRITICAL, f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
