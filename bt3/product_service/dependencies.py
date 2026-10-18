from fastapi import Header, HTTPException, status
import httpx

# Cổng của Auth Service (Bài TH số 2)
AUTH_SERVICE_VERIFY_URL = "http://localhost:8001/verify"

async def verify_auth_token(authorization: Optional[str] = Header(None)):
    """Giao tiếp HTTP liên dịch vụ (Inter-service call) để xác thực."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu cung cấp Authorization Header (Bearer token)",
        )

    async with httpx.AsyncClient() as client:
        try:
            # Gửi request sang Auth Service
            response = await client.get(
                AUTH_SERVICE_VERIFY_URL,
                headers={"Authorization": authorization},
                timeout=5.0
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token không hợp lệ hoặc đã hết hạn từ Auth Service",
                )
            
            # Trả về thông tin user đã xác thực nếu cần dùng
            return response.json()

        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth Service hiện không khả dụng, không thể hoàn tất xác thực",
            )