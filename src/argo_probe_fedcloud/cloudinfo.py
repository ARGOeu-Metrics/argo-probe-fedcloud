# Copyright (C) 2021 EGI Foundation
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
import time
from urllib.parse import urlparse, urlunparse

import requests
from argo_probe_fedcloud import helpers


def get_sites_data_from_is(is_endpoint, is_cache, is_cache_ttl):
    """Fetch required data from IS API for all endpoints
    and cache them in a file. If the cache has not expired, serve the data
    from the file upon the next request, otherwise, refetch from the API
    """
    data = None
    fetched = False
    try:
        if os.path.exists(is_cache):
            if time.time() - os.path.getmtime(is_cache) < is_cache_ttl:
                f = open(is_cache)
                data = json.load(f)
                f.close()
    except (OSError, IOError) as e:
        helpers.debug(f"Error while reading IS API response from cache file: {e}")

    if data is None:
        try:
            helpers.debug("Querying IS for endpoints")
            url = "/".join([is_endpoint, "sites/"])
            params = {"include_projects": True}
            r = requests.get(url, params=params, headers={"accept": "application/json"})
            r.raise_for_status()
            data = r.json()
            fetched = True
        except requests.exceptions.RequestException as e:
            msg = f"Could not get info from IS: {e}"
            helpers.nagios_out("Unknown", msg, 3)
        except (IndexError, ValueError):
            return None
    if fetched:
        try:
            f = open(is_cache, "w")
            json.dump(data, f)
            f.close()
        except (OSError, IOError) as e:
            helpers.debug(f"Error while saving IS API response to cache file {e}")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--endpoint", dest="endpoint", required=True)
    parser.add_argument("-v", dest="verb", action="store_true")
    parser.add_argument("-t", dest="timeout", type=int, default=120)
    parser.add_argument("--is-endpoint", default="https://is.cloud.egi.eu")
    parser.add_argument("--is-cache", dest="is_cache", default="/tmp/cloud_is.json")
    parser.add_argument("--is-cache-ttl", dest="is_cache_ttl", type=int, default="600")
    opts = parser.parse_args()

    if opts.verb:
        helpers.verbose = True

    sites = get_sites_data_from_is(opts.is_endpoint, opts.is_cache, opts.is_cache_ttl)

    search_endpoint = opts.endpoint

    site_info = None
    for site in sites:
        if site["url"] == search_endpoint:
            site_info = site
            break

    if site_info is None:
        # ARGO adds the port even if it's not originally in GOC, so try to
        # find the endpoint without it if it's HTTPS/443
        parsed = urlparse(search_endpoint)
        if parsed[0] == "https" and parsed[1].endswith(":443"):
            helpers.debug("Retry query with no port in URL")
            search_endpoint = urlunparse(
                (parsed[0], parsed[1][:-4], parsed[2], parsed[3], parsed[4], parsed[5])
            )
            for site in sites:
                if site["url"] == search_endpoint:
                    site_info = site
                    break

    if site_info is None:
        msg = f"Could not get info from IS about endpoint {search_endpoint}"
        helpers.nagios_out("Critical", msg, 2)

    # TODO: check if all the expected VOs are present
    vos = site_info.get("projects")
    if not vos:
        helpers.nagios_out(
            "Warning", f"No VOs available on IS about endpoint {search_endpoint}", 1
        )

    helpers.nagios_out(
        "OK", f"Endpoint publishing up to date information for {len(vos)} VOs", 0
    )


if __name__ == "__main__":
    main()
