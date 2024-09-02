import os
import json
import logging
import requests
import dataclasses
from datetime import datetime, timedelta
import re
from urllib.parse import unquote, urlparse
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import pandas as pd

DEBUG = os.environ.get("DEBUG", "false")
if DEBUG.lower() == "true":
    logging.basicConfig(level=logging.DEBUG)

AZURE_SEARCH_PERMITTED_GROUPS_COLUMN = os.environ.get(
    "AZURE_SEARCH_PERMITTED_GROUPS_COLUMN"
)

BLOB_CREDENTIAL = os.environ.get("BLOB_CREDENTIAL")
BLOB_ACCOUNT = os.environ.get("BLOB_ACCOUNT")

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


async def format_as_ndjson(r):
    try:
        async for event in r:
            yield json.dumps(event, cls=JSONEncoder) + "\n"
    except Exception as error:
        logging.exception("Exception while generating response stream: %s", error)
        yield json.dumps({"error": str(error)})


def parse_multi_columns(columns: str) -> list:
    if "|" in columns:
        return columns.split("|")
    else:
        return columns.split(",")

def getUserBusinessUnit(userToken):
    endpoint = "https://graph.microsoft.com/v1.0/me?$select=companyName"
    headers = {"Authorization": "Bearer " + userToken}
    try:
        r = requests.get(endpoint, headers=headers)
        if r.status_code != 200:
            logging.error(f"Error fetching user's business unit: {r.status_code} {r.text}")
            return []
        logging.info("Business Unit request:",r.json())
        return r.json()['companyName']
    
    except Exception as e:
        logging.error(f"Exception in getUserBusinessUnit: {e}")
        return []

def fetchUserGroups(userToken, nextLink=None):
    # Recursively fetch group membership
    if nextLink:
        endpoint = nextLink
    else:
        endpoint = "https://graph.microsoft.com/v1.0/me/transitiveMemberOf?$select=id"

    headers = {"Authorization": "bearer " + userToken}
    try:
        r = requests.get(endpoint, headers=headers)
        if r.status_code != 200:
            logging.error(f"Error fetching user groups: {r.status_code} {r.text}")
            return []

        r = r.json()
        if "@odata.nextLink" in r:
            nextLinkData = fetchUserGroups(userToken, r["@odata.nextLink"])
            r["value"].extend(nextLinkData)

        return r["value"]
    except Exception as e:
        logging.error(f"Exception in fetchUserGroups: {e}")
        return []


def generateFilterString(userToken):
    # Get list of groups user is a member of
    userGroups = fetchUserGroups(userToken)

    # Construct filter string
    if not userGroups:
        logging.debug("No user groups found")

    group_ids = ", ".join([obj["id"] for obj in userGroups])
    return f"{AZURE_SEARCH_PERMITTED_GROUPS_COLUMN}/any(g:search.in(g, '{group_ids}'))"

def generate_SAS(url):
    container, blob = split_url(url)
    blob_service_client =BlobServiceClient(BLOB_ACCOUNT, credential=BLOB_CREDENTIAL)
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob)

    sas_token_expiry_time = datetime.utcnow() + timedelta(hours=1)  # 1 hour from now

    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=blob_client.container_name,
        blob_name=blob_client.blob_name,
        account_key=BLOB_CREDENTIAL,
        permission=BlobSasPermissions(read=True),
        expiry=sas_token_expiry_time
    )

    return sas_token

def split_url(url):
    url_decoded = unquote(url)
    if url_decoded.endswith('/'):
        url_decoded = url_decoded[:-1]
    pattern = fr"{BLOB_ACCOUNT}/([^/]+)/(.+)"
    match = re.search(pattern, url_decoded)
    container = match.group(1)
    blob = match.group(2)
    return container, blob

def remove_SAS_token(url):
    parsed_url = urlparse(url)
    url_without_query = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
    return url_without_query

def append_SAS_to_image_link(content):
    # pattern = r'!\[[^)]+)]\((https://[^)]+)\)'
    pattern = r'!\[(.*?)\]\((.*?)\)'
    def url_replacer(match):
        original_url = match.group(2)
        generated_string = generate_SAS(original_url)
        return f"![{match.group(1)}]({original_url}?{generated_string})"
    replaced_text = re.sub(pattern, url_replacer, content)
    return replaced_text

def remove_SAS_from_image_link(content):    
    pattern = r'!\[(.*?)\]\((.*?)\)'
    def url_replacer(match):
        original_url = match.group(2)
        url_cleaned = remove_SAS_token(original_url)
        return f"![{match.group(1)}]({url_cleaned})"
    replaced_text = re.sub(pattern, url_replacer, content)
    return replaced_text

def format_non_streaming_response(chatCompletion, history_metadata, apim_request_id):
    response_obj = {
        "id": chatCompletion.id,
        "model": chatCompletion.model,
        "created": chatCompletion.created,
        "object": chatCompletion.object,
        "choices": [{"messages": []}],
        "history_metadata": history_metadata,
        "apim-request-id": apim_request_id,
    }

    if len(chatCompletion.choices) > 0:
        message = chatCompletion.choices[0].message
        if message:
            if hasattr(message, "context"):
                content = message.context
                for i, chunk in enumerate(content["citations"]):
                    content["citations"][i]["url"]=chunk["url"]+"?"+generate_SAS(chunk["url"])
                response_obj["choices"][0]["messages"].append(
                    {
                        "role": "tool",
                        "content": json.dumps(content),
                    }
                )
            response_obj["choices"][0]["messages"].append(
                {
                    "role": "assistant",
                    "content": append_SAS_to_image_link(message.content),
                }
            )
            return response_obj

    return {}

def format_stream_response(chatCompletionChunk, history_metadata, apim_request_id):
    response_obj = {
        "id": chatCompletionChunk.id,
        "model": chatCompletionChunk.model,
        "created": chatCompletionChunk.created,
        "object": chatCompletionChunk.object,
        "choices": [{"messages": []}],
        "history_metadata": history_metadata,
        "apim-request-id": apim_request_id,
    }

    if len(chatCompletionChunk.choices) > 0:
        delta = chatCompletionChunk.choices[0].delta
        if delta:
            if hasattr(delta, "context"):
                content = delta.context
                for i, chunk in enumerate(content["citations"]):
                    content["citations"][i]["url"]=chunk["url"]+"?"+generate_SAS(chunk["url"])
                messageObj = {
                    "role": "tool", 
                    "content": json.dumps(content)
                }
                response_obj["choices"][0]["messages"].append(messageObj)
                return response_obj
            if delta.role == "assistant" and hasattr(delta, "context"):
                messageObj = {
                    "role": "assistant",
                    "context": delta.context
                }
                response_obj["choices"][0]["messages"].append(messageObj)
                return response_obj
            else:
                if delta.content:
                    messageObj = {
                        "role": "assistant",
                        "content": delta.content 
                    }
                    response_obj["choices"][0]["messages"].append(messageObj)
                    return response_obj

    return {}


def format_pf_non_streaming_response(
    chatCompletion, history_metadata, response_field_name, message_uuid=None
):
    if chatCompletion is None:
        logging.error(
            "chatCompletion object is None - Increase PROMPTFLOW_RESPONSE_TIMEOUT parameter"
        )
        return {
            "error": "No response received from promptflow endpoint increase PROMPTFLOW_RESPONSE_TIMEOUT parameter or check the promptflow endpoint."
        }
    if "error" in chatCompletion:
        logging.error(f"Error in promptflow response api: {chatCompletion['error']}")
        return {"error": chatCompletion["error"]}

    logging.debug(f"chatCompletion: {chatCompletion}")
    try:
        response_obj = {
            "id": chatCompletion["id"],
            "model": "",
            "created": "",
            "object": "",
            "choices": [
                {
                    "messages": [
                        {
                            "role": "assistant",
                            "content": chatCompletion[response_field_name],
                        }
                    ]
                }
            ],
            "history_metadata": history_metadata,
        }
        return response_obj
    except Exception as e:
        logging.error(f"Exception in format_pf_non_streaming_response: {e}")
        return {}


def convert_to_pf_format(input_json, request_field_name, response_field_name):
    output_json = []
    logging.debug(f"Input json: {input_json}")
    # align the input json to the format expected by promptflow chat flow
    for message in input_json["messages"]:
        if message:
            if message["role"] == "user":
                new_obj = {
                    "inputs": {request_field_name: message["content"]},
                    "outputs": {response_field_name: ""},
                }
                output_json.append(new_obj)
            elif message["role"] == "assistant" and len(output_json) > 0:
                output_json[-1]["outputs"][response_field_name] = message["content"]
    logging.debug(f"PF formatted response: {output_json}")
    return output_json

def get_category_data(url):
    new_url = url+"?"+generate_SAS(url)
    categories_df = pd.read_excel(new_url,'CategoryMapping')
    examples_df = pd.read_excel(new_url,'Examples')
    subcategories = examples_df.to_json(orient='records')
    categories = categories_df.to_json(orient='records')

    return categories, subcategories

def get_query_category(prompt, client, model, message):
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "assistant", 
                "content": prompt
            },    
            {
                "role": "user",
                "content": message,
            },
        ],
        max_tokens=20,
        temperature=0,
        top_p=0,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
    )

    try:
        result = completion.choices[0].message.content.split(', ',2)
        category = result[0].split('Category: ',1)[1].replace('.','')
        subcategory = result[1].split('Subcategory: ',1)[1].replace('.','')
    except:
        category = 'Category: Other'
        subcategory = 'Subcategory: Other'

    return category, subcategory