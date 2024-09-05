import msal
import os
import requests
import logging

def get_authenticated_user_details(request_headers):
    user_object = {}

    ## check the headers for the Principal-Id (the guid of the signed in user)
    if "X-Ms-Client-Principal-Id" not in request_headers.keys():
        ## if it's not, assume we're in development mode and return a default user
        from . import sample_user
        raw_user_object = sample_user.sample_user
    else:
        ## if it is, get the user details from the EasyAuth headers
        raw_user_object = {k:v for k,v in request_headers.items()}

    user_object['user_principal_id'] = raw_user_object.get('X-Ms-Client-Principal-Id')
    user_object['user_name'] = raw_user_object.get('X-Ms-Client-Principal-Name')
    user_object['auth_provider'] = raw_user_object.get('X-Ms-Client-Principal-Idp')
    user_object['auth_token'] = raw_user_object.get('X-Ms-Token-Aad-Id-Token')
    user_object['client_principal_b64'] = raw_user_object.get('X-Ms-Client-Principal')
    user_object['aad_id_token'] = raw_user_object.get('X-Ms-Token-Aad-Id-Token')

    return user_object

def get_access_token():
    try:
        tenantID = os.environ.get("TENANT_ID")
        authority = 'https://login.microsoftonline.com/' + tenantID
        clientID = os.environ.get("CLIENT_ID")
        clientSecret = os.environ.get("CLIENT_SECRET")
        scope = ['https://graph.microsoft.com/.default']
        app = msal.ConfidentialClientApplication(clientID, authority=authority, client_credential = clientSecret)
        access_token = app.acquire_token_for_client(scopes=scope)
        token = access_token['access_token']
        logging.info('Access token from function: '+token)
    except:
        logging.error("Error getting access token.")
        token = []

        return token

def get_user_business_unit(token):
    endpoint = "https://graph.microsoft.com/v1.0/me?$select=companyName"
    headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
    }

    try:
        r = requests.get(endpoint, headers=headers)
        if r.status_code != 200:
            logging.error(f"Error fetching user's business unit: {r.status_code} {r.text}")
            logging.info(headers)
            return []
        return r.json()['companyName']

    except Exception as e:
        logging.error(f"Exception in getUserBusinessUnit: {e}")
        return []