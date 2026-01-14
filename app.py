import os
import secrets
import hashlib
import base64
import urllib.parse
import json

import requests
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='.')
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable must be set")

# Session cookie configuration for OAuth flows with external identity providers
# SameSite=None is required for cross-origin redirects from OAuth providers (e.g., Keycloak)
# Secure=True is required when SameSite=None (enforced by browsers)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

USERNAME = os.getenv("APP_USERNAME", "")
PASSWORD = os.getenv("APP_PASSWORD", "")




# Keycloak OAuth configuration
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "")  # e.g., https://keycloak.example.com
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "")  # e.g., my-realm
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")

# App origin for OAuth (must be explicitly configured)
APP_ORIGIN = os.getenv("APP_ORIGIN", "")

# Cloud.ru API credentials
CLOUD_CLIENT_ID = os.getenv("CLOUD_CLIENT_ID", "")
CLOUD_CLIENT_SECRET = os.getenv("CLOUD_CLIENT_SECRET", "")

@app.route("/", methods=["GET"])
def web():
    is_authed = session.get("is_authed", False)
    user_info = {
        "name": session.get("user_name"),
        "email": session.get("user_email"),
        "cloud_project_id": session.get("user_cloud_project_id"),
        "all_vms": session.get("all_vms")
    } if is_authed else None
    return render_template("index.html", is_authed=is_authed, user_info=user_info)


@app.route("/login", methods=["POST"])
def login():
    login_val = request.form.get("login", "")
    password_val = request.form.get("password", "")
    if login_val == USERNAME and password_val == PASSWORD:
        session["is_authed"] = True
        flash("Успешный вход", "success")
        return redirect(url_for("web"))
    flash("Неверный логин или пароль", "error")
    return redirect(url_for("web"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Вы вышли из системы", "info")
    return redirect(url_for("web"))


def generate_code_verifier():
    """Generate a random code_verifier for PKCE."""
    return secrets.token_urlsafe(32)


def generate_code_challenge(code_verifier):
    """Generate code_challenge from code_verifier using S256 method."""
    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


@app.route("/oauth/keycloak/init", methods=["POST"])
def keycloak_oauth_init():
    """Initialize Keycloak OAuth flow using redirect approach."""
    if not KEYCLOAK_URL or not KEYCLOAK_REALM or not KEYCLOAK_CLIENT_ID:
        return jsonify({"success": False, "error": "Keycloak not configured"}), 500

    if not APP_ORIGIN:
        return jsonify({"success": False, "error": "APP_ORIGIN not configured"}), 500

    response = os.system("ping -c 1 -w2 10.10.11.16 > /dev/null 2>&1")

    if response:
        return jsonify({"success": False, "error": "Network issues with Keycloak"}), 500

    # Generate PKCE code verifier and challenge for additional security
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store in session for callback validation
    session['keycloak_state'] = state
    session['keycloak_code_verifier'] = code_verifier

    # Build Keycloak authorization URL
    keycloak_auth_url = f"{KEYCLOAK_URL}/auth/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
    redirect_uri = f"{APP_ORIGIN}/oauth/keycloak/callback"

    params = {
        'client_id': KEYCLOAK_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': 'openid profile email',
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
    }

    auth_url = f"{keycloak_auth_url}?{urllib.parse.urlencode(params)}"

    return jsonify({
        "success": True,
        "auth_url": auth_url,
        "state": state
    })


@app.route("/oauth/keycloak/callback", methods=["GET"])
def keycloak_oauth_callback():
    """Handle Keycloak OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    error_description = request.args.get('error_description', '')

    if error:
        flash(f"Ошибка авторизации Keycloak: {error_description or error}", "error")
        return redirect(url_for("web"))

    # Verify state for CSRF protection
    stored_state = session.get('keycloak_state')
    if not state or state != stored_state:
        flash("Ошибка безопасности: неверный state параметр", "error")
        return redirect(url_for("web"))

    if not code:
        flash("Ошибка: не получен код авторизации", "error")
        return redirect(url_for("web"))

    # Get stored code_verifier for PKCE
    code_verifier = session.get('keycloak_code_verifier')
    if not code_verifier:
        flash("Ошибка: PKCE verifier не найден", "error")
        return redirect(url_for("web"))

    # Exchange code for access_token
    try:
        token_url = f"{KEYCLOAK_URL}/auth/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
        redirect_uri = f"{APP_ORIGIN}/oauth/keycloak/callback"

        token_data = {
            'client_id': KEYCLOAK_CLIENT_ID,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': code_verifier,
        }

        # Add client_secret if configured (for confidential clients)
        if KEYCLOAK_CLIENT_SECRET:
            token_data['client_secret'] = KEYCLOAK_CLIENT_SECRET

        token_response = requests.post(
            token_url,
            data=token_data,
            timeout=10,
            verify=False
        )
        result = token_response.json()

        if 'error' in result:
            flash(f"Ошибка обмена токена: {result.get('error_description', result.get('error', 'Unknown error'))}", "error")
            return redirect(url_for("web"))

        # Successfully authenticated
        access_token = result.get('access_token')
        if not access_token:
            flash("Ошибка: токен доступа не получен", "error")
            return redirect(url_for("web"))

        # Optionally fetch user info
        user_info = None
        try:
            userinfo_url = f"{KEYCLOAK_URL}/auth/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
            userinfo_response = requests.get(
                userinfo_url,
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10,
                verify=False
            )
            if userinfo_response.status_code == 200:
                user_info = userinfo_response.json()
                #print(user_info)
        except requests.RequestException:
            pass  # User info is optional

        cloud_project_id_for_token = user_info.get('cloud_project_id')
        get_all_vms_in_cloud(cloud_project_id_for_token)

        session["is_authed"] = True
        session["auth_provider"] = "keycloak"
        if user_info:
            session["user_email"] = user_info.get('email')
            session["user_name"] = user_info.get('preferred_username') or user_info.get('name')
            session["user_cloud_project_id"] = user_info.get('cloud_project_id')
            session["all_vms"] = get_all_vms_in_cloud(cloud_project_id_for_token)
        # Clean up OAuth session data
        session.pop('keycloak_state', None)
        session.pop('keycloak_code_verifier', None)

        flash("Успешная авторизация через Keycloak", "success")

        return redirect(url_for("web"))

    except requests.RequestException as e:
        flash(f"Ошибка API: {str(e)}", "error")
        return redirect(url_for("web"))


def get_access_token_from_cloud():
    
    url = "https://iam.api.cloud.ru/api/v1/auth/token"
    headers = {"Content-Type": "application/json"}
    payload = {
        "keyId": CLOUD_CLIENT_ID,
        "secret": CLOUD_CLIENT_SECRET
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()

    # Получаем токен из ответа
    token_data = response.json()
    access_token = token_data.get("access_token")

    return access_token

def get_all_vms_in_cloud(cloud_project_id_for_token):
    
    token = get_access_token_from_cloud()
    
    url = f"https://compute.api.cloud.ru/api/v1/vms?project_id=49abf5c8-9f16-4ca3-b5d3-5eca9bfac631"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers, allow_redirects=True)
    response.raise_for_status()  # вызовет исключение при HTTP ошибке

    # Получаем данные
    vms_data = response.json()
    total_vms = vms_data.get("total", 0)
    return total_vms


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)