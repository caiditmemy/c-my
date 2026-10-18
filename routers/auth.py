from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import jwt
from dependencies import SECRET_KEY, ALGORITHM

router = APIRouter(tags=["Authentication"])

# Phụ lục Bảng Người Dùng (Mô phỏng dữ liệu)
users_table = [
    {
        "IdUser": 1,
        "UserName": "hiep_si_tan_thu",
        "Password": "password123",  # Client gửi lên đã mã hóa Base64 hoặc MD5
        "Token": None
    },
    {
        "IdUser": 2,
        "UserName": "phap_su_ao_den@guild.com",
        "Password": "darkmagicpassword",
        "Token": None
    }
]

# Khuôn mẫu dữ liệu đầu vào (Pydantic Models)
class LoginRequest(BaseModel):
    userName: str
    password: str

class AuthTokenRequest(BaseModel):
    token: str

@router.post("/login")
def login(data: LoginRequest):
    # Tra cứu danh tính trong sổ bộ User
    user = next((u for u in users_table if u["UserName"] == data.userName and u["Password"] == data.password), None)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không khớp trong danh sách chiến binh!"
        )

    # Đúc Token có hạn 1 giờ
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "IdUser": user["IdUser"],
        "UserName": user["UserName"],
        "exp": expire
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    # Cập nhật Token vào bảng User theo đúng phụ lục đề bài
    user["Token"] = token

    return {
        "message": "Đăng nhập thành công! Nhận lấy ấn ký:",
        "token": token
    }

@router.post("/auth")
def authenticate_token(data: AuthTokenRequest):
    try:
        decoded = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "valid": True,
            "message": "Ấn ký chuẩn chỉ do Guild ban cấp!",
            "data": decoded
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Xác thực thất bại: {str(e)}"
        )   