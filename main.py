from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
import os
import traceback
import jwt
import httpx
from datetime import datetime, timedelta
from dotenv import load_dotenv

from auth.oauth import oauth

load_dotenv()

app = FastAPI(title="Student Gradebook Gateway")
config = Config('.env')
VK_CLIENT_ID = config('VK_CLIENT_ID')

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "random_string"),
    session_cookie="grades_session_id",
    same_site="lax",
    https_only=True
)

templates = Jinja2Templates(directory="templates")
VK_REDIRECT_URI = "https://localhost"

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_zero_trust_key")
DATA_SERVICE_URL = "https://127.0.0.1:8001/api"


def create_service_token() -> str:
    """Генерация JWT для межсервисной аутентификации"""
    payload = {
        "iss": "service_a_gateway",
        "aud": "service_b_data",
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def fetch_from_data_service(endpoint: str):
    """Выполнение защищенного запроса к Сервису Б (mTLS + JWT)"""
    token = create_service_token()
    headers = {"Authorization": f"Bearer {token}"}

    cert_files = ("client-cert.pem", "client-key.pem")
    url = f"{DATA_SERVICE_URL}{endpoint}"

    print(f"\n[Zero Trust] ---> Инициируем mTLS соединение с {url}")

    try:
        async with httpx.AsyncClient(cert=cert_files, verify=False) as client:
            response = await client.get(url, headers=headers)
            print(f"[Zero Trust] <--- Успех! Сервис Б ответил статусом: {response.status_code}")
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        print(f"[Zero Trust ERROR] Сервис Б отклонил запрос! Статус: {e.response.status_code}")
        raise e

    except Exception as e:
        print(f"\n[Zero Trust CRITICAL] Соединение разорвано на транспортном уровне!")
        print(f"Тип ошибки: {e.__class__.__name__}")
        print(f"Детали: {e}")
        import traceback
        traceback.print_exc()

        raise e


@app.get("/login", name="login")
async def login(request: Request):
    return await oauth.vk.authorize_redirect(
        request, VK_REDIRECT_URI, state=os.urandom(16).hex(),
    )


@app.get("/logout", name="logout")
async def logout(request: Request):
    request.session.pop('user_full_name', None)
    request.session.pop('is_admin', None)
    return RedirectResponse(url='/')


@app.get("/", name="home")
async def home(request: Request):
    if 'code' in request.query_params:
        extra_params = {'device_id': request.query_params['device_id']} if 'device_id' in request.query_params else {}
        try:
            token = await oauth.vk.authorize_access_token(request, **extra_params)
            user_info = await oauth.vk.userinfo(token=token, params={'client_id': VK_CLIENT_ID})

            user_data = user_info.get('user', {})
            if user_data.get('email'):
                request.session[
                    'user_full_name'] = f"{user_data.get('first_name', 'Admin')} {user_data.get('last_name', '')}"
                request.session['is_admin'] = True
                return RedirectResponse(url='/select_user', status_code=302)
        except Exception as e:
            traceback.print_exc()
            return templates.TemplateResponse("login.html", {"request": request, "error": str(e)})

    if request.session.get('is_admin'):
        return RedirectResponse(url='/select_user', status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})



@app.get("/select_user", name="select_user")
async def select_user(request: Request):
    if not request.session.get('is_admin'):
        return RedirectResponse(url='/', status_code=302)

    try:
        all_users = await fetch_from_data_service("/users")
    except Exception as e:
        print(f"Ошибка связи с Data API: {e}")
        all_users = []

    admin_name = request.session.get('user_full_name', 'Администратор')
    return templates.TemplateResponse("select_user.html", {
        "request": request,
        "admin_name": admin_name,
        "users": all_users
    })


@app.get("/grades/{user_name}", name="grades_view")
async def grades_view(request: Request, user_name: str):
    if not request.session.get('is_admin'):
        return RedirectResponse(url='/', status_code=302)

    try:
        student_data = await fetch_from_data_service(f"/grades/{user_name}")
    except Exception as e:
        print(f"Ошибка связи с Data API: {e}")
        student_data = []

    admin_name = request.session.get('user_full_name', 'Администратор')
    return templates.TemplateResponse("grades.html", {
        "request": request,
        "admin_name": admin_name,
        "student_name": user_name,
        "data": student_data
    })