"""Get Yougile API key interactively."""
import getpass
import httpx

BASE = "https://ru.yougile.com/api-v2"

email = input("Yougile email: ")
password = getpass.getpass("Yougile password: ")

# Step 1: Get companies
resp = httpx.post(f"{BASE}/auth/companies", json={"login": email, "password": password})
if resp.status_code != 200:
    print(f"Auth failed: {resp.status_code} {resp.text}")
    raise SystemExit(1)

companies = resp.json().get("content", [])
if not companies:
    print("No companies found for this account.")
    raise SystemExit(1)

if len(companies) == 1:
    company = companies[0]
else:
    print("\nCompanies:")
    for i, c in enumerate(companies):
        print(f"  {i + 1}. {c['name']} (admin: {c['isAdmin']})")
    choice = int(input("Choose number: ")) - 1
    company = companies[choice]

print(f"\nUsing company: {company['name']}")

# Step 2: Create API key
resp = httpx.post(f"{BASE}/auth/keys", json={
    "login": email,
    "password": password,
    "companyId": company["id"],
})
if resp.status_code not in (200, 201):
    print(f"Failed to create key: {resp.status_code} {resp.text}")
    raise SystemExit(1)

key = resp.json().get("key", "")
print(f"\nAPI Key: {key}")
print(f"\nTo use: export YOUGILE_API_KEY='{key}'")
