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
import os
import socket
import time
import traceback

import glanceclient
import neutronclient.v2_0.client as neutron_client
import novaclient.client as nova_client
from argo_probe_fedcloud import helpers
from novaclient.exceptions import NotFound

# time to sleep between status checks
STATUS_SLEEP_TIME = 10
SERVER_NAME = "cloudmonprobe-servertest"


def get_image(appdb_id, glance):
    for image in glance.images.list():
        if image.get("ad:appid", "") == appdb_id:
            return image
        # TODO: this is to be deprecated as sites move to newer cloudkeeper
        attrs = json.loads(image.get("APPLIANCE_ATTRIBUTES", "{}"))
        if attrs.get("ad:appid", "") == appdb_id:
            return image
    helpers.nagios_out(
        "Critical", "Could not find image ID for AppDB image %s" % appdb_id, 2
    )


def get_flavor(flavor_name, nova):
    try:
        return nova.flavors.find(name=flavor_name)
    except NotFound:
        helpers.nagios_out(
            "Critical", f"Could not fetch flavor ID for flavor {flavor_name}", 2
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
    server = nova.servers.get(server_id)
    server.delete()
    return wait_for_status("DELETED", server_id, vm_timeout, nova)


def clean_up(argo_host, vm_timeout, nova):
    for s in nova.servers.list():
        server_mon_host = s.metadata.get("argo-mon-host", "")
        if server_mon_host:
            if server_mon_host == argo_host:
                helpers.debug("Found server from previous run, deleting and aborting!")
                wait_for_delete(s.id, vm_timeout, nova)
                helpers.nagios_out(
                    "Warning",
                    "Previous run server still runnning, won't continue!",
                    1,
                )
            else:
                # this is another nagios test
                # we may want to delete it if it's been too long
                helpers.debug(f"Found server from {server_mon_host}, "
                              "triggering probe anyway")


def wait_for_status(status, server_id, vm_timeout, nova):
    i = 0
    helpers.debug(f"Check server {server_id} status every {STATUS_SLEEP_TIME}s")
    while i < vm_timeout / STATUS_SLEEP_TIME:
        # server status
        try:
            server = nova.servers.get(server_id)
            helpers.debug(server.status, False)
            if status in server.status:
                return True
            if "ERROR" in server.status:
                helpers.debug(f"Error from nova: {server.fault}")
                return False
            time.sleep(STATUS_SLEEP_TIME)
        except NotFound:
            if status == "DELETED":
                return True
            else:
                helpers.debug(f"Server {server_id} not found!? retrying")
        except Exception as e:
            helpers.debug(
                f"There was an error checking server {server_id} "
                f"status: {helpers.errmsg_from_excp(e)}, retrying"
            )
        i += 1
    return False
    # this goes out!
    helpers.nagios_out(
        "Critical",
        f"Timeout ({vm_timeout}) exceeded waiting for server {server_id} to be active",
        2,
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
        helpers.debug("Error from server while creating server")
        helpers.debug(e)
        helpers.nagios_out(
            "Critical",
            f"Could not launch server from image {image.id}: {helpers.errmsg_from_excp(e)}",
            2,
        )


def get_network_id(project_id, neutron):
    for net in neutron.list_networks()["networks"]:
        if net["status"] == "ACTIVE" and net["project_id"] == project_id:
            network_id = net["id"]
            helpers.debug("Network id: %s" % network_id)
            return network_id
    else:
        helpers.debug(
            "No tenant-owned network found, hoping VM creation will still work..."
        )
        return None


def novaprobe():
    argnotspec = []
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", dest="endpoint", nargs="?")
    parser.add_argument("-v", dest="verb", action="store_true")
    parser.add_argument("--flavor", dest="flavor", nargs="?")
    parser.add_argument("--image", dest="image", nargs="?")
    parser.add_argument("--cert", dest="cert", nargs="?")
    parser.add_argument("--access-token", dest="access_token", nargs="?")
    parser.add_argument("-t", dest="timeout", type=int, nargs="?", default=120)
    parser.add_argument(
        "--vm-timeout", dest="vm_timeout", type=int, nargs="?", default=300
    )
    parser.add_argument("--appdb-image", dest="appdb_img", nargs="?")
    parser.add_argument(
        "--identity-provider", dest="identity_provider", default="egi.eu", nargs="?"
    )
    parser.add_argument("--region", dest="region", default=None, nargs="?")
    parser.add_argument(
        "--argo-host-name", dest="argo_host_name", default=None, nargs="?"
    )
    parser.add_argument("--insecure", dest="insecure", action="store_true")

    argholder = parser.parse_args()
    helpers.verbose = argholder.verb

    for arg in ["endpoint", "timeout"]:
        if eval("argholder." + arg) is None:
            argnotspec.append(arg)

    if argholder.cert is None and argholder.access_token is None:
        helpers.nagios_out(
            "Unknown", "cert or access-token command-line arguments not specified", 3
        )

    if argholder.image is None and argholder.appdb_img is None:
        helpers.nagios_out(
            "Unknown", "image or appdb-image command-line arguments not specified", 3
        )

    if len(argnotspec) > 0:
        msg_error_args = ""
        for arg in argnotspec:
            msg_error_args += "%s " % (arg)
        helpers.nagios_out(
            "Unknown", "command-line arguments not specified, " + msg_error_args, 3
        )
    else:
        if not argholder.endpoint.startswith("http"):
            helpers.nagios_out("Unknown", "command-line arguments are not correct", 3)
        if argholder.cert and not os.path.isfile(argholder.cert):
            helpers.nagios_out("Unknown", "cert file does not exist", 3)
        if argholder.access_token and not os.path.isfile(argholder.access_token):
            helpers.nagios_out("Unknown", "access-token file does not exist", 3)

    ks_token = None
    access_token = None
    if argholder.access_token:
        access_file = open(argholder.access_token, "r")
        access_token = access_file.read().rstrip("\n")
        access_file.close()

    region = argholder.region

    argo_host = argholder.argo_host_name
    if not argo_host:
        argo_host = socket.gethostname()

    for auth_class in [helpers.OIDCAuth]:
        # , helpers.SecretAppCredentialsAuth]:
        authenticated = False
        try:
            auth = auth_class(
                argholder.endpoint,
                argholder.timeout,
                verify=not argholder.insecure,
                access_token=access_token,
                identity_provider=argholder.identity_provider,
                userca=argholder.cert,
            )
            ks_token = auth.authenticate()
            tenant_id = auth.get_project_id()
            helpers.debug("Authenticated with %s" % auth_class.name)
            authenticated = True
            ks_session = auth.session
            break
        except helpers.AuthenticationException:
            # just go ahead
            helpers.debug("Authentication with %s failed" % auth_class.name)

        if authenticated:
            break
    else:
        helpers.nagios_out("Critical", "Unable to authenticate against Keystone", 2)

    helpers.debug("Endpoint: %s" % argholder.endpoint)
    if region:
        helpers.debug("Region: %s" % region)
    helpers.debug("Auth token (cut to 64 chars): %.64s" % ks_token)
    helpers.debug("Project OPS, ID: %s" % tenant_id)

    # get clients
    nova = nova_client.Client("2", region_name=region, session=ks_session)
    glance = glanceclient.Client("2", region_name=region, session=ks_session)
    neutron = neutron_client.Client(region_name=region, session=ks_session)

    helpers.debug("Nova version: %s" % nova.versions.get_current().version)

    if not argholder.image:
        image = get_image(argholder.appdb_img, glance)
    else:
        image = argholder.image

    helpers.debug("Image: %s" % image.id)

    if not argholder.flavor:
        flavor = get_smaller_flavor(nova)
    else:
        flavor = get_flavor(argholder.flavor, nova)
    helpers.debug("Flavor ID: %s" % flavor.id)

    network_id = get_network_id(tenant_id, neutron)

    # remove previous servers if found
    clean_up(argo_host, argholder.vm_timeout, nova)

    # create server
    st = time.time()
    server_id = create_server(argo_host, image, flavor, network_id, nova)
    server_built = wait_for_status("ACTIVE", server_id, argholder.vm_timeout, nova)
    server_createt = round(time.time() - st, 2)

    if server_built:
        helpers.debug("\nServer created in %.2f seconds" % (server_createt))

    # server delete
    st = time.time()
    server_deleted = wait_for_delete(server_id, argholder.vm_timeout, nova)
    server_deletet = round(time.time() - st, 2)
    helpers.debug("\nServer=%s deleted in %.2f seconds" % (server_id, server_deletet))

    if server_built and server_deleted:
        helpers.nagios_out(
            "OK",
            "Compute instance=%s created(%.2fs) and destroyed(%.2fs)"
            % (server_id, server_createt, server_deletet),
            0,
        )
    elif server_built:
        # Built but not deleted
        helpers.nagios_out(
            "Critical",
            "Compute instance=%s created (%.2fs) but not destroyed(%.2fs)"
            % (server_id, server_createt, server_deletet),
            2,
        )
    else:
        # not built but deleted
        helpers.nagios_out(
            "Critical",
            "Compute instance=%s created with error(%.2fs) and destroyed(%.2fs)"
            % (server_id, server_createt, server_deletet),
            2,
        )


def main():
    try:
        novaprobe()
    except Exception as e:
        helpers.debug(traceback.format_exc())
        helpers.nagios_out("Critical", "Unexpected error: %s" % e, 2)


if __name__ == "__main__":
    main()
