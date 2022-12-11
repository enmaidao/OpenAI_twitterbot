# Import necessary packages
import tweepy
import openai
from config import bearer_token, consumer_key, consumer_secret, access_token, access_token_secret, openai_api_key
import requests
import os
import json
from requests_oauthlib import OAuth1Session
import time
import traceback
import re

# Authenticate with the Twitter API using the API keys and tokens
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)
Client = tweepy.Client(bearer_token, consumer_key, consumer_secret, access_token, access_token_secret)

# Set up the ChatGPT model
openai.api_key = openai_api_key

#Twitter Account
account = "enmai114"

#Auth&Setting
def bearer_oauth(r):
    r.headers["Authorization"] = f"Bearer {bearer_token}"
    r.headers["User-Agent"] = "v2FilteredStreamPython"
    return r

def get_rules():
    response = requests.get(
        "https://api.twitter.com/2/tweets/search/stream/rules", auth=bearer_oauth
    )
    if response.status_code != 200:
        raise Exception(
            "Cannot get rules (HTTP {}): {}".format(response.status_code, response.text)
        )
    print(json.dumps(response.json()))
    return response.json()

def delete_all_rules(rules):
    if rules is None or "data" not in rules:
        return None

    ids = list(map(lambda rule: rule["id"], rules["data"]))
    payload = {"delete": {"ids": ids}}
    response = requests.post(
        "https://api.twitter.com/2/tweets/search/stream/rules",
        auth=bearer_oauth,
        json=payload
    )
    if response.status_code != 200:
        raise Exception(
            "Cannot delete rules (HTTP {}): {}".format(
                response.status_code, response.text
            )
        )
    print(json.dumps(response.json()))

#Add rules
def set_rules(delete,account):
    rules = [
        {
            "value":f"to:{account} -from:{account}"
        },
        {
            "value":f"{account} has:mentions -from:{account}"
        }
    ]
    payload = {"add": rules}
    response = requests.post(
        "https://api.twitter.com/2/tweets/search/stream/rules",
        auth=bearer_oauth,
        json=payload,
    )
    if response.status_code != 201:
        raise Exception(
            "Cannot add rules (HTTP {}): {}".format(response.status_code, response.text)
        )
    print(json.dumps(response.json()))

#Streaming
def get_stream(headers):
    run = 1
    while run:
        try:
            with requests.get(
                "https://api.twitter.com/2/tweets/search/stream", auth=bearer_oauth, stream=True,
            ) as response:
                print(response.status_code)
                if response.status_code != 200:
                    raise Exception(
                        "Cannot get stream (HTTP {}): {}".format(
                            response.status_code, response.text
                        )
                    )
                for response_line in response.iter_lines():
                    if response_line:
                        json_response = json.loads(response_line)
                        tweet_id = json_response["data"]["id"]
                        reply_text = json_response["data"]["text"]

                        #Get conversation_id
                        with requests.get(
                            f"https://api.twitter.com/2/tweets?ids={tweet_id}&tweet.fields=author_id,conversation_id", auth=bearer_oauth,
                        ) as response:
                            if response.status_code != 200:
                                raise Exception(
                                    "Cannot get stream (HTTP {}): {}".format(
                                        response.status_code, response.text
                                    )
                                )
                            for response_line in response.iter_lines():
                                json_response = json.loads(response_line)
                                # print(json_response)
                                conversation_id = json_response["data"][0]["conversation_id"]
                                print(conversation_id)
                        
                        #Get conversations in the same sread
                        with requests.get(
                            f"https://api.twitter.com/2/tweets/search/recent?query=conversation_id:{conversation_id}&tweet.fields=in_reply_to_user_id,author_id,created_at,conversation_id", auth=bearer_oauth,
                        ) as response:
                            if response.status_code != 200:
                                raise Exception(
                                    "Cannot get stream (HTTP {}): {}".format(
                                        response.status_code, response.text
                                    )
                                )
                            for response_line in response.iter_lines():
                                json_response = json.loads(response_line)
                                # print(json_response)
                                conversations_num = json_response['meta']['result_count']
                                conversations_sread = ""
                                for j in range(conversations_num):
                                    conversations_sread = conversations_sread + str(json_response["data"][j]['text'])
                        
                        # Generate a reply using the openai chatgpt model
                        reply_text = f"「{conversations_sread}」この括弧内に会話があればその経緯や状況を考慮しつつ、@{account}風の話し方で「{reply_text}」に対する返事を「」と@を使わずにしてください。"

                        response = openai.Completion.create(
                            engine="text-davinci-003",
                            prompt=reply_text,
                            max_tokens=500,
                            temperature=0.9,
                            top_p=1,
                            frequency_penalty=0.0,
                            presence_penalty=0.6
                        )
                        text = ""
                        text = response["choices"][0]["text"]

                        n = 135 
                        l = [text[i:i+n] for i in range(0,len(text), n)]
                        l[0] = re.sub("^.*\n", "", l[0])

                        print(response)
                        print(reply_text)

                        if len(l) == 1:
                            text = l[0].replace('\n', '')

                            print(text)
                            print("============================")
                            
                            Client.create_tweet(
                            text=text,
                            in_reply_to_tweet_id =tweet_id)
                        else:
                            for i in range(len(l)):
                                _text = l[i].replace('\n', '')
                                text = f"{i+1}/{len(l)}\n" + _text
                                
                                print(text)
                                print("============================")

                                Client.create_tweet(
                                text=text,
                                in_reply_to_tweet_id =tweet_id)
                            time.sleep(20)

        except ChunkedEncodingError as chunkError:
            print(traceback.format_exc())
            time.sleep(6)
            continue
        
        except ConnectionError as e:
            print(traceback.format_exc())
            run+=1
            if run <10:
                time.sleep(6)
                print("再接続します",run+"回目")
                continue
            else:
                run=0

        except ConnectionResetError as e:
            print(traceback.format_exc())
            run+=1
            if run <10:
                time.sleep(6)
                print("再接続します",run+"回目")
                continue
            else:
                run=0
            
        except Exception as e:
            # some other error occurred.. stop the loop
            print("Stopping loop because of un-handled error")
            print(traceback.format_exc())
            run = 0
	    
class ChunkedEncodingError(Exception):
    pass

def main():
    rules = get_rules()
    delete = delete_all_rules(rules)
    set = set_rules(delete,account)
    get_stream(set)
    # time.sleep(60)
 
if __name__ == "__main__":
    main()
