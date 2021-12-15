import requests
import time
import tweepy
import secrets_keys as sk
import os
import json
import utilities as ut

# If you are getting many error response code from the request
# and the bot is failing because of this then please increase this number
request_try = 10
image_name = "nft_image.png"

# Get this from your Twitter development account (not in repo)
# and you need to add them to secrets_keys.py file in your cloned repo
consumer_token = sk.consumer_token
consumer_secret = sk.consumer_secret
key = sk.key
secret = sk.secret

# All the etherscan related URLs
etherscan_base_url = "https://etherscan.io/tx/"
etherscan_eth_prices = "https://api.etherscan.io/api?module=stats&action=ethprice&apikey="
etherscan_url_transfers = "https://api.etherscan.io/api?module=account&action=tokennfttx&contractaddress="
etherscan_url_tx = "https://api.etherscan.io/api?module=account&action=txlistinternal&txhash="

# URL of the latest transfer in etherscan for a defined contract [ERC-721]
# you need to have the Token contract number (contract_number) and your etherscan Api-Key Token
# (etherscan_key) and add them to secrets_keys.py file
# For reference visit https://etherscan.io/apis
url_transfers = etherscan_url_transfers+sk.contract_number + \
    "&page=1&offset=1&sort=desc&apikey="+sk.etherscan_key
headers_req = {'Accept': 'application/json'}

# Seed for the bot to start (latest Txn Hash from Etherscan)
# or you can leave this value empty if you are running the bot for
# the first time
past_tx = ""
latest_tx = ""

# Run the Bot til the infinite
while True:

    sum_price = 0
    # Make a request to get the latest transfer.
    # Try request_try times in case any exception is throw
    for _ in range(request_try):
        try:
            r_asset = requests.post(url_transfers, headers=headers_req)
            r_json = r_asset.json()
            r_asset.close()
            break
        except (ConnectionResetError, requests.exceptions.RequestException, json.decoder.JSONDecodeError):
            print("Response code---> ", r_asset.status_code,
                  "\n", "Response text---> ", r_asset.text)
            time.sleep(2)

    try:
        # Need to extract the Txn Hash and token of the latest Transfer
        # from etherscan
        Txn_Hash = r_json["result"][0]["hash"]
    except IndexError:
        print("IndexError: ", r_json)
        continue

    latest_tx = Txn_Hash
    from_address = str(r_json["result"][0]["from"])
    to_address = str(r_json["result"][0]["to"])
    token_id = str(r_json["result"][0]["tokenID"])
    filter_address = [from_address, to_address]
    if sk.nftx_vault_address in filter_address:
        time.sleep(2)
        continue

    url_txhash = etherscan_url_tx+str(Txn_Hash)+"&apikey="+sk.etherscan_key

    # Make a request to get the Txn Hash details.
    # Try request_try times in case any exception is throw
    for _ in range(request_try):
        try:
            # Make a request to the extracted Txn Hash from the latest Transfer
            hash_details = requests.post(url_txhash)
            r_json_details = hash_details.json()
            hash_details.close()
            break
        except (ConnectionResetError, requests.exceptions.RequestException, json.decoder.JSONDecodeError):
            print("Response code---> ", hash_details.status_code,
                  "\n", "Response text---> ", hash_details.text)
            time.sleep(2)

    # Here we check if the current Transaction/Sale is already posted.
    # For this we have captured the previous transaction.
    if latest_tx != past_tx:
        past_tx = latest_tx
        # There can be multiple transactions for one Transfer, so we iterate in the response
        # to get all the transactions and add all the 'values' in each transaction on the Txn Hash
        if r_json_details["status"] != "0" and "value" in r_json_details["result"][-1]:
            # Some magic to get all the 'values' and add them to get the real price of
            # the Transfer/Token/NFT in ETH
            for transaction in r_json_details["result"]:
                asset_price_api = str(transaction["value"])
                price_size = len(asset_price_api)
                asset_dec_int = 18

                if price_size < asset_dec_int:
                    diff = asset_dec_int - price_size
                    for n in range(diff):
                        asset_price_api = '0' + asset_price_api

                    asset_price_api = "."+asset_price_api

                    for idx, val in enumerate(reversed(asset_price_api)):
                        if val != "0":
                            if idx == 0:
                                asset_price = asset_price_api
                            else:
                                asset_price = asset_price_api[:-idx]
                            break
                else:
                    asset_price = round(
                        float(
                            asset_price_api[: price_size - asset_dec_int] + "." +
                            asset_price_api[price_size - asset_dec_int:]),
                        6)

                sum_price = float(asset_price) + sum_price

            # Final price(cost) of the Transfer in ETH rounded to 6 decimal
            final_price_eth = round(float(sum_price), 6)
            if final_price_eth < 0.4:
                continue

            # Make a request to get the ETH current prices (ETH/BTC).
            # Try request_try times in case any exception is throw
            for _ in range(request_try):
                try:
                    # Get the current prices of ETH (BTC/USD)
                    eth_prices = requests.post(
                        etherscan_eth_prices+sk.etherscan_key)
                    eth_prices_json = eth_prices.json()
                    break
                except (ConnectionResetError, requests.exceptions.RequestException, json.decoder.JSONDecodeError):
                    print("Response code---> ", eth_prices.status_code,
                          "\n", "Response text---> ", eth_prices.text)
                    time.sleep(2)

            # Extract the ETH price in USD only
            usd_price = float(eth_prices_json["result"]["ethusd"])
            # Pice in USD of the Token/NFT sale/transfer
            final_price_usd = round(final_price_eth*usd_price, 2)

            # The following only applies if the URL image of your NFT includes
            # the token ID if not then you need to adapt the code to your needs
            # **Contact me if you need help with this
            # For 10,000 NFT collection from 0 to 9999 (4 digits collection)
            if len(token_id) == 1:
                token_id = "00" + token_id
            elif len(token_id) == 2:
                token_id = "0" + token_id

            # URL of the NFT image in you server including the NFT token ID
            link_nft_image = "https://phunks.s3.us-east-2.amazonaws.com/images/phunk" + \
                token_id+".png"

            # URL of the 'Transaction Details' (sale/transfer) in etherscan
            url_tx = etherscan_base_url+Txn_Hash

            # Final text to post in twitter with a custom message, price in ETH,
            # the price in USD, the URL to the Transaction in etherscan and some hash tags,
            # adapt this code to your needs.
            # **Contact me if you need help with this
            nft_sale_text = "Phunk #"+str(token_id) + " was flipped for Ξ" + \
                str(final_price_eth) + " ($"+str(final_price_usd)+")\n"
            hash_tags = "#CryptoPhunks #Phunks #AltPhunks"
            tweet_text = nft_sale_text + url_tx + "\n" + hash_tags

            # Twitter API connection/authentication
            auth = tweepy.OAuthHandler(consumer_token, consumer_secret)
            try:
                redirect_url = auth.get_authorization_url()
            except tweepy.TweepError:
                print("Error! Failed to get request token.")

            auth = tweepy.OAuthHandler(consumer_token, consumer_secret)
            auth.set_access_token(key, secret)

            api = tweepy.API(auth)
            try:
                api.verify_credentials()
                print("Twitter Authentication Success")
            except:
                print("Twitter Authentication Error")

            tweets_urls = []
            tweets = api.user_timeline(
                screen_name=sk.twitter_username, count=15)
            for tweet in tweets:
                expanded_url = tweet._json["entities"]["urls"][0][
                    "expanded_url"]
                tweets_urls.append(expanded_url)

            if url_tx in tweets_urls:
                print("Avoiding repetead tweet with tx url: ",  url_tx)
                continue

            # Download (temporarily) the NFT image to attach it to the twitter post
            response = requests.get(link_nft_image)
            file = open(image_name, "wb")
            file.write(response.content)
            file.close()
            ut.create_background(image_name, (96, 131, 151))

            # Post the message in your Twitter Bot account
            # with the image of the sold NFT attached
            media = api.media_upload(image_name)
            # Post the message in your Twitter Bot account
            # with the image of the sold NFT attached
            res_status = api.update_status(
                status=tweet_text, media_ids=[media.media_id])

            if "created_at" in res_status._json:
                print("Tweet posted at: ", res_status._json["created_at"])

            """Remove the downloaded image"""
            os.remove(image_name)
        elif from_address == sk.vault_token_address:
            print(from_address)
    # The Free Api-Key Token from Etherscan only allows Up to 100,000 API calls per day
    # so wait some seconds to make a new request to check for a new Transaction
    # Adapt this wait time as you need
    time.sleep(2)
