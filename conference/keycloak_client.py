from keycloak import KeycloakAdmin, KeycloakOpenID, KeycloakOpenIDConnection
import os
from dotenv import load_dotenv
load_dotenv()



server_url=os.getenv("server_url")
client_id=os.getenv("client_id")
realm_name=os.getenv("realm_name")
client_secret_key=os.getenv("client_secret_key")

# print("*************************************************************")
# print(server_url)
# print(client_id)
# print(realm_name)
# print(client_secret_key)
# print("*************************************************************")


keycloak_openid = KeycloakOpenID(
    server_url=server_url,
    client_id=client_id,
    realm_name=realm_name,
    client_secret_key=client_secret_key,
    verify=False
)

# token = keycloak_openid.token("Sanath", "Test@123")
# print(token["access_token"])

keycloak_connection = KeycloakOpenIDConnection(
            server_url=server_url,
            realm_name=realm_name,
            user_realm_name = realm_name,
            client_id = client_id,
            client_secret_key = client_secret_key,
            verify=True)
keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
 
        # return keycloak_admin

# keycloak_admin = KeycloakAdmin(
#     server_url=server_url,
#     # username="admin",
#     # password="admin",
#     realm_name=realm_name,
#     client_id=client_id,
#     client_secret_key=client_secret_key,
#     verify=True
# )
# print("///////////////////////")

def create_keycloak_user(username, password):
    user = {
        "username": username,
        # "email": email,
        # "firstName": first_name,
        # "lastName": last_name,
        "enabled": True,
        "credentials": [{"value": password, "type": "password"}]
    }
    user_id = keycloak_admin.create_user(user)
    return user_id
