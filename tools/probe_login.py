import os

import requests

base = os.environ.get('API_BASE', 'https://qa.example.invalid')
paths = [
    "/REST/central/user/auth/login",
    "/REST/sso/login",
    "/REST/site/auth/login",
    "/REST/site/1/auth/login",
    "/REST/site/1/auth/logout",
    # try under v-apiserver prefix (the OpenAPI spec uses /v-apiserver)
    "/v-apiserver/REST/central/user/auth/login",
    "/v-apiserver/REST/sso/login",
    "/v-apiserver/REST/site/auth/login",
    "/v-apiserver/REST/site/1/auth/login",
]
creds = {'username':'qa_automation@soterix.com','password':'replace_me_securely'}
for p in paths:
    url = base + p
    try:
        r = requests.post(url, json=creds, verify=False, timeout=10)
        print(f"{p} -> {r.status_code}")
        text = r.text or ''
        print(text[:800])
    except Exception as e:
        print(f"{p} -> EXC: {e}")

# Additional probing: try different query parameter names for central login
print("\n-- probing central login with alternate param names --")
central = base + "/v-apiserver/REST/central/user/auth/login"
param_variants = [
    {"username": creds['username'], "password": creds['password']},
    {"userid": creds['username'], "password": creds['password']},
    {"userId": creds['username'], "password": creds['password']},
    {"email": creds['username'], "password": creds['password']},
]
for pv in param_variants:
    try:
        r = requests.post(central, params=pv, json=pv, verify=False, timeout=10)
        print(pv, r.status_code)
        print(r.text[:400])
    except Exception as e:
        print(pv, "EXC", e)

print("\n-- probing sso/login with alternate body shapes --")
sso = base + "/v-apiserver/REST/sso/login"
sso_bodies = [
    {"username": creds['username'], "password": creds['password']},
    {"userid": creds['username'], "password": creds['password']},
    {"userName": creds['username'], "password": creds['password']},
    {"email": creds['username'], "password": creds['password']},
    {"user": creds['username'], "pass": creds['password']},
]
for b in sso_bodies:
    try:
        r = requests.post(sso, json=b, verify=False, timeout=10)
        print(b.keys(), r.status_code)
        print(r.text[:400])
    except Exception as e:
        print(b.keys(), "EXC", e)
