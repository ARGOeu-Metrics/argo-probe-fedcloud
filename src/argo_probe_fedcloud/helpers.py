import os
import sys
from typing import List
from urllib.parse import urlparse

from keystoneauth1 import session
from keystoneauth1.exceptions.base import ClientException
from keystoneauth1.identity import v3
from keystoneclient.v3 import client

strerr = ""
num_excp_expand = 0
extra_out: List[str] = []
verbose = False


class AuthenticationException(Exception):
    pass


def nagios_out(status, msg, retcode):
    sys.stdout.write(status + ": " + msg + "\n")
    global extra_out
    global verbose
    if extra_out and verbose:
        sys.stdout.write("\n".join(extra_out))
    sys.exit(retcode)


def debug(msg, newline=True):
    global verbose
    if not verbose:
        return
    msg = str(msg)
    global extra_out
    if newline:
        extra_out.append(msg)
    else:
        if not extra_out:
            extra_out.append("")
        extra_out[-1] = " ".join((extra_out[-1], msg))


class BaseAuth(object):
    def __init__(self, host, timeout, verify=True, **kwargs):
        self.parsed_url = urlparse(host)
        self.timeout = timeout
        self.verify = verify
        if self.parsed_url.scheme != "https":
            raise AuthenticationException(
                "Connection error %s - Probe expects HTTPS endpoint"
                % (self.parsed_url.scheme + "://" + self.parsed_url.netloc)
            )
        s = self.parsed_url.path.rstrip("/")
        if s.endswith("v2.0"):
            raise AuthenticationException(
                "Probe does not support Keystone v2.0 endpoints"
            )
            s = os.path.dirname(s)
        self.auth_url = host
        self.session = None

    def get_unscoped_token(self):
        raise NotImplementedError

    def get_ops_tenant(self):
        raise NotImplementedError

    def get_scoped_token(self, project):
        raise NotImplementedError

    def authenticate(self):
        self.get_unscoped_token()
        project = self.get_ops_tenant()
        return self.get_scoped_token(project)

    def get_info(self, region=None):
        raise NotImplementedError

    def get_swift_endpoint(self, region=None):
        raise NotImplementedError


class BaseV3Auth(BaseAuth):
    def get_ops_tenant(self):
        keystone = client.Client(session=self.session)
        projects = keystone.auth.projects()
        for p in projects:
            if "ops" in p.name:
                return p
        else:
            return projects.pop()

    def get_scoped_token(self, project):
        try:
            self.session.invalidate()
            self.session.auth.project_id = project.id
            return self.session.get_token()
        except ClientException as e:
            raise AuthenticationException(
                f"Could not fetch scoped keystone token for {project}: {errmsg_from_excp(e)}"
            )

    def get_project_id(self):
        # FIXME: region needs to be checked here!
        return self.session.auth.project_id

    def get_swift_endpoint(self, region=None):
        # FIXME: region needs to be checked here!
        swift = self.session.get_endpoint(
            service_type="object-store", region_name=region
        )
        return self.session.auth.project_id, swift


class OIDCAuth(BaseV3Auth):
    name = "OpenID Connect"

    def __init__(
        self,
        host,
        timeout,
        verify=False,
        identity_provider="egi.eu",
        access_token="",
        **kwargs,
    ):
        super(OIDCAuth, self).__init__(host, timeout, verify, **kwargs)
        self.identity_provider = identity_provider
        self.access_token = access_token

    def get_unscoped_token(self):
        for p in ["openid", "oidc"]:
            try:
                self.protocol = p
                auth = v3.OidcAccessToken(
                    auth_url=self.auth_url,
                    identity_provider=self.identity_provider,
                    access_token=self.access_token,
                    protocol=self.protocol,
                )
                self.session = session.Session(
                    auth=auth, verify=self.verify, timeout=self.timeout
                )
                return self.session.get_token()
            except ClientException as e:
                debug("OIDC Auth failed with protocol %s (%s)" % (p, e))
        raise AuthenticationException("Unable to authenticate")


def errmsg_from_excp(e, level=5):
    global strerr, num_excp_expand
    return str(e)
    if isinstance(e, Exception) and getattr(e, "args", False):
        num_excp_expand += 1
        if not errmsg_from_excp(e.args):
            return strerr
    elif isinstance(e, dict):
        for s in e.iteritems():
            errmsg_from_excp(s)
    elif isinstance(e, list):
        for s in e:
            errmsg_from_excp(s)
    elif isinstance(e, tuple):
        for s in e:
            errmsg_from_excp(s)
    elif isinstance(e, str):
        if num_excp_expand <= level:
            strerr += e + " "
