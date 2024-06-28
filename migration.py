from pymongo import MongoClient
from passlib.context import CryptContext
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Подключение к MongoDB
uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/Cluster0")
client = MongoClient(uri)
db = client["Cluster0"]
admin_users_collection = db["admin_users"]

# Настройка контекста хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def update_password_hashes():
    try:
        users = admin_users_collection.find()
        for user in users:
            if not user["password"].startswith("$2b$"):  # Проверка на то, что пароль не является хешем bcrypt
                hashed_password = pwd_context.hash(user["password"])
                admin_users_collection.update_one({"_id": user["_id"]}, {"$set": {"password": hashed_password}})
                print(f"Password for user {user['username']} has been hashed.")
            else:
                print(f"Password for user {user['username']} is already hashed.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(update_password_hashes())
