from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from pymongo.collection import Collection
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from pydantic import BaseSettings, EmailStr
from typing import List
from models import Promotion, User
from database import db

router = APIRouter()
promotions_collection: Collection = db["promotions"]
users_collection: Collection = db["users"]  # Добавляем коллекцию пользователей


class Settings(BaseSettings):
    MONGODB_URI: str
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_LOGIN: EmailStr
    SMTP_PASSWORD: str
    SECRET: str

    class Config:
        env_file = ".env"


async def get_smtp_settings():
    settings = Settings()
    return settings.SMTP_SERVER, settings.SMTP_PORT, settings.SMTP_LOGIN, settings.SMTP_PASSWORD


@router.post("/", response_model=Promotion)
async def create_promotion(promotion_data: Promotion, smtp_settings: tuple = Depends(get_smtp_settings)):
    try:
        smtp_server, smtp_port, smtp_login, smtp_password = smtp_settings

        promotion_dict = promotion_data.dict()
        result = await promotions_collection.insert_one(promotion_dict)
        promotion_dict["_id"] = str(result.inserted_id)

        # Sending promotion added email
        await send_email(smtp_server, smtp_port, smtp_login, smtp_password,
                         'receiver@example.com', 'New Promotion Added!',
                         f"New promotion added:\n\nTitle: {promotion_data.title}\nDescription: {promotion_data.description}\nStart Date: {promotion_data.start_date}\nEnd Date: {promotion_data.end_date}\nImage URL: {promotion_data.image_url}")

        return promotion_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{promotion_id}")
async def delete_promotion(promotion_id: str, smtp_settings: tuple = Depends(get_smtp_settings)):
    try:
        smtp_server, smtp_port, smtp_login, smtp_password = smtp_settings

        result = await promotions_collection.delete_one({"_id": ObjectId(promotion_id)})
        if result.deleted_count == 1:
            # Sending promotion deleted email
            await send_email(smtp_server, smtp_port, smtp_login, smtp_password,
                             'receiver@example.com', 'Promotion Deleted',
                             f"Promotion with ID {promotion_id} has been deleted.")
            return {"message": "Promotion deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Promotion not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/send/{action_id}")
async def send_promotion_to_users(action_id: str, smtp_settings: tuple = Depends(get_smtp_settings)):
    try:
        smtp_server, smtp_port, smtp_login, smtp_password = smtp_settings

        promotion = await promotions_collection.find_one({"_id": ObjectId(action_id)})
        if not promotion:
            raise HTTPException(status_code=404, detail=f"Promotion with ID {action_id} not found")

        # Retrieve users from database
        user_emails = await get_user_emails_from_db()

        # Send promotion to each user
        for email in user_emails:
            await send_email(smtp_server, smtp_port, smtp_login, smtp_password,
                             email, 'New Promotion Available!',
                             f"Check out our new promotion:\n\nTitle: {promotion['title']}\nDescription: {promotion['description']}\nStart Date: {promotion['start_date']}\nEnd Date: {promotion['end_date']}\nImage URL: {promotion['image_url']}")

        return {"message": f"Promotion with ID {action_id} successfully sent to all users"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_user_emails_from_db() -> List[str]:
    try:
        # Fetch user emails from database (example query)
        users = await users_collection.find().to_list(length=None)
        user_emails = [user['email'] for user in users]
        return user_emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch user emails from database: {str(e)}")


async def send_email(smtp_server: str, smtp_port: int, smtp_login: EmailStr, smtp_password: str,
                     recipient: str, subject: str, body: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = f'Sender Name <{smtp_login}>'
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(str(smtp_login), smtp_password)
        server.sendmail(str(smtp_login), recipient, msg.as_string())
        print(f"Email '{subject}' sent successfully!")
    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP authentication error: {e.smtp_code}, {e.smtp_error}")
        raise HTTPException(status_code=500, detail=f"SMTP authentication error: {e.smtp_code}")
    except Exception as e:
        print(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending email: {e}")
    finally:
        server.quit()

