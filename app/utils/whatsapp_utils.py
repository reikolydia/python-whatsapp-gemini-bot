import logging
from flask import current_app, jsonify
import json
import requests
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

# from app.services.openai_service import generate_response
import re

load_dotenv()
genai.configure(api_key=os.environ["GENAI_API_KEY"])

float_temperature: float = float(0.75)
float_top_p: float = float(1)
float_top_k: int = int(1)
int_max_output_tokens: int = int(2048)
int_max_input_tokens: int = int(2048)

generation_config = {
    "temperature": float_temperature,
    "top_p": float_top_p,
    "top_k": float_top_k,
    "max_output_tokens": int_max_output_tokens,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

mdl = "gemini-pro"

model = genai.GenerativeModel(
    model_name=mdl, generation_config=generation_config, safety_settings=safety_settings
)

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def get_text_message_input(recipient, wa_id, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "context": {"message_id": wa_id},
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

convo = model.start_chat(history=[])
def generate_response(response):

    inp_tokencount = "You sent: " + str(model.count_tokens(response).total_tokens) + " tokens"
    #send_message(get_text_message_input(current_app.config["RECIPIENT_WAID"], inp_tokencount))

    try:
        reply = convo.send_message(response)
        return reply.text
        #send_message(get_text_message_input(current_app.config["RECIPIENT_WAID"], reply.text))
        #oup_tokencount = "AI responded with: " + str(model.count_tokens(convo.history[-1]).total_tokens) + " tokens"
        #send_message(get_text_message_input(current_app.config["RECIPIENT_WAID"], oup_tokencount))

    except BaseException as ex:
        ex_type, ex_value, ex_traceback = sys.exc_info()
        if ex_type.__name__ == "StopCandidateException":
            ex_value2 = str(ex_value).splitlines()
            ex_value3 = str(ex_value2[1]).split()
            error_message = "AI ERROR! " + str(ex_type.__name__) + " : " + str(ex_value3[1])
        else:
            error_message = "ERROR! " + str(ex_type.__name__) + " : " + str(ex_value)
        return error_message
        #send_message(get_text_message_input(current_app.config["RECIPIENT_WAID"], error_message))
        #send_message(get_text_message_input(current_app.config["RECIPIENT_WAID"], "Please try again.."))

    #return response.upper()


def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except (
        requests.RequestException
    ) as e:  # This will catch any general request exception
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        # Process the response as normal
        log_http_response(response)
        return response


def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text


def process_whatsapp_message(body):
    #wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    wa_id = body["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_body = message["text"]["body"]

    # TODO: implement custom function here
    response = generate_response(message_body)
    #response = generate_response(message_body, wa_id)

    # OpenAI Integration
    # response = generate_response(message_body, wa_id, name)
    # response = process_text_for_whatsapp(response)

    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], wa_id, response)
    send_message(data)


def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
