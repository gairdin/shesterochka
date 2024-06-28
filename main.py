import asyncio
from bson import ObjectId
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic.v1 import BaseSettings
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from models import User, Promotion
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from pymongo import MongoClient
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pydantic import BaseModel
from typing import List
import datetime
from datetime import datetime


# Настройки для загрузки переменных окружения
class Settings(BaseSettings):
    MONGODB_URI: str
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_LOGIN: str
    SMTP_PASSWORD: str
    SECRET: str

    class Config:
        env_file = ".env"


settings = Settings()

app = FastAPI()

# Отладка: Печать загруженных переменных окружения
print("MONGODB_URI:", settings.MONGODB_URI)
print("SMTP_SERVER:", settings.SMTP_SERVER)
print("SMTP_PORT:", settings.SMTP_PORT)
print("SMTP_LOGIN:", settings.SMTP_LOGIN)
print("SMTP_PASSWORD:", settings.SMTP_PASSWORD)
print("SECRET:", settings.SECRET)

# JWT configuration
SECRET_KEY = settings.SECRET
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not set")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Подключение к MongoDB
uri = settings.MONGODB_URI
client = MongoClient(uri)
db = client.get_database()
users_collection = db["users"]
admin_users_collection = db["admin_users"]

# Инициализация шаблонов Jinja2
templates = Jinja2Templates(directory="templates")

# Монтирование статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")


class TokenData(BaseModel):
    username: Optional[str] = None


# Хеширование и проверка паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
    to_encode = data.copy()
    print(f"Creating token with data: {to_encode}")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(request: Request):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = request.cookies.get("access_token")
        if not token:
            raise credentials_exception
        scheme, _, param = token.partition(" ")
        if scheme.lower() != "bearer":
            raise credentials_exception
        payload = jwt.decode(param, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = admin_users_collection.find_one({"username": token_data.username})
    if user is None:
        raise credentials_exception
    return user


# Маршрут для отображения формы регистрации на главной странице
@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Маршрут для отображения страницы входа в систему
@app.get("/admin/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = admin_users_collection.find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": form_data.username})
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response


from typing import Dict, Any


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = await get_current_user(request)
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})


def convert_objectid_to_str(promotion: Dict[str, Any]) -> Dict[str, Any]:
    # Преобразует ObjectId в строку, если он существует в документе
    if '_id' in promotion and isinstance(promotion['_id'], ObjectId):
        promotion['_id'] = str(promotion['_id'])
    return promotion


@app.post("/promotions/send/{action_id}")
async def send_promotion_to_all_users(action_id: str, background_tasks: BackgroundTasks):
    try:
        # Convert action_id to ObjectId
        obj_id = ObjectId(action_id)

        # Find promotion by ID
        promotions_collection = db["promotions"]
        promotion = promotions_collection.find_one({"_id": obj_id})

        if not promotion:
            raise HTTPException(status_code=404, detail=f"Promotion with id {action_id} not found")

        # Further logic to handle promotion and user emails
        users = users_collection.find()
        emails = [user['email'] for user in users]

        # Background task to send promotion emails
        background_tasks.add_task(send_promotion_email, promotion, emails)

        return {"message": "Рассылка начата"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def send_promotion_email(promotion: dict, emails: list):
    smtp_server = settings.SMTP_SERVER
    smtp_port = settings.SMTP_PORT
    smtp_login = settings.SMTP_LOGIN
    smtp_password = settings.SMTP_PASSWORD

    msg = MIMEMultipart()
    msg['From'] = formataddr(('Шестёрочка', smtp_login))
    msg['Subject'] = promotion['title']
    message = f"""
    {promotion['description']}

    Начало: {promotion['start_date']}
    Окончание: {promotion['end_date']}
    """
    msg.attach(MIMEText(message, 'plain'))

    server = None

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_login, smtp_password)

        # Установка заголовка To один раз перед циклом отправки
        msg['To'] = ', '.join(emails)

        server.sendmail(smtp_login, emails, msg.as_string())
        print(f"Email sent successfully to {', '.join(emails)}")

    except Exception as e:
        print(f"Error sending email: {e}")

    finally:
        if server:
            server.quit()


def send_welcome_email(email: str, name: str):
    smtp_server = settings.SMTP_SERVER
    smtp_port = settings.SMTP_PORT
    smtp_login = settings.SMTP_LOGIN
    smtp_password = settings.SMTP_PASSWORD

    msg = MIMEMultipart()
    msg['From'] = formataddr(('Шестёрочка', smtp_login))
    msg['To'] = email
    msg['Subject'] = "Добро пожаловать в Шестёрочку!"
    message = f"Привет {name}, спасибо что подписались на рассылку"
    msg.attach(MIMEText(message, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_login, smtp_password)
        server.sendmail(smtp_login, email, msg.as_string())
        print("Email sent successfully!")
    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP authentication error: {e.smtp_code}, {e.smtp_error}")  # Corrected syntax here
    except Exception as e:
        print(f"Error sending email: {e}")
    finally:
        server.quit()


@app.post("/register/")
async def register(background_tasks: BackgroundTasks, name: str = Form(...), email: str = Form(...)):
    user = User(name=name, email=email)
    user_data = user.dict()
    users_collection.insert_one(user_data)
    background_tasks.add_task(send_welcome_email, email, name)
    return {"message": "User registered and welcome email sent"}


def convert_objectid_to_str(promotion):
    promotion['_id'] = str(promotion['_id'])
    return promotion


@app.get("/promotions", response_model=List[Promotion])
async def get_promotions():
    promotions_collection = db["promotions"]
    promotions = list(promotions_collection.find())
    promotions = [convert_objectid_to_str(promotion) for promotion in promotions]
    return promotions


from migration import update_password_hashes


@app.on_event("startup")
async def on_startup():
    # Вызов функции обновления хешей паролей при запуске приложения
    await update_password_hashes()


promotions_collection = db["promotions"]


@app.post("/promotions/upload")
async def upload_promotions(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        content = await file.read()
        content = content.decode('utf-8')
        lines = content.split('\n')
        for line in lines:
            if line.strip():
                title, description, start_date, end_date = line.split(';')
                promotion = {
                    "title": title.strip(),
                    "description": description.strip(),
                    "start_date": start_date.strip(),
                    "end_date": end_date.strip()
                }
                promotions_collection.insert_one(promotion)
                # Background task to send promotion emails
                users = users_collection.find()
                emails = [user['email'] for user in users]
                background_tasks.add_task(send_promotion_email, promotion, emails)

        return {"message": "Файл успешно загружен и акции отправлены"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.delete("/promotions/{promotion_id}")
async def delete_promotion(promotion_id: str):
    try:
        obj_id = ObjectId(promotion_id)
        result = promotions_collection.delete_one({"_id": obj_id})
        if result.deleted_count == 1:
            return {"message": "Акция успешно удалена"}
        else:
            raise HTTPException(status_code=404, detail="Акция не найдена")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def delete_expired_promotions():
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Найти все просроченные акции
        expired_promotions = promotions_collection.find({"end_date": {"$lt": current_date}})

        for promotion in expired_promotions:
            promotion_id = promotion["_id"]
            promotions_collection.delete_one({"_id": promotion_id})
            print(f"Expired promotion with ID {promotion_id} deleted")

    except Exception as e:
        print(f"Error deleting expired promotions: {e}")


async def periodic_task():
    while True:
        await delete_expired_promotions()
        await asyncio.sleep(86400)  # Пауза в 24 часа (86400 секунд) перед следующей проверкой


async def main():
    task = asyncio.create_task(periodic_task())
    await task


if __name__ == "__main__":
    asyncio.run(main())
