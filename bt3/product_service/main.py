from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import engine, get_db
from dependencies import verify_auth_token

# Khởi tạo bảng CSDL khi start service
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Product Management Service (SOA)", version="1.0.0")

# -------------------------------------------------------------
# 1. GET /products: Lấy danh sách tất cả sản phẩm (Public)
# -------------------------------------------------------------
@app.get("/products", response_model=List[schemas.ProductResponse])
def get_all_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    products = db.query(models.Product).offset(skip).limit(limit).all()
    return products

# -------------------------------------------------------------
# 2. GET /products/{id}: Lấy thông tin chi tiết một sản phẩm (Public)
# -------------------------------------------------------------
@app.get("/products/{id}", response_model=schemas.ProductResponse)
def get_product(id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Không tìm thấy sản phẩm có ID = {id}"
        )
    return product

# -------------------------------------------------------------
# 3. POST /products: Thêm một sản phẩm mới (Cần Auth)
# -------------------------------------------------------------
@app.post("/products", response_model=schemas.ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: schemas.ProductCreate, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_auth_token)  # Bảo vệ bằng Auth Service
):
    new_product = models.Product(**product_in.model_dump())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

# -------------------------------------------------------------
# 4. PUT /products/{id}: Cập nhật sản phẩm (Cần Auth)
# -------------------------------------------------------------
@app.put("/products/{id}", response_model=schemas.ProductResponse)
def update_product(
    id: int, 
    product_update: schemas.ProductUpdate, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_auth_token)  # Bảo vệ bằng Auth Service
):
    product = db.query(models.Product).filter(models.Product.id == id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Không tìm thấy sản phẩm có ID = {id}"
        )

    # Cập nhật các trường có gửi lên
    update_data = product_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product

# -------------------------------------------------------------
# 5. DELETE /products/{id}: Xóa một sản phẩm (Cần Auth)
# -------------------------------------------------------------
@app.delete("/products/{id}", status_code=status.HTTP_200_OK)
def delete_product(
    id: int, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_auth_token)  # Bảo vệ bằng Auth Service
):
    product = db.query(models.Product).filter(models.Product.id == id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Không tìm thấy sản phẩm có ID = {id}"
        )

    db.delete(product)
    db.commit()
    return {"message": f"Đã xóa thành công sản phẩm có ID = {id}"}