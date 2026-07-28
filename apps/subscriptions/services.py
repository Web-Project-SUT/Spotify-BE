import requests

ZARINPAL_MERCHANT_ID = "00000000-0000-0000-0000-000000000000"
ZARINPAL_REQUEST_URL = "https://sandbox.zarinpal.com/pg/rest/WebGate/PaymentRequest.json"
ZARINPAL_VERIFY_URL = "https://sandbox.zarinpal.com/pg/rest/WebGate/PaymentVerification.json"

def initiate_payment(amount, description, callback_url):
    data = {
        "MerchantID": ZARINPAL_MERCHANT_ID,
        "Amount": int(amount * 10000),  # تبدیل به تومان برای درگاه
        "Description": description,
        "CallbackURL": callback_url,
    }
    try:
        response = requests.post(ZARINPAL_REQUEST_URL, json=data, timeout=5)
        if response.status_code == 200:
            res = response.json()
            if res.get("Status") == 100:
                authority = res.get("Authority")
                return authority, f"https://sandbox.zarinpal.com/pg/StartPay/{authority}"
    except requests.RequestException:
        pass
    return None, None

def verify_payment(authority, amount):
    data = {
        "MerchantID": ZARINPAL_MERCHANT_ID,
        "Authority": authority,
        "Amount": int(amount * 10000),
    }
    try:
        response = requests.post(ZARINPAL_VERIFY_URL, json=data, timeout=5)
        if response.status_code == 200:
            res = response.json()
            if res.get("Status") in [100, 101]:
                return True, res.get("RefID")
    except requests.RequestException:
        pass
    return False, None