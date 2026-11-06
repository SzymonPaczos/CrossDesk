import requests


def price(order):
    return requests.get("https://example.com").json()
