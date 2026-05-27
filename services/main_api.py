from fastapi import FastAPI, Depends, HTTPException, Header
import jwt
import os
from typing import Optional
from dotenv import load_dotenv

from external_api import data_service

load_dotenv()

app = FastAPI(title="Data API (Zero Trust)")

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_zero_trust_key")
JWT_ALGORITHM = "HS256"


def verify_jwt_token(authorization: Optional[str] = Header(None)):
    """Middleware для проверки JWT токена"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Отсутствует заголовок Authorization")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Неверная схема аутентификации")

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], audience="service_b_data")

        if payload.get("iss") != "service_a_gateway":
            raise HTTPException(status_code=403, detail="Недоверенный источник (Issuer)")

        return payload
    except jwt.ExpiredSignatureError:
        print("JWT ERROR: Токен просрочен")
        raise HTTPException(status_code=401, detail="Токен просрочен")
    except jwt.InvalidTokenError as e:
        print(f"JWT ERROR: {e}")
        raise HTTPException(status_code=401, detail="Недействительный токен")

@app.get("/api/users")
async def get_users(token_payload: dict = Depends(verify_jwt_token)):
    print(f"DEBUG: Data API - Запрос списка пользователей от {token_payload.get('iss')}")
    return data_service.get_all_users()


@app.get("/api/grades/{user_name}")
async def get_grades(user_name: str, token_payload: dict = Depends(verify_jwt_token)):
    print(f"DEBUG: Data API - Запрос оценок для {user_name} от {token_payload.get('iss')}")
    return data_service.get_grades_for_user(user_name)