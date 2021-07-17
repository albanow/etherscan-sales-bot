import requests
import time
import tweepy
import secrets_keys as sk
import pyshorteners as sh
import os
import json

s = sh.Shortener()

""" Get this from your Twitter development account (not in repo) 
you need to create secrets_keys.py file in your cloned repo """
consumer_token = sk.consumer_token
consumer_secret = sk.consumer_secret
key = sk.key
secret = sk.secret
etherscan_base_url = "https://etherscan.io/tx/"
etherscan_eth_prices = "https://api.etherscan.io/api?module=stats&action=ethprice&apikey="
etherscan_url_transfers = "https://api.etherscan.io/api?module=account&action=tokennfttx&contractaddress="
etherscan_url_tx = "https://api.etherscan.io/api?module=account&action=txlistinternal&txhash="


"""URL of the latest transfer in etherscan for a defined contract [ERC-721]
you need to have the contract number (contract_number) and your etherscan Api-Key Token
(etherscan_key) defined in the secrets_keys.py file"""
url_transfers = etherscan_url_transfers+sk.contract_number + \
    "&page=1&offset=1&sort=desc&apikey="+sk.etherscan_key
headers_req = {'Accept': 'application/json'}

"""Seed for the bot to start (latest Txn Hash from Etherscan"""
past_tx = "0x7e059114725ecacbdce8f8e7824f56c415b02615c027ca1f969d4336aebf48cd"
latest_tx = ""

"""Run the Bot til the infinite"""
while True:

    sum_price = 0
    """Make a request to get the latest transfer.
    Try 10 times in case any exception is throw"""
    for _ in range(10):
        try:
            r_asset = requests.post(url_transfers, headers=headers_req)
            r_json = r_asset.json()
            r_asset.close()
            break
        except (ConnectionResetError, requests.exceptions.RequestException, json.decoder.JSONDecodeError):
            print(r_asset, "----", r_asset.text)
            time.sleep(2)

    """Need to extract the Txn Hash and token of the latest Transfer
    from etherscan """
    Txn_Hash = r_json["result"][0]["hash"]
    latest_tx = Txn_Hash
    token_id = str(r_json["result"][0]["tokenID"])

    url_txhash = etherscan_url_tx+str(Txn_Hash)+"&apikey="+sk.etherscan_key

    for _ in range(10):
        try:
            """Make a request to the extracted Txn Hash from the latest Transfer"""
            hash_details = requests.post(url_txhash)
            r_json_details = hash_details.json()
            hash_details.close()
            break
        except (ConnectionResetError, requests.exceptions.RequestException, json.decoder.JSONDecodeError):
            print(hash_details, "----", hash_details.text)
            time.sleep(2)

    if latest_tx != past_tx:
        past_tx = latest_tx
        """There can be multiple transactions for one Transfer, so we iterate in the response
        to get all the transacion and add all the 'values' in each transacion on the Txn Hash"""
        if r_json_details["status"] != "0" and "value" in r_json_details["result"][-1]:
            """" Do some magic to get all the 'values' and add them to get the real price of
            the Transfer in ETH """
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
                            asset_price = asset_price_api[:-idx]
                            break
                else:
                    asset_price = round(float(
                        asset_price_api[:price_size-asset_dec_int] + "." + asset_price_api[price_size-asset_dec_int:]), 6)

                sum_price = float(asset_price) + sum_price

            """Final price(cost) of the Transfer in ETH rounded to 6 decimals"""
            final_price_eth = round(float(sum_price), 6)

            for _ in range(10):
                try:
                    """Get the current prices of ETH (BTC and USD)"""
                    eth_prices = requests.post(
                        etherscan_eth_prices+sk.etherscan_key)
                    eth_prices_json = eth_prices.json()
                    break
                except (ConnectionResetError, requests.exceptions.RequestException, json.decoder.JSONDecodeError):
                    print(eth_prices, "----", eth_prices.text)
                    time.sleep(2)

            """Extract the ETH price in USD"""
            usd_price = float(eth_prices_json["result"]["ethusd"])
            final_price_usd = round(final_price_eth*usd_price, 2)

            """URL of the NFT image"""
            if len(token_id) == 1:
                token_id = "000"+token_id
            elif len(token_id) == 2:
                token_id = "00"+token_id
            elif len(token_id) == 3:
                token_id = "0"+token_id

            link_phunk = "https://phunks.s3.us-east-2.amazonaws.com/notpunks/notpunk" + \
                token_id+".png"

            """Short the URL of the 'Transaction Details' in etherscan"""
            url_tx = etherscan_base_url+Txn_Hash

            """Short the URL of the 'Transaction Details' in etherscan
            note: this can be fail if the tinyurl server is unreachable"""
            """ etherscan_tx_url = etherscan_base_url+Txn_Hash
            url_tx = s.tinyurl.short(etherscan_tx_url) """

            """Download the NFT image to attach it to the twitter post"""
            response = requests.get(link_phunk)
            file = open("nft_image.png", "wb")
            file.write(response.content)
            file.close()

            """Final text to post in twitter with the price in ETH, the price in
            USD, the image of the NFT, the URL to the Transaction in etherscan
            and some hash tags"""
            phunk_sale = "Phunk #"+str(token_id) + " was flipped for Ξ" + \
                str(final_price_eth) + " ($"+str(final_price_usd)+")\n"
            hash_tags = "#CryptoPhunks #Phunks #AltPhunks"
            tweet = phunk_sale + url_tx + "\n" + hash_tags

            """Twitter API connection/authentication"""
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
                print("Authentication OK")
            except:
                print("Authentication error")

            """Update the status in Twitter"""
            res_status = api.update_with_media('nft_image.png', status=tweet)

            """Remove the downloaded image"""
            os.remove("nft_image.png")

    """The Free Api-Key Token from Etherscan only allows Up to 100,000 API calls per day
    so wait 5 seconds to make a new request to check for a new Transaction"""
    time.sleep(2)
