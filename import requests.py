import requests

url="https://strategies-ceo-peoples-seem.trycloudflare.com"

print(requests.get(url+"/api/version").text)