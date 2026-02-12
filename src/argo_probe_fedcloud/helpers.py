import hashlib
import io
import logging
import os
import sys
from urllib.parse import urlparse

import hvac
import requests
from hvac.exceptions import VaultError
from keystoneauth1 import session
from keystoneauth1.exceptions.base import ClientException
from keystoneauth1.identity import v3
from keystoneclient.v3 import client

logger_stream = io.StringIO()
LOG = logging.getLogger(__name__)

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3


def configure_logging(verbose=0):
    level = logging.DEBUG if verbose > 1 else logging.INFO
    logging.basicConfig(
        level=level,
        handlers=[logging.StreamHandler(logger_stream)],
        force=True,
        format="%(asctime)s %(levelname).1s - %(message)s",
    )
    if verbose:
        logging.getLogger("argo_probe_fedcloud").setLevel(logging.DEBUG)


def nagios_out(exit_code, msg):
    status_map = {
        OK: "OK",
        WARNING: "Warning",
        CRITICAL: "Critical",
        UNKNOWN: "Unknown",
    }
    status = status_map.get(exit_code, "Unknown")
    LOG.debug(f"Exit code: {exit_code} - {status} - {msg}")
    sys.stdout.write(f"{status}: {msg}\n")
    sys.stdout.write(logger_stream.getvalue())
    sys.exit(exit_code)


def warning(msg=""):
    nagios_out(WARNING, msg)


def ok(msg=""):
    nagios_out(OK, msg)


def critical(msg=""):
    nagios_out(CRITICAL, msg)


def unknown(msg=""):
    nagios_out(UNKNOWN, msg)


class AuthenticationException(Exception):
    pass


class BaseV3Auth:
    """Common class for Keystone V3 Authentication"""

    def __init__(self, endpoint="", timeout=120, verify=True, **kwargs):
        if urlparse(endpoint).scheme != "https":
            raise AuthenticationException(
                "Probe expects HTTPS endpoint instead of {endpoint}, aborting"
            )
        self.endpoint = endpoint
        self.timeout = timeout
        self.verify = verify
        self.session = None

    def _get_keystone_v3(self, version_info):
        try:
            for mt in version_info["media-types"]:
                if mt["type"] == "application/vnd.openstack.identity-v3+json":
                    for link in version_info["links"]:
                        if link["rel"] == "self":
                            return link["href"]
        except KeyError:
            # bad json, we ignore
            pass
        return None

    def _discover_keystone(self):
        # discover the V3 endpoint
        auth_url = ""
        try:
            r = requests.get(self.endpoint)
            # if not authenticated and has a header, X-xxx-xxx. then use that one header
            if r.status_code == 222:
                keystone_endpoint = r.headers["X-xxx-xxx"]
                self._discover_keystone(keystone_endpoint)
            else:
                server_info = r.json()
                if "versions" in server_info:
                    for v in server_info["versions"]["values"]:
                        auth_url = self._get_keystone_v3(v)
                        if auth_url:
                            break
                elif "version" in server_info:
                    auth_url = self._get_keystone_v3(server_info["version"])
        except Exception:
            raise AuthenticationException("Cannot discover the Keystone API endpoint")
        self.auth_url = auth_url

    def _get_authenticated(self):
        raise NotImplementedError

    def authenticate(self):
        self._discover_keystone()
        self._get_authenticated()

    def get_project_id(self):
        return self.session.get_project_id()

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
        identity_provider="egi.eu",
        access_token="",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.identity_provider = identity_provider
        self.access_token = access_token

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
            token = self.session.get_token()
            LOG.debug(f"Auth token (SHA256): {hashlib.sha256(token.encode())}")
        except ClientException as e:
            raise AuthenticationException(
                f"Could not fetch scoped keystone token for {project}: {e}"
            )

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
                if self.session.get_token():
                    return
            except ClientException as e:
                LOG.debug(f"OIDC Auth failed with protocol {p} {e}")
        raise AuthenticationException("Unable to authenticate")

    def _get_authenticated(self):
        self.get_unscoped_token()
        project = self.get_ops_tenant()
        LOG.debug("Project OPS, ID: %s" % project.id)
        self.get_scoped_token(project)


class SecretAppCredentialsAuth(BaseV3Auth):
    name = "Secret Store Application Credentials"
    vault_url = "https://vault.services.fedcloud.eu:8200"
    vault_role = ""
    vault_mount_point = "/secrets/"
    vault_path_base = (
        "users/529a87e5ce04cd5ddd7161734d02df0e2199a11452430803e714cb1309cc3907@egi.eu"
    )

    def __init__(self, access_token="", **kwargs):
        super().__init__(**kwargs)
        self.access_token = access_token

    def _get_authenticated(self):
        """Get an unscoped token using application credentials

        It goes to secrets store and get the credentials for the
        host (auth_url) we are trying to authenticate against.
        The secret store should contain all needed params, so we can
        easily adapt to different sites without touching the code
        in general this should be: `application_credential_id`
        and `application_credential_secret`.

        The app credentials should be actually scoped to a project
        so we will also store this project_id for scoping later on
        """
        appcred_args = {}
        try:
            client = hvac.Client(url=self.vault_url)
            client.auth.jwt.jwt_login(role="", jwt=self.access_token)
            keystone_host = urlparse(self.auth_url).netloc.split(":", 1)[0]
            secret_path = os.path.join(self.vault_path_base, keystone_host)
            appcred_args = client.secrets.kv.v1.read_secret(
                path=secret_path,
                mount_point="/secrets/",
            )
        except VaultError as e:
            msg = f"Unable to get secret for {self.auth_url}: {e}"
            raise AuthenticationException(msg)

        # 2. Authenticate with that into the site
        try:
            auth = v3.ApplicationCredential(
                auth_url=self.auth_url,
                **appcred_args["data"],
            )
            self.session = session.Session(
                auth=auth, verify=self.verify, timeout=self.timeout
            )
            token = self.session.get_token()
            LOG.debug("Project OPS, ID: %s" % self.session.get_project_id())
            LOG.debug(f"Auth token (SHA256): {hashlib.sha256(token.encode())}")
        except ClientException as e:
            LOG.debug(f"Authentication failed: {e}")
            raise AuthenticationException(f"Unable to authenticate: {e}")
