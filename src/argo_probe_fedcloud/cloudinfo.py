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
from datetime import datetime
from urllib.parse import urlparse, urlunparse

import requests
from argo_probe_fedcloud import helpers


def get_endpoint_info_from_appdb(appdb_endpoint, appdb_cache, appdb_cache_ttl):
    """Fetch required data from AppDB IS GraphQL API for all endpoints
    and cache them in a file. If the cache has not expired, serve the data
    from the file upon the next request, otherwise, refetch from the API
    """
    data = None
    fetched = False
    try:
        if os.path.exists(appdb_cache):
            if time.time() - os.path.getmtime(appdb_cache) < appdb_cache_ttl:
                f = open(appdb_cache)
                data = json.load(f)
                f.close()
    except (OSError, IOError) as e:
        helpers.debug("Error while reading AppDB API response from cache file %s" % e)

    if data is None:
        try:
            helpers.debug("Querying AppDB for endpoints")
            url = "/".join([appdb_endpoint, "graphql"])
            query = """
{
siteCloudComputingEndpoints{
  items{
    endpointURL
    shares: shareList {
      VO
      entityCreationTime
    }
  }
}
}
"""
            params = {"query": query}
            r = requests.get(url, params=params, headers={"accept": "application/json"})
            r.raise_for_status()
            data = r.json()["data"]["siteCloudComputingEndpoints"]["items"]
            fetched = True
        except requests.exceptions.RequestException as e:
            msg = "Could not get info from AppDB: %s" % e
            helpers.nagios_out("Unknown", msg, 3)
        except (IndexError, ValueError):
            return None
    if fetched:
        try:
            f = open(appdb_cache, "w")
            json.dump(data, f)
            f.close()
        except (OSError, IOError) as e:
            helpers.debug("Error while saving AppDB API response to cache file %s" % e)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--endpoint", dest="endpoint", required=True)
    parser.add_argument("-v", dest="verb", action="store_true")
    parser.add_argument("-t", dest="timeout", type=int, default=120)
    parser.add_argument("--appdb-endpoint", default="https://is.appdb.egi.eu")
    parser.add_argument("--warning-treshold", type=int, default=1)
    parser.add_argument("--critical-treshold", type=int, default=5)
    parser.add_argument(
        "--appdb-cache", dest="appdb_cache", default="/tmp/appdbcache.json"
    )
    parser.add_argument(
        "--appdb-cache-ttl", dest="appdb_cache_ttl", type=int, default="600"
    )
    opts = parser.parse_args()

    if opts.verb:
        helpers.verbose = True

    endpoints = get_endpoint_info_from_appdb(
        opts.appdb_endpoint, opts.appdb_cache, opts.appdb_cache_ttl
    )

    search_endpoint = opts.endpoint
    vos = None

    for endpoint in endpoints:
        if endpoint["endpointURL"] == search_endpoint:
            vos = endpoint["shares"]
            break

    if vos is None:
        # ARGO adds the port even if it's not originally in GOC, so try to
        # find the endpoint without it if it's HTTPS/443
        parsed = urlparse(search_endpoint)
        if parsed[0] == "https" and parsed[1].endswith(":443"):
            helpers.debug("Retry query with no port in URL")
            search_endpoint = urlunparse(
                (parsed[0], parsed[1][:-4], parsed[2], parsed[3], parsed[4], parsed[5])
            )
            for endpoint in endpoints:
                if endpoint["endpointURL"] == search_endpoint:
                    vos = endpoint["shares"]
                    break

    if vos is None:
        msg = "Could not get info from AppDB about endpoint %s" % search_endpoint
        helpers.nagios_out("Critical", msg, 2)

    # Now check how old the information is
    # TODO: check if all the expected VOs are present
    today = datetime.today()
    for vo in vos:
        # entityCreationTime has the date where the info was produced
        # should look like "2020-12-14T10:50:56.773201"
        # will produce a Warning if the info is older than 1 day
        # or critical if older than 5 days
        updated = datetime.strptime(vo["entityCreationTime"][:16], "%Y-%m-%dT%H:%M")
        helpers.debug("VO %(VO)s updated by %(entityCreationTime)s" % vo)
        diff_days = ((today - updated).total_seconds()) / (60 * 60 * 24.0)
        if diff_days > opts.critical_treshold:
            msg = "VO %s info is older than %s days" % (
                vo["VO"],
                opts.critical_treshold,
            )
            helpers.nagios_out("Critical", msg, 2)
        elif diff_days > opts.warning_treshold:
            msg = "VO %s info is older than %s days" % (vo["VO"], opts.warning_treshold)
            helpers.nagios_out("Warning", msg, 1)

    helpers.nagios_out("OK", "Endpoint publishing up to date information for VOs", 0)


if __name__ == "__main__":
    main()
