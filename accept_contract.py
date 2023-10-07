import json
from straders_sdk import SpaceTraders

user = json.load(open("user.json"))
current_agent_symbol = user.get("agents")[0]["username"]
current_agent_token = user.get("agents")[0]["token"]

client = SpaceTraders(
    current_agent_token,
    db_host=user["db_host"],
    db_port=user["db_port"],
    db_name=user["db_name"],
    db_user=user["db_user"],
    db_pass=user["db_pass"],
    current_agent_symbol=current_agent_symbol,
)


all_contracts = client.view_my_contracts()
unaccepted_contracts = [c for c in all_contracts if not c.accepted]
for con in unaccepted_contracts:
    resp = client.contract_accept(con.id)
    if not resp:
        print("Failed to accept contract %s" % con.id)
        print(resp.error_code)
        print(resp.error)
