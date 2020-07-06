"""
Custom Authenticator to use Auth0 OAuth with JupyterHub

Derived using the Github and Google OAuthenticator implementations as examples.

The following environment variables may be used for configuration:

    AUTH0_DOMAIN- Your domain_name, can be custom domain as well
    OAUTH_CLIENT_ID - Your client id
    OAUTH_CLIENT_SECRET - Your client secret
    OAUTH_CALLBACK_URL - Your callback handler URL

Additionally, if you are concerned about your secrets being exposed by
an env dump(I know I am!) you can set the client_secret, client_id and
oauth_callback_url directly on the config for Auth0OAuthenticator.

One instance of this could be adding the following to your jupyterhub_config.py :

  c.Auth0OAuthenticator.client_id = 'YOUR_CLIENT_ID'
  c.Auth0OAuthenticator.client_secret = 'YOUR_CLIENT_SECRET'
  c.Auth0OAuthenticator.oauth_callback_url = 'YOUR_CALLBACK_URL'
  c.Auth0OAuthenticator.scope = ['openid','profile','email']

If you are using the environment variable config, all you should need to
do is define them in the environment then add the following line to 
jupyterhub_config.py :

  c.JupyterHub.authenticator_class = 'oauthenticator.auth0.Auth0OAuthenticator'

"""

import json
import os

from tornado.auth import OAuth2Mixin
from tornado import web
from tornado.httpclient import HTTPRequest, AsyncHTTPClient

from traitlets import Unicode, default

from jupyterhub.auth import LocalAuthenticator

from .oauth2 import OAuthLoginHandler, OAuthenticator


class Auth0OAuthenticator(OAuthenticator):

    login_service = "Auth0"

    auth0_domain = Unicode(config=True)
           
    @default("auth0_domain")
    def _generate_auth0_domain(self):
        domain = os.getenv("AUTH0_DOMAIN")
        if not domain:
            raise ValueError(
                "Please specify $AUTH0_DOMAIN env or %s.auth0_domain config"
                % self.__class__.__name__
            )
        if not self.auth0_domain.endswith(".com"):
            self.auth0_domain = f"{self.auth0_domain}.auth0.com"
            
    @default("authorize_url")
    def _authorize_url_default(self):
        return "https://%s/authorize" % self.auth0_domain

    @default("token_url")
    def _token_url_default(self):
        return "https://%s/oauth/token" % self.auth0_domain

    async def authenticate(self, handler, data=None):
        code = handler.get_argument("code")
        # TODO: Configure the curl_httpclient for tornado
        http_client = AsyncHTTPClient()

        params = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.get_callback_url(handler),
        }
        url = self.token_url

        req = HTTPRequest(
            url,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(params),
        )

        resp = await http_client.fetch(req)
        resp_json = json.loads(resp.body.decode('utf8', 'replace'))

        access_token = resp_json['access_token']

        # Determine who the logged in user is
        headers = {
            "Accept": "application/json",
            "User-Agent": "JupyterHub",
            "Authorization": "Bearer {}".format(access_token),
        }
        req = HTTPRequest(
            "https://%s/userinfo" % self.auth0_domain,
            method="GET",
            headers=headers,
        )
        resp = await http_client.fetch(req)
        resp_json = json.loads(resp.body.decode('utf8', 'replace'))

        return {
            'name': resp_json["email"],
            'auth_state': {'access_token': access_token, 'auth0_user': resp_json},
        }


class LocalAuth0OAuthenticator(LocalAuthenticator, Auth0OAuthenticator):

    """A version that mixes in local system user creation"""

    pass
