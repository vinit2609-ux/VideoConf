# utils/jitsi.py
import jwt
import time
 
def generate_jitsi_jwt(room_name, user_name):
    app_id = 'local_jitsi_app'  # Must match JWT_APP_ID in .env
    app_secret = 'supersecret123'  # Must match JWT_APP_SECRET in .env
    domain = "https://127.0.0.1:8080/"  # Matches your Jitsi server
 
    now = int(time.time())
 
    payload = {
        "aud": app_id,
        "iss": app_id,
        "sub": domain,
        "room": room_name,
        "exp": now + 3600,  # 1 hour expiry
        "nbf": now,
        "context": {
            "user": {
                "name": user_name,
                "moderator": True
            }
        }
    }
 
    token = jwt.encode(payload, app_secret, algorithm="HS256")
    print("Generated Jits:", token)
    return token
 
 