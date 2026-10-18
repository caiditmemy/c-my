from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

SECRET_KEY = "npc_bi_mat_khong_the_bat_mi_fastapi_123"
ALGORITHM = "HS256"

# Tạo cổng kiểm tra header Authorization: Bearer <token>
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload  # Trả về dữ liệu người dùng bên trong token
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="[NPC Cảnh Báo] Ấn ký JWT đã cạn kiệt năng lượng (Hết hạn)!"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="[NPC Cảnh Báo] Ấn ký JWT giả mạo hoặc không hợp lệ!"
        )